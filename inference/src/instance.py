import logging
import os
import time
from typing import Optional

from agentrl.worker.environment import EnvironmentController
from android_lab.evaluation.auto_test import Instance
from android_lab.evaluation.docker_utils import start_avd
from android_lab.evaluation.utils import execute_adb


class FrameworkProvidedInstance(Instance):

    controller: EnvironmentController

    def __init__(self, config, *args, **kwargs):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.env_type = kwargs.get('env_type', 'default')
        self.session_id: Optional[str] = None
        self.container_id: Optional[str] = None
        self.device_port: Optional[int] = None
        self.adb_port: Optional[int] = None
        self.grpc_port: Optional[int] = None

    def __del__(self):
        pass  # override

    def initialize_worker(self, *args, **kwargs):
        pass  # override

    def initialize_single_task(self, config, *args, **kwargs) -> str:
        session_id, container_ids, container_urls = self.controller.sync_start_session(self.env_type)
        self.session_id = session_id
        self.container_id = container_ids[self.env_type]
        self.docker_port_local = container_urls[self.env_type]

        # if port_allocator is present, the environment is using host network and dynamically allocating ports
        if hasattr(self.controller.delegation, 'port_allocator'):
            # we need to retrieve the ports from the container environment variables
            try:
                env_vars = self.controller.sync_get_env_variables(self.container_id)
                if value := env_vars.get('ADB_PORT'):
                    self.adb_port = int(value)
                    self.device_port = self.adb_port - 1
                if value := env_vars.get('GRPC_PORT'):
                    self.grpc_port = int(value)
                if not self.device_port or not self.adb_port or not self.grpc_port:
                    raise RuntimeError('failed to retrieve device ports from environment variables')
            except:
                self.stop_single_task()
                raise

            # workaround for emulator console port only listens to localhost
            host_ip = os.environ.get('EMULATOR_HOST')
            if host_ip and host_ip not in ['localhost', '127.0.0.1', '::1']:
                socat_cmd = f'socat TCP-LISTEN:{self.device_port},fork,reuseaddr,bind={host_ip} TCP:localhost:{self.device_port}'
                self.logger.info(f'starting socat command: {socat_cmd}')
                self.controller.sync_execute_command(self.container_id, [
                    '/bin/bash',
                    '-c',
                    f'{socat_cmd} > /dev/null 2>&1 < /dev/null & disown $!'
                ])

            adb_type = 'cmd'
        else:
            self.device_port = 5554
            self.adb_port = 5555

            # for android_lab environment, call the adb client to start the emulator
            time.sleep(3)  # ensure the container is started
            result = start_avd(self.docker_port_local, config.avd_name)
            if result.get('error'):
                self.stop_single_task()
                raise RuntimeError(f'failed to start AVD: {result.error}')

            # create necessary directories for the adb client
            self.controller.sync_execute_command(self.container_id, [
                'mkdir',
                '-p',
                config.task_dir,
                config.trace_dir,
                config.screenshot_dir,
                config.xml_dir
            ])

            adb_type = 'docker'

        adb_path = config.adb_path or 'adb'
        device = f'emulator-{self.device_port}'

        self.logger.info(f'waiting for device {device} to boot...')
        limit_time = time.time() + 120
        while True:
            boot_anim = f'{adb_path} -s {device} shell getprop init.svc.bootanim'
            boot_anim = execute_adb(boot_anim, type=adb_type, output=False, port=self.docker_port_local)

            boot_complete = f'{adb_path} -s {device} shell getprop sys.boot_completed'
            boot_complete = execute_adb(boot_complete, type=adb_type, output=False, port=self.docker_port_local)

            if boot_anim == 'stopped' and boot_complete == '1':
                break
            if time.time() > limit_time:
                self.stop_single_task()
                raise TimeoutError('device did not boot in time limit')
            time.sleep(5)

        # for docker containers using the bridge network,
        # network connection in the emulator should be manually enabled
        if adb_type == 'docker':
            turn_on_wifi = f'{adb_path} -s {device} shell svc wifi enable'
            execute_adb(turn_on_wifi, type=adb_type, output=False, port=self.docker_port_local)
            time.sleep(1)

            connect_wifi = f'{adb_path} -s {device} shell su 0 cmd -w wifi connect-network AndroidWifi open'
            execute_adb(connect_wifi, type=adb_type, output=False, port=self.docker_port_local)
            time.sleep(1)

        self.logger.info(f'device {device} is ready')
        return device

    def stop_single_task(self):
        if self.session_id:
            self.controller.sync_end_session(self.session_id)
            self.session_id = None
            self.container_id = None
            self.device_port = None
            self.adb_port = None
            self.grpc_port = None
            self.docker_port_local = None
