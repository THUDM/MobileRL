import json
import subprocess
import time

import requests
import docker
import os
import io
import tarfile

def run_docker_command(command):
    full_command = f"{command}"
    result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def create_docker_container(docker_image_name, port_list):
    command_start = f"docker run -itd --privileged --init"
    for port in port_list:
        command_start += f" -p {port[1]}:{port[0]}"
    command_start += f" {docker_image_name}"
    returncode, stdout, stderr = run_docker_command(command_start)
    time.sleep(10)
    if returncode == 0:
        container_id = stdout.strip()
        command = f"docker cp adb_client.py {container_id}:/"
        returncode, stdout, stderr = run_docker_command(command)
        return container_id
    else:
        print(returncode, stdout, stderr)
        raise Exception(f"Error creating container: {stderr}")


def execute_command_in_container(container_id: str, command: str):
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.exec_run(cmd=["/bin/bash", "-lc", command], detach=True)
    return ""

def _make_tar_bytes(src_path: str, arcname: str) -> bytes:
    buf = io.BytesIO()
    mode = "w"
    with tarfile.open(fileobj=buf, mode=mode) as tar:
        tar.add(src_path, arcname=arcname)
    buf.seek(0)
    return buf.getvalue()


def _save_tar_to_path(tar_bytes: bytes, dest_dir: str):
    os.makedirs(dest_dir, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
        tar.extractall(path=dest_dir)

def cp_docker(local_path: str, docker_path: str, container_id: str, local_to_docker: bool = True):
    client = docker.from_env()
    container = client.containers.get(container_id)

    if local_to_docker:
        if docker_path.endswith("/"):
            dest_dir = docker_path
            arcname = os.path.basename(local_path.rstrip("/"))
            if not arcname:
                arcname = os.path.basename(local_path.rstrip("/"))
        else:
            dest_dir = os.path.dirname(docker_path) or "/"
            arcname = os.path.basename(docker_path)

        tar_bytes = _make_tar_bytes(local_path, arcname=arcname)
        res = container.put_archive(path=dest_dir, data=tar_bytes)
        if not res:
            raise Exception(f"Error copying file into container: put_archive returned False")
        return ""
    else:
        stream, stat = container.get_archive(docker_path)
        buf = io.BytesIO()
        for chunk in stream:
            buf.write(chunk)
        buf.seek(0)

        dest_dir = local_path
        if not (dest_dir.endswith(os.sep) or os.path.isdir(dest_dir)):
            dest_dir = os.path.dirname(dest_dir) or "."

        _save_tar_to_path(buf.getvalue(), dest_dir=dest_dir)
        return ""
    


def send_post_request(url, headers, data, max_attempts=10, retry_interval=3, timeout=120):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=timeout)
            return response.json()
        except Exception as e:
            print(f"Error occurred: {e}")
            attempts += 1
            if attempts < max_attempts:
                print(f"Timeout occurred. Retrying... Attempt {attempts}/{max_attempts}")
                print(data)
                time.sleep(retry_interval)
            else:
                return {'error': f'Timeout occurred after {max_attempts} attempts'}


def start_avd(port, avd_name):
    if not str(port).startswith('http://'):
        port = f'http://localhost:{port}'
    url = f'{port}/start'
    headers = {'Content-Type': 'application/json'}
    data = {'avd_name': avd_name}
    return send_post_request(url, headers, data)


def execute_adb_command(port, command):
    if not str(port).startswith('http://'):
        port = f'http://localhost:{port}'
    url = f'{port}/execute'
    headers = {'Content-Type': 'application/json'}
    data = {'command': command}
    return send_post_request(url, headers, data)


def stop_avd(port, avd_name):
    if not str(port).startswith('http://'):
        port = f'http://localhost:{port}'
    url = f'{port}/stop'
    headers = {'Content-Type': 'application/json'}
    data = {'avd_name': avd_name}
    return send_post_request(url, headers, data)
