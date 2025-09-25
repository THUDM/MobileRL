import asyncio
import copy
import logging
import math
import os
import weakref
from functools import cache
from tempfile import TemporaryDirectory
from typing import List, Optional

import android_lab.evaluation.android_world_utils
import android_lab.evaluation.auto_test
from agentrl.worker.environment import create_controller
from agentrl.worker.task import Task, Session
from agentrl.worker.trace_store import TraceStore
from agentrl.worker.typings import RewardHistoryItem, SampleIndex, SampleStatus, TaskSampleExecutionResult
from android_lab.evaluation.android_world_utils import AndroidWorld_AutoTest, initialize_android_world_suite, split_dict
from android_lab.evaluation.configs import TaskConfig

from .environment import AndroidWorldEnvironmentDelegation
from ..agent import AgentRLAgent
from ..instance import FrameworkProvidedInstance


def create_suite_list(n_task_combinations, random, task_id=None):
    suite_list = []
    for _ in range(n_task_combinations):
        if random:
            suite = initialize_android_world_suite(n_task_combinations=1, seed=None, task_template=task_id)
        else:
            suite = initialize_android_world_suite(n_task_combinations=1, seed=30, task_template=task_id)
        suite_list.extend(split_dict(suite, 1))
    return suite_list


class AndroidWorldTask(Task):

    def __init__(self,
                 android_lab_config: dict,
                 traces_dir: Optional[str] = None,
                 port_allocator: str = 'http://localhost:5030',
                 image_max_pixels: Optional[int] = None,
                 env_driver: str = 'docker',
                 env_options: Optional[dict] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.trace_store = TraceStore(os.path.join(traces_dir, self.name)) if traces_dir else None

        self.android_lab_config = android_lab_config
        assert self.android_lab_config, 'android_lab_config is not set'

        self.task_list = create_suite_list(n_task_combinations=1, random=False)
        self.data_size = len(self.task_list)

        self.image_max_pixels = image_max_pixels

        self.env_delegation = AndroidWorldEnvironmentDelegation(port_allocator)
        self.env_controller = create_controller(env_driver, self.env_delegation, **env_options)
        FrameworkProvidedInstance.controller = self.env_controller
        android_lab.evaluation.android_world_utils.Instance_AndroidWorld_docker = FrameworkProvidedInstance  # monkey-patch
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
            trace_writer = self.trace_store.new_trace(list(task_suite.keys())[0], session.id)
            single_config.save_dir = str(trace_writer.get_dir())
        else:
            tmp_dir = TemporaryDirectory(prefix='log')
            single_config.save_dir = tmp_dir.name

        task_config = copy.deepcopy(single_config)
        auto_class = autotask_class(task_config)
        agent = AgentRLAgent(session, image_max_pixels=self.image_max_pixels)
        android_world_class = AndroidWorld_AutoTest(task_config, auto_class, agent)

        def renew_session():
            instance = getattr(android_world_class, 'instance', None)
            if instance:
                session_id = getattr(instance, 'session_id', None)
                if session_id:
                    asyncio.run_coroutine_threadsafe(
                        self.env_controller.renew_session(session_id),
                        session.loop
                    )  # ignore result
        agent.renew_callback = renew_session

        try:
            results = android_world_class.run_task(task_suite)
        except Exception as e:
            self.logger.exception('Error during task execution')
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR, result={
                "result": False,
                "error": e
            })
        finally:
            android_world_class.clean_docker()

        self.logger.info(f'finish results: {results}')

        if results is None:
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR, result={
                "result": False,
                "error": "results is None"
            })

        result = results[0]
        try:
            if math.isnan(result["is_successful"]):
                result["is_successful"] = 0.0
        except:
            result["is_successful"] = 0.0
        for key, value in result.items():
            try:
                if isinstance(value, str):
                    continue
                elif math.isnan(value):
                    result[key] = None
            except:
                result[key] = None

        reward_history = RewardHistoryItem(reward=result["is_successful"], score=result["is_successful"])
        session.inject(reward_history)

        if "aux_data" in result and result["aux_data"] is not None and result["aux_data"] in ["ERROR", "MAX_ROUNDS"]:
            if result["aux_data"].get("finish_reason") == "ERROR":
                return TaskSampleExecutionResult(status=SampleStatus.AGENT_INVALID_ACTION, result=result)
            if result["aux_data"].get("finish_reason") == "MAX_ROUNDS":
                return TaskSampleExecutionResult(status=SampleStatus.TASK_LIMIT_REACHED, result=result)
            return TaskSampleExecutionResult(status=SampleStatus.UNKNOWN, result=result)
        return TaskSampleExecutionResult(status=SampleStatus.COMPLETED, result=result)
