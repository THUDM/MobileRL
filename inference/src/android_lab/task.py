import asyncio
import copy
import logging
import os
import weakref
from functools import cache
from glob import glob
from os.path import join, dirname, realpath
from tempfile import TemporaryDirectory
from typing import List, Optional

import android_lab.evaluation
import android_lab.evaluation.android_world_utils
import android_lab.evaluation.auto_test
from agentrl.worker.environment import create_controller
from agentrl.worker.task import Task, Session
from agentrl.worker.trace_store import TraceStore
from agentrl.worker.typings import RewardHistoryItem, SampleIndex, SampleStatus, TaskSampleExecutionResult
from android_lab.evaluation.configs import TaskConfig, AppConfig, AppConfig_Sample
from android_lab.evaluation.task import Evaluation_Task

from .environment import AndroidLabEnvironmentDelegation
from ..agent import AgentRLAgent
from ..instance import FrameworkProvidedInstance


def create_suite_list_android_lab(yaml_path: str, aug=False) -> List[dict]:
    evaluation_path = realpath(join(dirname(android_lab.evaluation.__file__), yaml_path))
    task_files = [path for path in glob(join(evaluation_path, '**/*.yaml'), recursive=True)]
    logging.info(f'android lab {task_files=}')

    all_task_start_info = []
    for app_task_config_path in task_files:
        if yaml_path == 'config':
            app_config = AppConfig(app_task_config_path)
        else:
            app_config = AppConfig_Sample(app_task_config_path)

        for task_id in app_config.task_name:
            task_instruction = app_config.task_name[task_id].strip()
            app = app_config.APP
            package = app_config.package

            if hasattr(app_config, 'command_per_step') and isinstance(app_config.command_per_step, dict):
                command_per_step = app_config.command_per_step.get(task_id, None)
            else:
                command_per_step = None

            task_instruction = f"You should use {app} to complete the following task: {task_instruction}"
            all_task_start_info.append({
                "config": app_config,
                "task_id": task_id,
                "task_instruction": task_instruction,
                "package": package,
                "command_per_step": command_per_step,
                "app": app,
                'env_type': 'android_lab_eval' if aug else ''
            })

    return sorted(all_task_start_info, key=lambda x: x['task_id'])


class JudgeArgs:

    def __init__(self, **kwargs):
        self.judge_model = kwargs.get("judge_model", "glm4")
        self.api_base = kwargs.get("api_base", "")
        self.api_key = kwargs.get("api_key", "")
        self.api_gateway_key = kwargs.get("api_gateway_key", "")
        self.api_gateway_base_url = kwargs.get("api_gateway_base_url", "")
        self.qwen_vl_base_url = kwargs.get("qwen_vl_base_url", "")
        self.proxy_url = kwargs.get("proxy_url", "")

class AndroidLabTask(Task):

    def __init__(self,
                 android_lab_config: dict,
                 yaml_path: str,
                 traces_dir: Optional[str] = None,
                 aug_path: Optional[str] = None,
                 data_size: Optional[int] = None,
                 judge_args: Optional[dict] = None,
                 image_max_pixels: Optional[int] = None,
                 env_type: str = 'android_lab_eval',
                 env_driver: str = 'docker',
                 env_options: Optional[dict] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.trace_store = TraceStore(join(traces_dir, self.name)) if traces_dir else None

        self.android_lab_config = android_lab_config
        assert self.android_lab_config, 'android_lab_config is not set'

        self.data_size = data_size
        assert self.data_size, 'data_size is not set'
        self.task_list = create_suite_list_android_lab(yaml_path)
        self.aug_task_list = create_suite_list_android_lab(aug_path, aug=True) if aug_path else []
        self.task_list = self.task_list + self.aug_task_list

        assert self.task_list, 'task_list is empty'
        self.judge_args = JudgeArgs(**(judge_args or {}))

        self.image_max_pixels = image_max_pixels

        self.env_type = env_type
        self.env_delegation = AndroidLabEnvironmentDelegation()
        self.env_controller = create_controller(env_driver, self.env_delegation, **env_options)
        FrameworkProvidedInstance.controller = self.env_controller
        self.env_controller_background_task = None

    @cache
    def get_indices(self) -> List[SampleIndex]:
        return list(range(len(self.task_list)))

    async def start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        self.env_controller.loop = asyncio.get_running_loop()
        if not self.env_controller_background_task:
            self.env_controller_background_task = asyncio.create_task(self.env_controller.background_task())
            weakref.finalize(self, self.env_controller_background_task.cancel)

        try:
            return await super().start_sample(index, session)
        except Exception as e:
            self.logger.exception('Error during task execution')
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR, result={
                "result": False,
                "error": e
            })

    def sync_start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        task_suite = copy.deepcopy(self.task_list[index])

        task_config = self.android_lab_config["task"]
        single_config = TaskConfig(**task_config["args"])

        autotask_class = getattr(android_lab.evaluation.auto_test, task_config["class"])
        if autotask_class is None:
            raise AttributeError(f"Class {autotask_class} not found. Please check the class name in the config file.")

        eval_config = self.android_lab_config["eval"]
        single_config = single_config.add_config(eval_config)

        if self.trace_store:
            trace_writer = self.trace_store.new_trace(task_suite['task_id'], session.id)
            single_config.save_dir = str(trace_writer.get_dir())
        else:
            tmp_dir = TemporaryDirectory(prefix='log')
            single_config.save_dir = tmp_dir.name

        task_config = copy.deepcopy(single_config)
        auto_class = autotask_class(task_config)

        agent = AgentRLAgent(session, image_max_pixels=self.image_max_pixels)
        task_suite['agent'] = agent
        env_type = task_suite['env_type'] if task_suite['env_type'] != '' else self.env_type

        instance = FrameworkProvidedInstance(task_config, env_type=env_type)
        def renew_session():
            if instance.session_id:
                asyncio.run_coroutine_threadsafe(
                    self.env_controller.renew_session(instance.session_id),
                    session.loop
                )  # ignore result
        agent.renew_callback = renew_session

        try:
            auto_class.run_task(task_suite, instance)

            # input_dir = task_config.save_dir
            # traces = find_all_traces_files(input_dir)
            traces = {
                task_suite["task_id"]: {
                    'task_id': task_suite["task_id"],
                    'trace_file': os.path.join(auto_class.config.task_dir, 'traces', 'trace.jsonl'),
                    'xml_path': os.path.join(auto_class.config.task_dir, 'xml'),
                    'trace_root': auto_class.config.task_dir
                }
            }
            args = self.judge_args
            app_task = Evaluation_Task(task_suite['config'], traces, args, detail=True)
            results = app_task.evaluate_result(task_suite["task_id"], self.name)
        except Exception as e:
            self.logger.exception('Error during task execution')
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR, result={
                "result": False,
                "error": e
            })
        finally:
            instance.stop_single_task()

        self.logger.info(f'finish results: {results}')

        if results is None:
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR, result={
                "result": False,
                "error": "results is None"
            })

        result = results
        if result.get('norm_amount') and result.get('accepted_amount'):
            result['complete'] = result['accepted_amount'] / result['norm_amount']
        reward_history = RewardHistoryItem(reward=result["complete"], score=result["complete"])
        session.inject(reward_history)

        if "aux_data" in result and result["aux_data"] is not None and result["aux_data"] in ["ERROR", "MAX_ROUNDS"]:
            if result["aux_data"].get("finish_reason") == "ERROR":
                return TaskSampleExecutionResult(status=SampleStatus.AGENT_INVALID_ACTION, result=result)
            if result["aux_data"].get("finish_reason") == "MAX_ROUNDS":
                return TaskSampleExecutionResult(status=SampleStatus.TASK_LIMIT_REACHED, result=result)
            return TaskSampleExecutionResult(status=SampleStatus.UNKNOWN, result=result)
        return TaskSampleExecutionResult(status=SampleStatus.COMPLETED, result=result)
