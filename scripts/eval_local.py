import os
os.environ['TMPDIR'] = os.path.join(os.getcwd(), 'tmp')
import jsonlines
import argparse
import shutil
import yaml
from typing import List
from glob import glob
from os.path import join, relpath


from android_lab.agent import get_agent
from android_lab.evaluation.auto_test import *
from android_lab.evaluation.parallel import parallel_worker, parallel_worker_android_world
from android_lab.evaluation.configs import AppConfig, TaskConfig
from android_lab.evaluation.android_world_utils import (
    AndroidWorld_AutoTest,
    initialize_android_world_suite,
    print_android_world_results,
    split_dict,
)



def find_all_task_files(all_task_config_path) -> List[str]:
    tasks = []
    for task in all_task_config_path:
        if os.path.isdir(task):
            tasks += [relpath(path, ".") for path in glob(join(task, "**/*.yaml"), recursive=True)]
        elif os.path.isfile(task):
            tasks.append(task)
        else:
            print(f"'{task}' is not a valid file or directory, ignored.")
    return tasks


if __name__ == '__main__':
    if not os.path.exists(os.environ['TMPDIR']):
        os.makedirs(os.environ['TMPDIR'])

    task_yamls = os.listdir('android_lab/evaluation/config')
    task_yamls = ["android_lab/evaluation/config/" + i for i in task_yamls if i.endswith(".yaml")]

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-n", "--name", default="test", type=str)
    arg_parser.add_argument("-d", "--dataset", default="android_lab", type=str)  # 控制分支
    arg_parser.add_argument("-c", "--config", required=True, type=str)
    arg_parser.add_argument("--task_config", nargs="+", default=task_yamls, help="All task config(s) to load")
    arg_parser.add_argument("--task_id", nargs="+", default=None)
    arg_parser.add_argument("--debug", action="store_true", default=False)
    arg_parser.add_argument("--app", nargs="+", default=None)
    arg_parser.add_argument("-p", "--parallel", default=1, type=int)

    # Android World
    arg_parser.add_argument("--n_task_combinations", default=1, type=int)
    arg_parser.add_argument("--random", action="store_true", default=False)
    arg_parser.add_argument("--delete_exist", action="store_true", default=False)
    arg_parser.add_argument("--ir_only", action="store_true", default=False)
    arg_parser.add_argument("--parallel_start_num", default=0, type=int)

    args = arg_parser.parse_args()

    with open(args.config, "r") as file:
        yaml_data = yaml.safe_load(file)

    agent_config = yaml_data["agent"]
    task_config = yaml_data["task"]
    eval_config = yaml_data["eval"]

    autotask_class = task_config.get("class", "ScreenshotMobileTask_AutoTest")

    single_config = TaskConfig(**task_config["args"])
    single_config = single_config.add_config(eval_config)
    if "True" == agent_config.get("relative_bbox"):
        single_config.is_relative_bbox = True
    agent = get_agent(agent_config["name"], **agent_config["args"])


    if args.dataset == "android_lab":
        task_files = find_all_task_files(args.task_config)
        

        if os.path.exists(os.path.join(single_config.save_dir, args.name)):
            already_run = os.listdir(os.path.join(single_config.save_dir, args.name))
            already_run = [i.split("_")[0] + "_" + i.split("_")[1] for i in already_run if 'results' not in i]
            if "results" in already_run:
                shutil.rmtree(os.path.join(single_config.save_dir, args.name, "results"))
        else:
            already_run = []
            
        

        all_task_start_info = []
        for app_task_config_path in task_files:
            app_config = AppConfig(app_task_config_path)
            if args.task_id is None:
                task_ids = list(app_config.task_name.keys())
            else:
                task_ids = args.task_id

            for task_id in task_ids:
                if task_id in already_run:
                    print(f"Task {task_id} already run, skipping")
                    continue
                if task_id not in app_config.task_name:
                    continue

                task_instruction = app_config.task_name[task_id].strip()
                app = app_config.APP
                if args.app is not None:
                    print(app, args.app)
                    if app not in args.app:
                        continue
                package = app_config.package
                command_per_step = app_config.command_per_step.get(task_id, None)

                task_instruction = f"You should use {app} to complete the following task: {task_instruction}"
                all_task_start_info.append({
                    "agent": agent,
                    "task_id": task_id,
                    "task_instruction": task_instruction,
                    "package": package,
                    "command_per_step": command_per_step,
                    "app": app
                })

        class_ = globals().get(autotask_class)
        if class_ is None:
            raise AttributeError(f"Class {autotask_class} not found. Please check the class name in the config file.")
        
        if args.parallel == 1:
            Auto_Test = class_(single_config.subdir_config(args.name))
            Auto_Test.run_serial(all_task_start_info)
        else:
            parallel_worker(class_, single_config.subdir_config(args.name), args.parallel, all_task_start_info)
        
        if "judge" in yaml_data:
            judge_config = yaml_data["judge"]
            input_folder = os.path.join(single_config.save_dir, args.name)
            judge_config["input_folder"] = input_folder
            from android_lab.evaluation.generate_result import judge_androidlab
            judge_androidlab(judge_config, task_files)
    else:
        already_run = []
        if args.n_task_combinations == 1:
            task_path_root = os.path.join(single_config.save_dir, args.name)
            if os.path.exists(task_path_root):
                if not args.delete_exist:
                    already_run = os.listdir(task_path_root)
                    already_run = [i.split("_")[0] for i in already_run]
                else:
                    already_run = []
                    shutil.rmtree(task_path_root)


        if args.random:
            suite = initialize_android_world_suite(
                n_task_combinations=args.n_task_combinations, seed=None, task_template=args.task_id
            )
        else:
            suite = initialize_android_world_suite(
                n_task_combinations=args.n_task_combinations, seed=30, task_template=args.task_id
            )


        if not args.task_id:
            num_delete = 0
            for key in list(suite.keys()):
                if key in already_run:
                    del suite[key]
                    num_delete += 1
                    print(f"Task {key} already run, skipping")
            print(f"Num of tasks already run: {num_delete}")

        suite_list = split_dict(suite, 1)

        class_ = globals().get(autotask_class)
        if class_ is None:
            raise AttributeError(f"Class {autotask_class} not found. Please check the class name in the config file.")

        Auto_Test = class_(single_config.subdir_config(args.name))
        task_path = os.path.join(single_config.save_dir, args.name)
        args.parallel = min(args.parallel, len(suite_list))

        if args.parallel == 1:
            android_world_class = AndroidWorld_AutoTest(single_config.subdir_config(args.name), Auto_Test, agent)
            android_world_class.run_serial(suite_list)
        else:
            results = parallel_worker_android_world(
                args, class_, AndroidWorld_AutoTest, single_config.subdir_config(args.name), agent, args.parallel, suite_list
            )
            print_android_world_results(path=task_path, all_results=results)
