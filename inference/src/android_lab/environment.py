from typing import Dict, Optional, Union, List

from agentrl.worker.environment import EnvironmentDelegation


class AndroidLabEnvironmentDelegation(EnvironmentDelegation):

    def __init__(self):
        super().__init__('android_lab')

    def get_subtypes(self) -> List[str]:
        return list(self.get_container_images().keys())

    def is_exclusive(self, subtype: str) -> bool:
        return True

    async def create_docker_container(self, attrs: dict, subtype: str) -> dict:
        attrs['ExposedPorts'] = {
            '5555/tcp': {},
            f'{self.get_service_port(subtype)}/tcp': {}
        }

        attrs['HostConfig']['Devices'] = [{
            'PathOnHost': '/dev/kvm',
            'PathInContainer': '/dev/kvm',
            'CgroupPermissions': 'rwm'
        }]

        attrs['Cmd'] = [
            'python',
            '/adb_client.py'
        ]

        return attrs

    def get_service_port(self, subtype: str) -> Optional[Union[int, List[int]]]:
        return 6060

    def get_container_images(self) -> Dict[str, str]:
        return {
            'android_lab_eval': 'xuyifan0731/mobilerl-androidlab-eval'
        }
