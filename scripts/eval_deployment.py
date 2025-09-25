#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from argparse import BooleanOptionalAction
import asyncio
from asyncio import Semaphore
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
import math
import base64
import sys
import os
import random
import traceback

import numpy as np
import pandas as pd
import sglang as sgl
import torch
from PIL import Image
from tqdm.asyncio import tqdm_asyncio
from transformers import AutoProcessor, PreTrainedTokenizerBase, ProcessorMixin

from qwen_vl_utils import process_vision_info as _process_vision_info


# ===================== Utility Functions ===================== #

def process_image(image, max_pixels, min_pixels, print_size=False):
    """Load image from bytes, dict, base64 string, or file path, and convert to RGB."""
    if isinstance(image, dict) and "bytes" in image:
        image = Image.open(BytesIO(image["bytes"]))
    elif isinstance(image, bytes):
        image = Image.open(BytesIO(image))
    elif isinstance(image, str):
        if image.startswith("data:image") or "," in image:
            if "," in image:
                image = image.split(",", 1)[1]
            image = Image.open(BytesIO(base64.b64decode(image)))
        else:
            image = Image.open(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image

def write_final_result(output_dir: Path, store_name: str, succeed: bool, metrics: dict | None):
    """Write the final summary result JSON file."""
    info = {
        "store_name": store_name,
        "status": "done" if succeed else "failed",
        "finished_at": datetime.utcnow().isoformat(),
        "metrics": metrics or {},
    }
    final_path = output_dir / f"{store_name}.json"
    tmp_path = final_path.with_suffix(".json.tmp")
    with tmp_path.open("w") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    tmp_path.replace(final_path)

# ===================== Inline Agent Logic ===================== #

def format_history(history, is_aw):
    formatted_history = []
    for idx, msg in enumerate(history):
        content = msg.get("content")
        if isinstance(content, str):
            msg['content'] = msg['content'].replace('<ans>', '<answer>').replace('</ans>', '</answer>')
            if idx == 1 and is_aw:
                assert history[idx-1]['role'] == 'system', f'{history[idx-1]=}'
                if not msg['content'].startswith('[AndroidWorld Benchmark]'):
                    msg['content'] = '[AndroidWorld Benchmark]' + msg['content']
            formatted_history.append(msg)
        else:
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url" and isinstance(part["image_url"], dict):
                    new_parts.append({"type": "image","image_url":part["image_url"]["url"]})
                elif isinstance(part, dict) and part.get("type") == "text":
                    t = part.get("text", "")
                    if idx == 1 and is_aw:
                        assert history[idx-1]['role'] == 'system', f'{history[idx-1]=}'
                        if not t.startswith('[AndroidWorld Benchmark]'):
                            t = '[AndroidWorld Benchmark]' + t
                    new_parts.append({"type": "text", "text": t})
            formatted_history.append({"role": msg["role"], "content": new_parts})
    return formatted_history

def add_reward(turns):
    """Propagate the final reward to all turns and mark the last turn as done=True."""
    if not turns:
        return turns
    final_reward = turns[-1].get("reward", 0)
    for t in turns:
        t["reward"] = final_reward
        t["done"] = False
    turns[-1]["done"] = True
    return turns

def _to_openai_messages(messages):
    """Convert formatted ChatML-like messages to OpenAI 'messages' schema (supports text+image parts)."""
    out = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for p in c:
                if p.get("type") == "text":
                    parts.append({"type": "text", "text": p.get("text", "")})
                elif p.get("type") in ("image", "image_url"):
                    url = p.get("image_url")
                    if isinstance(url, dict):
                        url = url.get("url")
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            out.append({"role": m["role"], "content": parts})
        else:
            out.append({"role": m["role"], "content": c})
    return out

async def _openai_style_generate(api_base, api_key, model, messages):
    """Async call to OpenAI-style Chat Completions; returns text."""
    import aiohttp
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": _to_openai_messages(messages),
    }
   
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600), trust_env=True) as sess:
        async with sess.post(api_base, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
    text = data["choices"][0]["message"]["content"]
    return text

async def openai_chat_start(index, name, url, sid=None):
    """Simplified /start_sample request with up to 3 retries."""
    import aiohttp
    await asyncio.sleep(random.randint(0, 2))  # Random stagger to avoid spikes
    for i in range(3):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600), trust_env=True) as sess:
                async with sess.post(url + "/start_sample", json={"index": int(index), "name": name}) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    data["sid"] = resp.headers.get("session_id") or data.get("sid")
                    assert data.get("messages"), f"Empty messages in response {data.get('sid')=}"
                    return data
        except Exception:
            print(f"[WARN] start_sample failed (attempt {i+1}/3)")
            traceback.print_exc()
            if i < 2:
                await asyncio.sleep(1 + i)
                continue
            raise

async def openai_chat_obs(message, sid, url, **_):
    """Simplified /interact request to send a single assistant message and get updated state."""
    import aiohttp
    payload = {"messages": [message]}
    header = {"session_id": str(sid)}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600), trust_env=True) as sess:
        async with sess.post(url + "/interact", json=payload, headers=header) as resp:
            assert resp.status == 200, f"Wrong status {resp.status}: sid={sid} text={await resp.text()}"
            ret = await resp.json()
    ret.setdefault("messages", [])
    ret.setdefault("finish", True)
    ret.setdefault("reward", 0)
    return ret

async def openai_chat_end(sid, done, url):
    """Cancel the session if not finished."""
    if done:
        return
    import aiohttp
    try:
        async with aiohttp.ClientSession(trust_env=True) as sess:
            await sess.post(url + "/cancel", headers={"session_id": str(sid)}, json={})
    except Exception as e:
        print(f"[WARN] cancel failed: sid={sid} err={e}")

async def openai_chat_agent_loop(
    start_args: dict,
    start_fn,
    gen_fn,
    obs_fn,
    end_fn,
    max_turns: int,
    max_length: int,
    max_response_length: int,
    tokenizer: PreTrainedTokenizerBase | None,
    processor: ProcessorMixin | None,
    inference_backend: str = "sgl",
    stop_sequences=None,
    **_
):
    """
    Main multi-turn chat loop:
    - Request initial conversation context
    - Generate model response (sgl or openai backend)
    - Send to controller and receive feedback
    """
    start = await start_fn(**start_args)
    history = start.get("messages", [])
    tools = start.get("tools", None)
    sid = start.get("sid")
    image_data = start.get("image_data")
    is_aw = 'android_world' in str(start_args.get('name', ''))
    history = format_history(history, is_aw)

    if image_data:
        for msg in history:
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") == "image" and part.get("image") is None:
                        if image_data:
                            part["image"] = image_data.pop(0)


    # Prepare initial prompt/state per backend
    if inference_backend == "sgl":
        try:
            image_inputs, _ = _process_vision_info(history)
            prompt_ids = tokenizer.apply_chat_template(history, tools=tools, tokenize=True, add_generation_prompt=True)
            prompt = tokenizer.apply_chat_template(conversation=history, tokenize=False, add_generation_prompt=True)
        except Exception:
            traceback.print_exc()
            raise
        current_ids = list(prompt_ids)
    else:
        # openai backend uses messages directly
        image_inputs = None
        prompt = None
        prompt_ids = None
        current_ids = []

    turns = []
    done = False

    for _turn in range(max_turns):
        # Generate assistant response
        if inference_backend == "sgl":
            text, log_probs = await gen_fn(prompt, image_inputs, False)
            new_ids = [t[1] for t in log_probs] if log_probs else []
        else:
            # gen_fn expects messages for openai backend
            text, log_probs = await gen_fn(history, None, False)
            new_ids = []

        msg_text = text.replace('<answer>', '<ans>').replace('</answer>', '</ans>')
        assistant_msg = {"role": "assistant", "content": msg_text}

        # Send response to controller, receive reward & updated context
        obs = await obs_fn(assistant_msg, sid, url=start_args["url"])
        messages = obs.get("messages", [])
        done = bool(obs.get("finish", True))
        reward = float(obs.get("reward", 0))

        turns.append({
            "prompts": prompt_ids if inference_backend == "sgl" else None,
            "responses": new_ids,
            "response_loss_mask": [1] * len(new_ids),
            "reward": reward,
            "obs_metrics": obs.get("metrics", {}),
            "image_data": image_inputs,
            "sid": sid,
        })

        if done or (inference_backend == "sgl" and (len(new_ids) > max_response_length or len(current_ids) >= max_length)):
            break

        # Prepare for the next turn
        try:
            messages = format_history(messages, is_aw)
            if inference_backend == "sgl":
                image_inputs, _ = _process_vision_info(messages)
                prompt_ids = tokenizer.apply_chat_template(messages, tools=tools, tokenize=True, add_generation_prompt=True)
                prompt = tokenizer.apply_chat_template(conversation=messages, tokenize=False, add_generation_prompt=True)
                current_ids = list(prompt_ids)
            else:
                # openai backend: keep messages for next call
                history = messages
        except Exception:
            traceback.print_exc()
            break

        if inference_backend == "sgl" and len(current_ids) >= max_length:
            break

    await end_fn(sid, done, url=start_args["url"])
    return add_reward(turns)


# ===================== Main Benchmark Execution ===================== #

def run_benchmark(args) -> dict:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / (args.output_file if args.output_file else f"{args.store_name}.jsonl")
    print(f"[INFO] run-level results -> {output_file}")

    if output_file.exists():
        df = pd.read_json(output_file, lines=True)
    else:
        df = pd.DataFrame(columns=['model', 'task_index', 'run_number', 'result', 'timestamp', 'sid'])

    completed_runs = {(int(r['task_index']), int(r['run_number']))
                      for _, r in df.iterrows()
                      if r['model'] == args.model and r['result'] != 'error'}
    print(f"[INFO] Completed runs found: {len(completed_runs)}")

    # Backend init
    engine = None
    tokenizer = None
    processor = None

    if args.inference_backend == "sgl":
        gpu_count = torch.cuda.device_count()
        print(f"[INFO] GPUs detected: {gpu_count}")
        engine = sgl.Engine(
            model_path=args.model,
            dtype="bfloat16",
            tp_size=1,
            enable_memory_saver=False,
            enable_metrics=True,
            enable_cache_report=True,
            mem_fraction_static=0.5,
            mm_attention_backend="fa3",
            log_level="INFO",
        )
        tokenizer = engine.tokenizer_manager.tokenizer
        processor = AutoProcessor.from_pretrained(args.model)
    else:
        print(f"[INFO] Using OpenAI-style backend: {args.api_base}  model={args.model}")

    # Async generation function(s)
    async def gen_chat_local(ids_or_prompt, image_data=None, val: bool = False):
        image_data = [process_image(img, max_pixels=args.max_pixels, min_pixels=args.min_pixels)
                      for img in (image_data or [])]
        sampling_params = {
            "temperature": args.temperature,
            "max_new_tokens": args.max_new_tokens,
            "skip_special_tokens": args.skip_special_tokens,
            "no_stop_trim": args.no_stop_trim,
            "stop": args.stop_sequences,
        }
        while True:
            try:
                ret = await engine.async_generate(
                    prompt=ids_or_prompt,
                    sampling_params=sampling_params,
                    return_logprob=True,
                    image_data=image_data,
                )
                break
            except asyncio.CancelledError:
                print("[WARN] generation cancelled, retrying...")
        return ret["text"], ret["meta_info"]["output_token_logprobs"]

    async def gen_chat_openai(messages, image_data=None, val: bool = False):
        text = await _openai_style_generate(
            api_base=args.api_base,
            api_key=args.api_key,
            model=args.model,
            messages=messages,
        )
        return text, None

    # Concurrency control
    sem = Semaphore(args.concurrency)
    name = args.task_name[0]
    index_start, index_end = map(int, args.range.split(','))
    max_turns = args.max_turns
    max_length = args.max_length
    base_url = args.controller
    max_response_length = args.max_response_length

    async def worker(task_index, run_number):
        async with sem:
            turns = await openai_chat_agent_loop(
                start_args={"index": task_index, "name": name, "url": base_url},
                start_fn=openai_chat_start,
                gen_fn=gen_chat_local if args.inference_backend == "sgl" else gen_chat_openai,
                obs_fn=openai_chat_obs,
                end_fn=openai_chat_end,
                max_turns=max_turns,
                max_length=max_length,
                max_response_length=max_response_length,
                tokenizer=tokenizer,
                processor=processor,
                inference_backend=args.inference_backend,
                stop_sequences=args.stop_sequences,
            )
            sid = turns[-1].get("sid") if len(turns) > 0 else None
            reward = turns[-1].get("reward", 0) if len(turns) > 0 else 0

            # Write results back to DataFrame
            idx = df[(df['model'] == args.model) &
                     (df['task_index'] == task_index) &
                     (df['run_number'] == run_number)].index
            if len(idx):
                df.at[idx[0], 'result'] = reward
                df.at[idx[0], 'timestamp'] = pd.Timestamp.utcnow()
                df.at[idx[0], 'sid'] = sid
            else:
                df.loc[len(df)] = [args.model, task_index, run_number, reward, pd.Timestamp.utcnow(), sid]
            df.sort_values(by=['model', 'task_index', 'run_number'], inplace=True)
            df.to_json(output_file, orient='records', lines=True, index=False)

    tasks = [
        worker(i, r)
        for r in range(args.runs)
        for i in range(index_start, index_end)
        if (i, r) not in completed_runs
    ]
    if tasks:
        asyncio.get_event_loop().run_until_complete(tqdm_asyncio.gather(*tasks, position=0))
    else:
        print("[INFO] Nothing to run (all completed).")

    # Calculate summary metrics
    df = pd.read_json(output_file, lines=True)
    df = df[df['result'] != "error"]
    valid = len(df)
    avg = float(df["result"].mean()) if valid else 0.0
    by_run = df.groupby(["run_number"])["result"].mean() if valid else pd.Series(dtype=float)
    std = float(by_run.std()) if len(by_run) > 1 else 0.0
    bon = float(df.groupby(["task_index"])["result"].max().mean()) if valid else 0.0

    print(f"[METRICS] Valid: {valid}  Avg: {avg*100:.2f} ± {std*100:.2f} | Best of n: {bon*100:.2f}")

    if engine is not None:
        engine.release_memory_occupation()

    return {
        "valid": valid,
        "avg": avg,
        "std": std,
        "best_of_n": bon,
        "run_results": by_run.tolist() if len(by_run) else [],
        "output_file": str(output_file),
    }

# ===================== CLI Entry Point ===================== #

def main():
    parser = argparse.ArgumentParser(
        description="Single-model evaluation runner with inline agent/HTTP logic. "
                    "Supports sgl (local) and openai-style inference backends."
    )
    # Required core args
    parser.add_argument("-m", "--model", type=str, required=True,
                        help="Model path (sgl) or model name (openai-style).")
    parser.add_argument("-o", "--output-dir", type=str, required=True,
                        help="Directory to store outputs (jsonl and final json).")
    parser.add_argument("--store-name", type=str, default="test",
                        help="Base name for output files (no extension).")

    # Controller & execution
    parser.add_argument("-c", "--controller", type=str, default="http://localhost:5020/api",
                        help="Controller base URL for /start_sample, /interact, /cancel.")
    parser.add_argument("-j", "--concurrency", type=int, default=1,
                        help="Number of concurrent tasks.")
    parser.add_argument("-n", "--runs", type=int, default=5,
                        help="Repeated runs per task index.")
    parser.add_argument("-f", "--output-file", type=str, default=None,
                        help="Custom jsonl filename for per-run records.")
    parser.add_argument("-r", "--range", type=str, required=True,
                        help="Task index range 'start,end' (end exclusive), e.g. '0,100'.")
    parser.add_argument("-i", "--index", type=str, required=False,
                        help="Reserved; unused.")

    parser.add_argument("task_name", type=str, nargs=1,
                        help="Task suite name passed to the controller.")

    # Generation & image processing params
    parser.add_argument("-t", "--temperature", type=float, default=0.0,
                        help="Sampling temperature.")
    parser.add_argument("--max-new-tokens", type=int, default=4096,
                        help="Max new/completion tokens.")
    parser.add_argument("--skip-special-tokens", action=BooleanOptionalAction, default=False,
                        help="Remove special tokens (sgl only).")
    parser.add_argument("--no-stop-trim", action=BooleanOptionalAction, default=True,
                        help="Keep stop sequences (sgl only).")
    parser.add_argument("--stop-sequences", nargs="*", default=["<|user|>", "<|observation|>", "</answer>"],
                        help="Stop sequences.")

    parser.add_argument("--max-pixels", type=int, default=500000,
                        help="Max image pixels (vision).")
    parser.add_argument("--min-pixels", type=int, default=65536,
                        help="Min ensured image pixels (vision).")

    # Conversation/loop control
    parser.add_argument("--max-turns", type=int, default=50,
                        help="Max controller turns.")
    parser.add_argument("--max-length", type=int, default=32768,
                        help="Max prompt token length (sgl only).")
    parser.add_argument("--max-response-length", type=int, default=4096,
                        help="Max tokens per response (sgl only).")

    # Inference backend switch
    parser.add_argument("--inference-backend", type=str, choices=["sgl", "openai"], default="sgl",
                        help="Choose 'sgl' (local engine) or 'openai' (OpenAI-style API).")
    parser.add_argument("--api-base", type=str, default=os.environ.get("OPENAI_API_BASE", ""),
                        help="OpenAI-style Chat Completions endpoint.")
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENAI_API_KEY", ""),
                        help="API key for OpenAI-style backend.")

    args = parser.parse_args()

    try:
        metrics = run_benchmark(args)
        succeed = True
    except Exception as e:
        print(f"[ERROR] Evaluation process exception: {e}", file=sys.stderr)
        succeed = False
        metrics = None
        raise
    finally:
        out_dir = Path(args.output_dir).expanduser().resolve()
        write_final_result(out_dir, args.store_name, succeed, metrics)

if __name__ == "__main__":
    main()
