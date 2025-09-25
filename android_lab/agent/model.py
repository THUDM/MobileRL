from typing import List, Dict, Any
import json
import backoff
import requests
#from openai import OpenAI

from android_lab.agent.utils import *
from android_lab.templates.android_screenshot_template import *


def handle_giveup(details):
    print(
        "Backing off afters {tries} tries calling fzunction {target} with args {args} and kwargs {kwargs}"
        .format(**details))


def handle_backoff(details):
    args = str(details['args'])[:1000]
    print(f"Backing off {details['wait']:0.1f} seconds after {details['tries']} tries "
          f"calling function {details['target'].__name__} with args {args} and kwargs ")

    import traceback
    print(traceback.format_exc())


class Agent:
    name: str

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        raise NotImplementedError

    def prompt_to_message(self, prompt, images):
        raise NotImplementedError

class RLAgent(Agent):
    def __init__(
            self,
            api_base: str = '',
            api_key: str = '',
            model_name: str = '',
            max_new_tokens: int = 256,
            temperature: float = 0,
            top_p: float = 0.95,
            **kwargs
    ) -> None:
        self.api_base = api_base
        self.api_key = api_key
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.kwargs = kwargs
        self.name = "RLAgent"

    @backoff.on_exception(
        backoff.expo, Exception,
        on_backoff=handle_backoff,
        on_giveup=handle_giveup,
        max_tries=10
    )
    def act(self, messages: List[Dict[str, Any]]) -> str:
        messages = self.format_messages(messages)
        return self._act(messages)
    
    def _act(self, messages: List[Dict[str, Any]]) -> str:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'{self.api_key}'
        }
        
        data = {
            'model': self.model_name,
            'messages': messages,
            'seed': 34,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_new_tokens,
            'stream': False,
        }
        response = requests.post(
            self.api_base,
            headers=headers,
            json=data,
            timeout=300  # Optional timeout
        )
        try:
            response.raise_for_status()
            resp_json = response.json()
            return True, resp_json["choices"][0]["message"]["content"]
        except Exception as e:
            print(response.text)
            return False, response.text
    
    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return messages

    def format_prompt(self, messages: List[Dict[str, Any]]) -> str:
        #messages = self.format_messages(messages)
        for message in messages:
            if 'current_app' in message:
                current_app = message.pop("current_app")
            if isinstance(message["content"], list):
                for i, content in enumerate(message["content"]):
                    if "text" in content:
                        message["content"] = "<image>" + message["content"][i]["text"]

        return messages
                    
    def prompt_to_message(self, prompt: str, images: List[str], xml: str=None) -> Dict[str, Any]:
        content = []
        for img in images:
            base64_img = image_to_base64(img)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}"
                }
            })
            
        final_text = prompt + (f"\n{xml}" if xml is not None else "")
        content.append({
            "type": "text",
            "text": final_text
        })
        
        message = {
            "role": "user",
            "content": content
        }
        return message

def format_history(history):
    formatted_history = []
    for msg in history:
        content = msg.get("content")
        if isinstance(content, str):
            formatted_history.append(msg)
        else:
            # ChatML multimodal message
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url" and isinstance(part["image_url"], dict):
                    new_parts.append({"type": "image_url","image_url":part["image_url"]["url"][:100]})
                else:
                    new_parts.append(part)
            formatted_history.append({"role": msg["role"], "content": new_parts})
    return formatted_history

def format_history_print(history):
    """保持与 openai_chat_agent_loop 中相同的格式化规则。"""
    formatted_history = []
    for msg in history:
        content = msg.get("content")
        if isinstance(content, str):
            formatted_history.append(msg)
        else:
            # ChatML multimodal message
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url" and isinstance(part["image_url"], dict):
                    new_parts.append({"type": "image_url","image_url":part["image_url"]["url"][:100]})
                else:
                    new_parts.append(part)
            formatted_history.append({"role": msg["role"], "content": new_parts})
    return formatted_history
