import datetime
import time
import docker
import os
import shutil
import subprocess
import uuid
from android_lab.evaluation.configs import TaskConfig
from android_lab.evaluation.docker_utils import execute_command_in_container, start_avd, stop_avd, cp_docker
from android_lab.evaluation.evaluation import *
from android_lab.evaluation.utils import *
from android_lab.page_executor import TextOnlyExecutor, TextOnlyExecutor_v4, TextOnlyExecutor_v41, TextOnlyExecutor_android_world
from android_lab.page_executor.simple_vision_executor import VisionExecutor
from android_lab.recorder import JSONRecorder
from android_lab.templates import *
from android_lab.templates.packages import find_package


class Instance():
    def __init__(self, config, idx = 0):
        self.idx = str(idx)
        self.type = "cmd"
        self.config = config
        self.container_id = None
        self.docker_port_local = None
        self.avd_name = None
        self.tar_avd_dir = None
        self.tar_ini_file = None
        self.initialize_worker()

    def initialize_worker(self):
        sdk_path = self.config.avd_base
        src_avd_name = self.config.avd_name
        self.avd_name = f"{src_avd_name}_{self.idx}"
        self.tar_avd_dir, self.tar_ini_file = clone_avd(src_avd_name, self.avd_name, sdk_path)

    def initialize_single_task(self):
        avd_name = self.avd_name
        print_with_color(f"Starting Android Emulator with AVD name: {avd_name}", "blue")
        if not os.path.exists(self.config.avd_log_dir):
            os.makedirs(self.config.avd_log_dir, exist_ok=True)
        out_file = open(os.path.join(self.config.avd_log_dir, 'emulator_output.txt'), 'a')

        if self.config.show_avd:
            emulator_process = subprocess.Popen(["emulator", "-avd", avd_name, "-no-snapshot-save"], stdout=out_file,
                                                stderr=out_file)
        else:
            emulator_process = subprocess.Popen(
                ["emulator", "-avd", avd_name, "-no-snapshot-save", "-no-window", "-no-audio"], stdout=out_file,
                stderr=out_file)
        print_with_color(f"Waiting for the emulator to start...", "blue")
        while True:
            try:
                device = get_adb_device_name(avd_name)
            except:
                continue
            if device is not None:
                break

        while True:
            boot_complete = f"adb -s {device} shell getprop init.svc.bootanim"
            boot_complete = execute_adb(boot_complete, output=False)
            if boot_complete == 'stopped':
                break
            time.sleep(1)
        time.sleep(1)
        self.emulator_process = emulator_process
        self.out_file = out_file
        device_list = list_all_devices()
        if len(device_list) == 1:
            device = device_list[0]
            print_with_color(f"Device selected: {device}", "yellow")
        else:
            device = get_avd_serial_number(avd_name)
        return device

    def stop_single_task(self):
        self.emulator_process.terminate()

        while True:
            try:
                device = get_adb_device_name(self.config.avd_name)
                command = f"adb -s {device} reboot -p"
                ret = execute_adb(command, output=False)
                self.emulator_process.terminate()
            except:
                device = None
            if device is None:
                break
            time.sleep(1)
        self.out_file.close()

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

class Docker_Instance(Instance):
    def __init__(self, config, idx = 0):
        self.idx = idx
        self.config = config
        self.container_id = None
        self.docker_port_local = None
        self.config = config

    def start_docker(self, docker_image_name, docker_port):
        client = docker.from_env()
        try:
            container = client.containers.run(
                image=docker_image_name,
                detach=True,
                tty=True,
                stdin_open=True,
                privileged=True,
                init=True,
                ports={f"{docker_port}/tcp": self.docker_port_local},
            )
        except docker.errors.ContainerError as e:
            print("ContainerError:", e.stderr.decode() if e.stderr else str(e))
        except docker.errors.ImageNotFound as e:
            print("ImageNotFound:", str(e))
        except docker.errors.APIError as e:
            print("APIError:", str(e))
        container_id = container.id
        self.device = f"emulator-{self.docker_port_local}"
        cp_docker(local_path="android_lab/evaluation/adb_client.py", docker_path="/adb_client.py", container_id=container.id, local_to_docker=True)
        return container_id

    def check_avd_status(self):
        device = self.device
        limit_time = time.time() + 120
        while True:
            bootanim = f"docker exec {self.container_id} /root/.android/platform-tools/adb -s {device} shell getprop init.svc.bootanim"
            bootanim = execute_adb(bootanim, output=False)
            
            boot_complete = f"docker exec {self.container_id} /root/.android/platform-tools/adb -s {device} shell getprop sys.boot_completed"
            boot_complete = execute_adb(boot_complete, output=False)
                
            if bootanim == 'stopped' and boot_complete == '1':
                break
            if time.time() > limit_time:
                return False
            time.sleep(5)
        return True

    def initialize_single_task(self,config, assign_port = None):
        if assign_port is not None:
            self.docker_port_local = assign_port
        if config.docker_image_name is not None:
            docker_image_name = config.docker_image_name
        else:
            docker_image_name = config.docker_args.get("image_name")
        docker_port = config.docker_args.get("port")
        container_id = self.start_docker(docker_image_name, docker_port)

        command = "/usr/local/bin/python adb_client.py > server.txt 2>&1"
        execute_command_in_container(container_id, command)
        self.container_id = container_id
        time.sleep(3)

        avd_name = config.avd_name
        result = start_avd(self.docker_port_local, avd_name)
        device = result.get("device")

        execute_command_in_container(self.container_id, f"mkdir -p {config.task_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {config.trace_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {config.screenshot_dir}")
        execute_command_in_container(self.container_id, f"mkdir -p {config.xml_dir}")
        time.sleep(10)
        return device

    def stop_single_task(self):
        print_with_color("Stopping Android Emulator in docker...", "blue")
        client = docker.from_env()
        try:
            container = client.containers.get(self.container_id)
            if container:
                container.stop(timeout=5)
                container.remove(force=True)
        except:
            pass
        

 
        


    def __del__(self):
        if self.container_id is not None:
            client = docker.from_env()
            try:
                container = client.containers.get(self.container_id)
            except:
                return
            if container is not None:
                self.stop_single_task()
 


class AutoTest():
    def __init__(self, config: TaskConfig) -> None:
        self.config = config

    def prepare_for_task(self):
        os.makedirs(self.config.save_dir, exist_ok=True)
        self.config.task_dir = os.path.join(self.config.save_dir, self.config.task_name)
        self.config.log_path = os.path.join(self.config.task_dir, f"log_explore_{self.config.task_name}.jsonl")
        self.config.trace_dir = os.path.join(self.config.task_dir, 'traces')
        self.config.screenshot_dir = os.path.join(self.config.task_dir, 'Screen')
        self.config.xml_dir = os.path.join(self.config.task_dir, 'xml')
        if not os.path.exists(self.config.task_dir):
            os.mkdir(self.config.task_dir)
        os.makedirs(self.config.trace_dir, exist_ok=True)
        os.makedirs(self.config.screenshot_dir, exist_ok=True)
        os.makedirs(self.config.xml_dir, exist_ok=True)

    def start_emulator(self, instance, assign_port = None):
        type = "docker"
        device = instance.initialize_single_task(self.config, assign_port)

        self.controller = AndroidController(device, type, instance)
        if not self.config.android_world:
            self.controller.run_command("adb root")
            self.controller.run_command("adb emu geo fix -122.156 37.438")
            if "map.me" not in self.instruction:
                self.controller.run_command("adb shell date \"2024-05-10 12:00:00\"")
        if self.config.mode == "in_app":
            self.controller.launch_app(find_package(self.app))
            time.sleep(15)

    def run_serial(self, tasks):
        instance = Docker_Instance(self.config)
        import random
        assign_port = random.randint(10000, 65535)
        for task in tasks:
            self.run_task(task, instance, assign_port)
            
    def run_task(self, task_dict, instance, assign_port = None):
        try:
            self._run_task(task_dict, instance, assign_port)
        except Exception as e:
            instance.stop_single_task()
            import traceback
            traceback.print_exc()

        

    def _run_task(self, task_dict, instance, assign_port = None):
        task_id = task_dict['task_id']
        demo_timestamp = int(time.time()*1000)
        uuid_number = str(uuid.uuid4())
        self.config.task_name = task_id + "_" + str(demo_timestamp) + "_" + uuid_number

        self.instruction = task_dict['task_instruction']
        self.app = task_dict['app']
        if not self.config.sample:
            self.command_per_step = task_dict['command_per_step']
        else:
            self.command_per_step = None
        self.prepare_for_task()
        self.start_emulator(instance, assign_port)
        self.llm_agent = task_dict["agent"]

        round_count = 0
        task_complete = False

        self.page_executor = self.get_executor()

        self.record = JSONRecorder(id=self.config.task_name, instruction=self.instruction,
                                   page_executor=self.page_executor,
                                   config=self.config)
        task_agent = self.get_agent()
        if self.app in ["map.me", "Pi Music Player"]:
            task_agent.accessibility = task_agent.controller.check_ac_survive()
        while round_count < self.config.max_rounds:
            round_count += 1
            state = task_agent.run_step(instruction=self.instruction)
            time.sleep(self.config.request_interval)

            if not state:
                break

            if task_agent.page_executor.is_finish:
                task_agent.page_executor.update_screenshot(prefix="end")
                task_complete = True
                break

        instance.stop_single_task()
        if task_complete:
            print_with_color(f"Completed successfully. {round_count} rounds generated.", "green")
        elif round_count == self.config.max_rounds:
            print_with_color(
                f"Finished due to reaching max rounds. {round_count} rounds generated.",
                "yellow")
        else:
            print_with_color(f"Finished unexpectedly. {round_count} rounds generated.", "red")

    def get_agent(self):
        return NotImplementedError

    def get_executor(self):
        return NotImplementedError


class TextOnlyMobileTask_AutoTest(AutoTest):
    def get_agent(self):
        task_agent = TextOnlyTask(self.instruction, self.controller, self.page_executor, self.llm_agent, self.record,
                                  self.command_per_step)
        return task_agent

    def get_executor(self):
        return TextOnlyExecutor(self.controller, self.config)


class TextOnlyMobileTask_AutoTest_v4(AutoTest):
    def get_agent(self):
        task_agent = TextOnlyTask(self.instruction, self.controller, self.page_executor, self.llm_agent, self.record,
                                  self.command_per_step)
        return task_agent

    def get_executor(self):
        return TextOnlyExecutor_v4(self.controller, self.config)


class Multi_ScreenshotMobileTask_AutoTest(AutoTest):
    def get_agent(self):
        task_agent = Multi_ScreenshotTask(self.instruction, self.controller, self.page_executor, self.llm_agent, self.record,
                                          self.command_per_step, self.config)
        return task_agent
    
    def get_executor(self):
        return TextOnlyExecutor(self.controller, self.config)


class Multi_ScreenshotMobileTask_AutoTest_v4(TextOnlyMobileTask_AutoTest_v4):
    def get_agent(self):
        task_agent = Multi_ScreenshotTask(self.instruction, self.controller, self.page_executor, self.llm_agent, self.record,
                                          self.command_per_step, self.config)
        return task_agent

class Multi_ScreenshotMobileTask_AutoTest_v4_android_world(Multi_ScreenshotMobileTask_AutoTest_v4):
    def get_executor(self):
        return TextOnlyExecutor_android_world(self.controller, self.config)

class ScreenshotMobileTask_AutoTest(TextOnlyMobileTask_AutoTest):
    def get_agent(self):
        task_agent = ScreenshotTask(self.instruction, self.controller, self.page_executor, self.llm_agent, self.record,
                                    self.command_per_step, self.config)
        return task_agent

    def get_executor(self):
        return VisionExecutor(self.controller, self.config)


