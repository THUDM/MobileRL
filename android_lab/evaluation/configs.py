import importlib
import os
from dataclasses import dataclass
from typing import Optional

import yaml


class AppConfig:
    def __init__(self, file_path, output_dir=None):
        self.file_path = file_path
        self.data = None
        self.metrics = {}
        self.task_name = {}
        self.metrics_type = {}
        self.command_per_step = {}
        self.output_dir = output_dir
        self.load_params()

    def load_params(self):
        try:
            with open(self.file_path, 'r') as file:
                self.data = yaml.safe_load(file)
                self.APP = self.data.get('APP')
                self.package = self.data.get('package')
                if 'tasks' in self.data:
                    for task in self.data['tasks']:
                        func_name = task.get('metric_func')
                        task_id = task.get('task_id')
                        metric_type = task.get('metric_type')
                        if func_name:
                            app_module_name = func_name.split('.')[-1]
                            module = importlib.import_module(f'.tasks.{app_module_name}', __spec__.parent)
                            if hasattr(module, 'function_map') and task_id in module.function_map:
                                task['metric_func'] = module.function_map[task_id]
                                self.metrics[task_id] = task['metric_func']
                                self.metrics_type[task_id] = metric_type
                                self.task_name[task_id] = task.get('task')
                                if task.get("adb_query"):
                                    self.command_per_step[task_id] = task.get("adb_query")
                            else:
                                print(f"No valid function mapped for {task_id}")
                                task['metric_func'] = None
        except FileNotFoundError:
            print("Error: The file was not found.")
        except yaml.YAMLError as exc:
            print(f"Error in YAML file formatting: {exc}")
        except Exception as e:
            import traceback
            print(traceback.print_exc())

    def get_tasks(self):
        if self.data:
            return self.data.get('tasks', [])
        return []

    def get_metrics(self):
        return self.metrics


class AppConfig_Sample:
    def __init__(self, file_path, output_dir=None):
        self.file_path = file_path
        self.data = None
        self.task_name = {}
        self.output_dir = output_dir
        self.metrics = {}
        self.load_params()

    def load_params(self):
        try:
            with open(self.file_path, 'r') as file:
                self.data = yaml.safe_load(file)
                self.APP = self.data.get('APP')
                self.package = self.data.get('package')
                if 'tasks' in self.data:
                    for task in self.data['tasks']:
                        task_id = task.get('task_id')
                        self.metrics[task_id] = 'reward_model'
                        self.task_name[task_id] = task.get('task')
        except FileNotFoundError:
            print("Error: The file was not found.")
        except yaml.YAMLError as exc:
            print(f"Error in YAML file formatting: {exc}")
        except Exception as e:
            import traceback
            print(traceback.print_exc())

    def get_tasks(self):
        if self.data:
            return self.data.get('tasks', [])
        return []

    def get_metrics(self):
        return self.metrics

@dataclass
class TaskConfig:
    save_dir: str
    max_rounds: int
    mode: Optional[float] = None
    request_interval: Optional[float] = None
    task_id: Optional[str] = None
    avd_name: Optional[str] = "Pixel_7_Pro_API_33"
    avd_log_dir: Optional[str] = None
    avd_base: Optional[str] = None
    adb_path: Optional[str] = None
    android_sdk_path: Optional[str] = None
    is_relative_bbox: Optional[bool] = False
    docker: Optional[bool] = False
    docker_args: Optional[dict] = None
    docker_image_name: Optional[str] = None
    sample: Optional[bool] = False
    show_avd: Optional[bool] = False
    version: Optional[str] = None
    use_ocr: Optional[bool] = False
    tap_desc: Optional[bool] = False
    ablation: Optional[str] = None
    device_start_port: Optional[int] = 5558
    grpc_start_port: Optional[int] = 8554
    android_world: Optional[bool] = False
    reasoning_agent: Optional[bool] = True
    picture_round: Optional[int] = 2
    with_xml: Optional[bool] = True
    redis_config_port: Optional[int] = 6379
    redis_port_start: Optional[int] = 26000
    redis_port_end: Optional[int] = 30000
    system_prompt: Optional[str] = None
    aw_launch: Optional[str] = None

    def subdir_config(self, subdir: str):
        new_config = self.__dict__.copy()
        new_config["save_dir"] = os.path.join(self.save_dir, subdir)
        # new_config["task_id"] = task_id
        return TaskConfig(**new_config)

    def add_config(self, config):
        new_config = self.__dict__.copy()
        for key, values in config.items():
            new_config[key] = values
        return TaskConfig(**new_config)
