from collections.abc import Sequence
import os
import time
import uuid
import random
import sys
import datetime
import logging
import threading
import subprocess
import jsonlines

from absl import app
from absl import flags
from absl import logging
from android_world import checkpointer as checkpointer_lib
from android_world import registry
from android_world import suite_utils
from android_world.suite_utils import process_episodes
from android_world.agents import base_agent
from android_world.agents import human_agent
from android_world.agents import infer
from android_world.agents import m3a
from android_world.agents import random_agent
from android_world.agents import seeact
from android_world.agents import t3a
from android_world.env import env_launcher
from android_world.env import interface
from android_world.env import adb_utils
from android_world.env import json_action
from android_world.task_evals.task_eval import TaskEval
from android_world.task_evals.information_retrieval.proto_utils import get_expected_answer

from android_lab.evaluation.auto_test import AutoTest, Instance
from android_lab.evaluation.evaluation import *
from android_lab.evaluation.auto_test import find_package
from android_lab.recorder import JSONRecorder
    
import docker
from docker.types import Mount


def split_dict(input_dict, n=1):
    if not isinstance(input_dict, dict) or not isinstance(n, int) or n <= 0:
        raise ValueError("输入参数不合法，input_dict 应为字典，n 应为正整数")

    expanded_items = []
    for key, value in input_dict.items():
        if isinstance(value, list) and len(value) > 1:
            for v in value:
                expanded_items.append((key, [v]))
        else:
            expanded_items.append((key, value if not isinstance(value, list) else [value[0]]))


    return [dict(expanded_items[i:i + n]) for i in range(0, len(expanded_items), n)]

_TASKS = None
_FIXED_TASK_SEED = False
_TASK_RANDOM_SEED = 30
_N_TASK_COMBINATIONS = 1
_EMULATOR_SETUP = False
_SUITE_FAMILY = registry.TaskRegistry.ANDROID_WORLD_FAMILY
# other:registry.TaskRegistry.MINIWOB_FAMILY_SUBSET
  

def android_world_answer(state, env, finish_message):
    action = json_action.JSONAction(**{'action_type':'answer', 'text':finish_message})
    env.execute_action(action)


def print_android_world_results(path = None, all_results = None):
    df = process_episodes(all_results, print_summary = True)
    df.to_excel(os.path.join(path, "results.xlsx"), index=True)
    return df

        
def remove_existing_container(client, name, retries=5):
    for i in range(retries):
        try:
            existing = client.containers.get(name)
            print_with_color(f"Removing existing container: {name}", "yellow")
            existing.remove(force=True)
            return True
        except docker.errors.NotFound:
            return False
        except docker.errors.APIError as e:
            if "removal of container" in str(e):
                print_with_color(f"Removal in progress... retrying ({i+1})", "yellow")
                time.sleep(2)
            else:
                print_with_color(f"Unexpected error during removal: {e}", "red")
                break
    return False


class Instance_AndroidWorld_docker(Instance):
    def __init__(self, config, idx=0, start_idx=0, is_assign_port=False, assign_port=None):
        self.idx_num = idx
        self.start_idx = start_idx
        self.type = "cmd"
        self.config = config
        self.tar_avd_dir = None
        self.tar_ini_file = None
        self.docker_port_local = None
        self.log_stop_event = threading.Event()
        self.log_thread = None
        self.docker_container = None
        self.is_assign_port = is_assign_port
        self.assign_port = assign_port


    def create_task_idx(self):
        unique_id = uuid.uuid4().hex[:8]
        
        if self.is_assign_port:
            device_start_port = self.assign_port
            self.idx = str(self.assign_port)+"_"+str(time.time()) + unique_id
            self.device_port = device_start_port
            self.grpc_port = device_start_port + 2
        else:
            assert self.assign_port is None, "assign_port must be None if is_assign_ports is False"
            self.idx = str(self.idx_num + self.start_idx)+"_"+str(time.time()) + unique_id
            device_start_port = self.config.device_start_port
            idx_num = self.idx_num + self.start_idx
            self.device_port = device_start_port + idx_num * 4
            self.grpc_port = device_start_port + idx_num * 4 + 2
            
  
    def initialize_single_task(self, config=None, log_path="docker_emulator.log"):
        self.create_task_idx()

        client = docker.from_env()

        adbkey_path = os.path.expanduser("~/.android/adbkey")
        with open(adbkey_path, "r") as f:
            adbkey_content = f.read()
        existing = None
        try:
            existing = client.containers.get(f"android_emulator_{self.idx}")
        except docker.errors.NotFound:
            pass

        if existing:
            print_with_color(f"Removing existing container: {existing.name}", "yellow")
            remove_existing_container(client, existing.name)
 
        try:
            tmp_dir = os.environ['TMPDIR'] if os.environ['TMPDIR'] else os.path.join(os.getcwd(), 'tmp')
            container = client.containers.run(
                image=self.config.docker_image_name,
                detach=True,
                network_mode="host",
                environment={
                    "ADBKEY": adbkey_content,
                    "ADB_PORT": str(self.device_port + 1),
                    "GRPC_PORT": str(self.grpc_port),
                },
                devices=["/dev/kvm"],
                name=f"android_emulator_{self.idx}",
                remove=False,
                stdout=True,
                stderr=True,
                volumes={
                    tmp_dir: {'bind': tmp_dir, 'mode': 'rw'}
                }
            )
            
            self.container_id = container.id
            print_with_color(f"Container started with ID: {self.container_id}", "green")
          

        except docker.errors.APIError as e:
            print_with_color(f"Failed to start container: {str(e)}", "red")
            return False

        device = f"emulator-{self.device_port}"

        limit_time = time.time() + 120
        while True:
            bootanim = f"docker exec {self.container_id} /android/sdk/platform-tools/adb -s {device} shell getprop init.svc.bootanim"
            bootanim = execute_adb(bootanim, output=False)
            
            boot_complete = f"docker exec {self.container_id} /android/sdk/platform-tools/adb -s {device} shell getprop sys.boot_completed"
            boot_complete = execute_adb(boot_complete, output=False)

            with open(os.path.join(log_path, "boot_complete.log"), "a") as f:
                f.write(boot_complete + "\n" + bootanim + "\n")
                
            if bootanim == 'stopped' and boot_complete == '1':
                print_with_color("Emulator boot completed", "blue")
                break
            if time.time() > limit_time:
                print_with_color("Emulator boot timeout", "red")
                with open(os.path.join(log_path, "boot_complete.log"), "a") as f:
                    f.write("Emulator boot timeout" + "\n")
                return False
            time.sleep(5)
            
        return device


    def stop_single_task(self):
        print_with_color(f"Stopping Docker Android Emulator {self.idx_num}...", "blue")
        try:
            self.log_stop_event.set()
            if self.log_thread:
                self.log_thread.join(timeout=5)
            client = docker.from_env()
            container = client.containers.get(self.container_id)
            if container:
                container.stop(timeout=5)
                container.remove(force=True)
        except Exception as e:
            print_with_color(f"idx: {self.idx_num} Container has already been stopped", "red")
            
         
    def __del__(self):
        if self.tar_avd_dir is not None:
            shutil.rmtree(self.tar_avd_dir)
        if self.tar_ini_file is not None:
            os.remove(self.tar_ini_file)
        try:
            self.emulator_process.terminate()
        except:
            pass
        try:
            self.out_file.close()
        except:
            pass
        
class AndroidLabAgent(base_agent.EnvironmentInteractingAgent):
  """A random agent interaction loop for testing purposes."""

  def __init__(
      self,
      env: interface.AsyncEnv,
      name: str = 'AndroidLabAgent',
      verbose: bool = False,
      autotest_agent: AutoTask | None = None,
      max_rounds: int = 15,
      app: str = None,
      controller: AndroidController | None = None,
      transition_pause = 5.0,
  ):
    """Initializes a RandomAgent.

    Args:
      env: The environment.
      name: The agent name.
      verbose: True if the grounder should produce verbose updates.
    """
    super().__init__(env, name)
    self.env = env
    self._verbose = verbose
    self.autotest_agent = autotest_agent
    self.max_rounds = max_rounds
    self.app = app
    self.controller = controller
    self.transition_pause = transition_pause

  def step(self, goal: str) -> base_agent.AgentInteractionResult:
    """See base class."""
    round_count = self.autotest_agent.record.get_round_count()
    
    if round_count == 0 and not self.autotest_agent.controller.check_ac_survive():
        #turn_on_ac(state, self.env)
        command = 'adb shell settings put secure enabled_accessibility_services \
"$(adb shell settings get secure enabled_accessibility_services):com.google.androidenv.accessibilityforwarder/.AccessibilityForwarder:com.example.android.xml_parser/.XMLParserAccessibilityService"'
        self.controller.run_command(command)
        time.sleep(1)
        self.autotest_agent.accessibility = self.autotest_agent.controller.check_ac_survive()
    
        max_tries = 0
        
    for i in range(0,5):
        state = self.get_post_transition_state()
        try:
            pixel = state.pixels
            break
        except:
            print(f"State: {state}")
            print(f"State is None,{max_tries}/5,retrying")
            time.sleep(5)
            max_tries = max_tries + 1

        

    
    step_data = {
        'raw_screenshot': state.pixels,
        'ui_elements': state.ui_elements,
    }

    response_state = self.autotest_agent.run_step(instruction=goal)
    if not response_state:
        done = True
        return base_agent.AgentInteractionResult(
            done,
            step_data,
        )
    try:
        latest_action = self.autotest_agent.record.get_latest_parsed_action()
        if latest_action.get("operation") == 'finish':
            finish_message = latest_action.get("kwargs",{}).get("message", None)
            android_world_answer(state, self.env, finish_message)
    except:
        import traceback
        traceback.print_exc()
        done = True
    
    done = False
    if self.autotest_agent.page_executor.is_finish:
        done = True
        self.autotest_agent.page_executor.update_screenshot(prefix="end")

    
    if round_count >= self.max_rounds:
        done = True
    time.sleep(self.transition_pause)
    return base_agent.AgentInteractionResult(
        done,
        step_data,
    )


def initialize_android_world_suite(task_template = None, n_task_combinations = 1, seed = 30):
    n_task_combinations = n_task_combinations
    task_registry = registry.TaskRegistry()
    suite = suite_utils.create_suite(
        task_registry.get_registry(family=_SUITE_FAMILY),
        n_task_combinations=n_task_combinations,
        seed=seed,
        tasks=task_template,
        use_identical_params=_FIXED_TASK_SEED,
    )
    suite.suite_family = _SUITE_FAMILY
    return suite

class AndroidWorld_AutoTest(AutoTest):
    def __init__(self, config, base_class, llm_agent, docker_idx = None, parallel_start_num = None, assign_port = None) -> None:
        self.config = config
        self.base_class = base_class
        self.llm_agent = llm_agent
       
   
        if assign_port is None:
            self.is_assign_port = False
            self.assign_port = None
            if docker_idx is None:
                self.docker_idx = 0
            if parallel_start_num is None:
                self.parallel_start_num = 0
        else:
            self.is_assign_port = True
            self.assign_port = assign_port
            self.docker_idx = docker_idx
            self.parallel_start_num = parallel_start_num
            
   
    def test_llm_agent(self):
        print("test_llm_agent")
        print(self.llm_agent)
        print("input: hello, who are you?")
        response = self.llm_agent.act(messages=[{"role": "user", "content": "hello, who are you?"}])
        print(response)
        
    def clean_docker(self):
        self.instance.stop_single_task()
        

    def start_emulator(self):
        if self.config.docker:
            type = "docker"
        else:
            type = "cmd"

        device = self.instance.initialize_single_task(self.config, log_path=self.config.task_dir)
        env = env_launcher.load_and_setup_env(
            console_port=self.instance.device_port,
            emulator_setup=_EMULATOR_SETUP,
            adb_path=self.config.adb_path,
            grpc_port=self.instance.grpc_port
        )

        self.env = env

        self.controller = AndroidController(device, type, self.instance)


    def run_serial(self, tasks):
        for task in tasks:
            self.run_task(task)

    def run_task(self, suite):
        self.instance = Instance_AndroidWorld_docker(self.config, self.docker_idx, self.parallel_start_num, self.is_assign_port, self.assign_port)
        
        try:
          
            task_id = list(suite.keys())[0]
            try:
                app = suite[task_id][0].app_names[-1]
                if 'Browser' in suite[task_id][0].name:
                    app = "No APP"
                if self.config.aw_launch == 'no':
                    app = "No APP"
            except:
                app = "No APP"
            self.instruction = suite[task_id][0].goal
            self.base_class.instruction = self.instruction
            self.command_per_step = None
            self.base_class.command_per_step = self.command_per_step
            self.app = app

            demo_timestamp = int(time.time()*1000)
            uuid_number = str(uuid.uuid4())
            self.config.task_name = task_id + "_" + str(demo_timestamp) + "_" + uuid_number
            
            self.prepare_for_task()
            self.start_emulator()
    
            self.config.checkpoint_dir = os.path.join(self.config.task_dir, "android_world_checkpoint")
            checkpoint_dir = checkpointer_lib.create_run_directory(self.config.checkpoint_dir)
 
            assert len(suite) == 1, "Only one task is supported for now"
            self.base_class.controller = self.controller
            self.base_class.config = self.config
            
            self.page_executor = self.get_executor()
            self.base_class.page_executor = self.page_executor
            self.record = JSONRecorder(id=self.config.task_name, instruction=self.instruction,
                                    page_executor=self.page_executor,
                                    config=self.config)
            self.base_class.record = self.record
            self.base_class.llm_agent = self.llm_agent
            self.autotest_agent = self.get_agent()

     
            agent = AndroidLabAgent(self.env, autotest_agent=self.autotest_agent, max_rounds=self.config.max_rounds, app=self.app, controller=self.controller)
            agent.name = "AndroidLabAgent"
        
            log_dir = os.path.join(self.config.task_dir, "output.log")
            results = suite_utils.run(
                suite,
                agent,
                checkpointer=checkpointer_lib.IncrementalCheckpointer(checkpoint_dir),
                demo_mode=False,
            )
            
        except (KeyboardInterrupt, EOFError, SystemExit, Exception) as e:
            import traceback
            traceback.print_exc()
            self.instance.stop_single_task()
            return None
            


        self.env.close()
        print("Successfully run task: ", self.config.task_name, "with results: ", results)
        self.instance.stop_single_task()

        with jsonlines.open(os.path.join(self.config.task_dir, "results.jsonl"), "w") as writer:
            for result in results:
                writer.write(result)

        return results

    def get_agent(self):
        return self.base_class.get_agent()

    def get_executor(self):
        return self.base_class.get_executor()

