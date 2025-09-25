from queue import Queue
import concurrent
from android_lab.evaluation.auto_test import *
from android_lab.evaluation._redis import PortAllocatorSync, RedisStateProvider
import uuid

def create_redis_provider(config):
    redis_config_port = config.redis_config_port
    redis_port_start = config.redis_port_start
    redis_port_end = config.redis_port_end
    redis_config = {
        "host": "localhost",
        "port": redis_config_port,
        "decode_responses": False
    }
    redis_provider = RedisStateProvider(
        connection=redis_config,
        prefix='portalloc',
        port_start=redis_port_start,
        port_end=redis_port_end
    )
    return PortAllocatorSync(redis_provider)
    

def task_done_callback(future, instance, free_dockers, results, port_allocator, task_uuid, is_aw = False):
    try:
        port_allocator.release(task_uuid)
        if is_aw:
            result = future.result()
            if result:
                results.extend(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Task failed with exception: {e}")
    finally:
        free_dockers.put(instance)

def parallel_worker(class_, config, parallel, tasks):
    port_allocator = create_redis_provider(config)
    free_dockers = Queue()
    results = []
    for idx in range(parallel):
        free_dockers.put(idx)

    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
        while tasks:
            if free_dockers.empty():
                time.sleep(0.5)
                continue
            
            task_uuid = str(uuid.uuid4())
            ports = port_allocator.allocate(task_uuid)
            idx = free_dockers.get()
            instance = Docker_Instance(config, idx)
            task = tasks.pop(0)

            config_copy = copy.deepcopy(config)
            auto_class = class_(config_copy)

            future = executor.submit(auto_class.run_task, task, instance, assign_port = ports[0])
            future.add_done_callback(lambda fut, di=idx: task_done_callback(fut,di, free_dockers, results, port_allocator, task_uuid))
    port_allocator.shutdown()


def parallel_worker_android_world(args, class_, AndroidWorld_AutoTest, config, agent, parallel, tasks, sample = False):
    port_allocator = create_redis_provider(config)
    free_dockers = Queue()
    results = []
    if isinstance(tasks, dict):
        items = list(tasks.items())
        tasks = [dict(items[i:i + 1]) for i in range(0, len(items), 1)]
    
    for idx in range(parallel):
        free_dockers.put(idx)
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
        while tasks:
            if free_dockers.empty():
                time.sleep(0.5)
                continue

            #instance = free_dockers.get()
            idx = free_dockers.get()
            task = tasks.pop(0)
            config_copy = copy.deepcopy(config)
            #agent_copy = copy.deepcopy(agent)
            auto_class = class_(config_copy)
            task_uuid = str(uuid.uuid4())
            ports = port_allocator.allocate(task_uuid)
            android_world_class = AndroidWorld_AutoTest(config_copy, auto_class, agent, assign_port = ports[0])
            future = executor.submit(android_world_class.run_task, task)
            future.add_done_callback(lambda fut, di=idx: task_done_callback(fut, di, free_dockers, results, port_allocator, task_uuid, is_aw = True))
    port_allocator.shutdown()
    return results
