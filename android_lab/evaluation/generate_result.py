import concurrent.futures
import datetime
import os
import shutil
from collections import defaultdict
from glob import glob
from os.path import join, isdir, isfile, relpath
from typing import List, Dict, Optional

import jsonlines
import pandas as pd

from android_lab.evaluation.configs import AppConfig
from android_lab.evaluation.task import Evaluation_Task


from typing import Optional, Dict


class JudgeConfig:
    judge_model: Optional[str] = "glm4"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    input_folder: str = None
    output_folder: Optional[str] = None 
    output_excel: str = "output.xlsx"
    tt: int = 138

    def __init__(self, **kwargs):
        for key, value in self.__class__.__dict__.items():
            if not key.startswith("__") and not callable(value):
                setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)
        assert self.input_folder is not None, "input_folder is required"
        if self.output_folder is None:
            self.output_folder = self.input_folder

    def add_config(self, config: Dict):
        new_config = self.__dict__.copy()
        for key, value in config.items():
            new_config[key] = value
        return JudgeConfig(**new_config)


def find_all_traces_files(traces_path_fold) -> Dict[str, Dict[str, str]]:
    traces_path = os.listdir(traces_path_fold)
    traces = {}
    for trace in traces_path:
        if 'results' in trace:
            continue
        app_name = trace.split('_')[0]
        app_id = trace.split('_')[1]
        task_id = f"{app_name}_{app_id}"
        trace_root = os.path.join(traces_path_fold, trace)
        trace_file = os.path.join(trace_root, "traces", "trace.jsonl")
        xml_path = os.path.join(trace_root, "xml")
        trace_item = {
            "task_id": task_id,
            "trace_file": trace_file,
            "xml_path": xml_path,
            "trace_root": trace_root
        }
        traces[task_id] = trace_item
    return traces


def evaluate_all_tasks(tasks: List[Evaluation_Task]):
    for task in tasks:
        try:
            task.evaluate()
            del task
        except Exception:
            pass


def evaluate_input_dir(input_dir, task_files, create_time, config: JudgeConfig):
    test_name = input_dir.split('/')[-1]
    output_root_dir = os.path.join(config.output_folder, "results")
    if not os.path.exists(output_root_dir):
        os.makedirs(output_root_dir)
    traces = find_all_traces_files(input_dir)
    tasks = []
    print("> Loading task configs")
    for app_task_config_path in task_files:
        app_config = AppConfig(app_task_config_path, output_dir=output_root_dir)
        app_task = Evaluation_Task(app_config, traces, config, detail=True)
        print(f"    Evaluation_Task '{app_task.name}' loaded from config {app_task_config_path}")
        tasks.append(app_task)
    print(f"> Successfully load {len(tasks)} task{'s' if len(tasks) > 1 else ''}")
    evaluate_all_tasks(tasks)
  

def output(config: JudgeConfig):
    output_df = pd.DataFrame()
    base_folder = config.output_folder
    outputs = os.listdir(base_folder)

    for output in outputs:
        output_folder = os.path.join(base_folder, output)
        agent_name = output.split("_202")[0]
        if not os.path.exists(os.path.join(output_folder, "total.jsonl")):
            continue
        with jsonlines.open(os.path.join(output_folder, "total.jsonl")) as f:
            dict = defaultdict(list)
            tt = 0
            for line in f:
                for key, value in line.items():
                    if key == "App":
                        dict["App"].append(1)
                    elif key == "Total":
                        dict[key].append(value)
                        tt += value
                    elif "Sum_" in key or key == "Complete_Correct":
                        dict[key].append(value)
            tt_correct = sum(dict["Complete_Correct"])
            output_dict = {"agent_name": agent_name}
            for key, value in dict.items():
                if key == "App":
                    output_dict[key] = len(value)
                elif key == "Total":
                    output_dict[key] = sum(value)
                elif key == "Sum_RRR":
                    output_dict[key] = 0 if tt_correct == 0 else 100 * sum(value) / tt_correct
                elif key == "Complete_Correct" or "Sum_" in key:
                    output_dict[key] = 100 * sum(value) / config.tt
            output_dict["Acc"] = tt_correct / tt
            output_dict["correct"] = tt_correct
            output_df = output_df._append(output_dict, ignore_index=True)
    return output_df
    
def _judge_androidlab(config: JudgeConfig, task_files: List[str]):
    assert config.judge_model in ["glm4", "gpt-4o-2024-05-13"], "We only support glm4 or gpt-4o for judge model"

    task_yamls = os.listdir('android_lab/evaluation/config')
    task_yamls = ["android_lab/evaluation/config/" + i for i in task_yamls if i.endswith(".yaml")]

    create_time = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    input_dir = config.input_folder

    if not os.path.exists(config.output_folder):
        os.makedirs(config.output_folder)

    if os.path.exists(os.path.join(config.output_folder, "results")):
        shutil.rmtree(os.path.join(config.output_folder, "results"))
    os.makedirs(os.path.join(config.output_folder, "results"))


    try:
        evaluate_input_dir(input_dir, task_files, create_time, config)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f'Generated an exception: {exc}')
    output_df_main_result = output(config)
    print(f"model name: {input_dir.split('/')[-1]}\nSR: {output_df_main_result['Complete_Correct'].iloc[0]}\nSSR: {output_df_main_result['Sum_Partial_Acc'].iloc[0]}\nRRR: {output_df_main_result['Sum_RRR'].iloc[0]}\nROR: {output_df_main_result['Sum_reasonable_operation_ratio'].iloc[0]}")
    
def judge_androidlab(config_dict, task_files):
    config = JudgeConfig(**config_dict)
    _judge_androidlab(config, task_files)

if __name__ == "__main__":
    config = JudgeConfig(judge_model="glm4", api_key="your_api_key", api_base="")
    main(config)
