from __future__ import annotations

import os
from typing import List, Optional

from aiohttp import ClientSession

from agentrl.worker.environment import EnvironmentDelegation
from ..port_allocator import allocate_port

DOCKER_IMAGE = 'xuyifan0731/mobilerl-androidworld-eval'


class PortAllocatorClient:

    def __init__(self, url: Optional[str], port_start: int, port_end: int):
        self._client: Optional[ClientSession] = None
        self.url = url
        self.port_start = port_start
        self.port_end = port_end

    async def _get_client(self) -> ClientSession:
        if self._client is None and self.url and self.url != 'local':
            self._client = ClientSession(base_url=self.url)
        return self._client

    async def allocate_port(self) -> int:
        return (await self.allocate_ports(1))[0]

    async def allocate_ports(self, seq: int = 1) -> List[int]:
        client = await self._get_client()

        if client:
            response = await client.post('allocate', json={
                'start': self.port_start,
                'end': self.port_end,
                'seq': seq
            })
            response.raise_for_status()
            data = await response.json()
            return data['ports']

        data = await allocate_port(self.port_start, self.port_end, seq)
        return data.ports


class AndroidWorldEnvironmentDelegation(EnvironmentDelegation):

    def __init__(self, port_allocator_url: str):
        super().__init__('android_world')
        self.port_allocator = PortAllocatorClient(port_allocator_url, 5554, 7999)
        self.adb_key = self._get_adb_key()
        if not os.environ.get('EMULATOR_TOKEN'):
            os.environ['EMULATOR_TOKEN'] = 'agentbench'  # default token for emulator console

    def is_exclusive(self, subtype: str) -> bool:
        return True

    async def create_docker_container(self, attrs: dict, subtype: str) -> dict:
        ports = await self.port_allocator.allocate_ports(3)

        attrs['Image'] = DOCKER_IMAGE
        attrs['Env'] = {
            'ADB_KEY': self.adb_key,
            'ADB_PORT': str(ports[1]),
            'GRPC_PORT': str(ports[2]),
            'TOKEN': os.environ['EMULATOR_TOKEN']
        }
        attrs['HostConfig']['Devices'] = [{
            'PathOnHost': '/dev/kvm',
            'PathInContainer': '/dev/kvm',
            'CgroupPermissions': 'rwm'
        }]
        attrs['Healthcheck'] = {
            # query adb to check if the avd is booted
            'Test': [
                'CMD-SHELL',
                f'/android/sdk/platform-tools/adb -s emulator-{ports[0]} shell getprop dev.bootcomplete | grep "1"'
            ],
            'Interval': 10 * 1000 * 1000 * 1000,  # 10 seconds
            'Timeout': 5 * 1000 * 1000 * 1000,  # 5 seconds
            'StartPeriod': 30 * 1000 * 1000 * 1000,  # 30 seconds
            'StartInterval': 1 * 1000 * 1000 * 1000,  # 1 second
        }

        return attrs

    @staticmethod
    def _get_adb_key() -> str:
        """Get the ADB key from different possible locations:"""

        # 1. Environment variable `ADB_KEY`
        adb_key = os.getenv('ADB_KEY')
        if adb_key:
            return adb_key

        # 2. Docker secret `adbkey`
        try:
            with open('/run/secrets/adbkey', 'r') as f:
                adb_key = f.read().strip()
                return adb_key
        except FileNotFoundError:
            pass

        # 3. File at `~/.android/adbkey`
        try:
            with open(os.path.expanduser('~/.android/adbkey'), 'r') as f:
                adb_key = f.read().strip()
                return adb_key
        except FileNotFoundError:
            raise RuntimeError('ADB key not found in environment variable, Docker secret, or home directory.')
