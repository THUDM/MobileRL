"""
Async Redis port-group allocator
--------------------------------
* 每 4 个连续端口视为一组。
* 双向映射键：
      <prefix>port_group:{start_port} = session_id
      <prefix>sessions:{session_id}   = start_port
* 所有写 / 删 / 续期在 Lua 脚本内一次完成，原子。
* 分布式锁用「SET NX + Lua 校验续期 / 删除」实现。
* **初始化逻辑已内嵌进 allocate_port_group()**：首次调用时自动建占位键。
* 分配端口组时在可用范围内 **随机** 选择，降低热点。
"""

import asyncio
import random
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

import redis.asyncio as redis


class RedisStateProvider:
    # ------------------------------------------------------------------ #
    # ctor
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        connection: dict,
        prefix: str,
        port_start: int,
        port_end: int,
        session_expiry: int = 600,
        lock_timeout: int = 5,
    ):
        """
        Parameters
        ----------
        connection : dict
            参数直接传给 redis.asyncio.Redis(**connection)
        prefix : str
            Redis 键前缀，可为 ''（内部会补 '.')
        port_start, port_end : int
            闭区间 [port_start, port_end]，每 4 个端口组成一组
        session_expiry : int
            端口组 / 会话映射键 TTL（秒）
        lock_timeout : int
            分布式锁超时（秒）
        """
        self._client: Optional[redis.Redis] = None
        self._client_connection_params = connection

        self.prefix = f"{prefix}." if prefix else ""
        self.session_expiry = session_expiry
        self.lock_timeout = lock_timeout

        # 预生成端口组
        self.port_groups: List[List[int]] = [
            list(range(p, p + 4))
            for p in range(port_start, port_end + 1, 4)
            if p + 3 <= port_end
        ]

        # 唯一 client id（线程 / 进程级）
        self.client_id = uuid.uuid4().hex

    # ------------------------------------------------------------------ #
    # redis helpers
    # ------------------------------------------------------------------ #
    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(**self._client_connection_params)
        return self._client

    # --------------------------- key helpers --------------------------- #
    def _port_group_key(self, start_port: int) -> str:
        return f"{self.prefix}port_group:{start_port}"

    def _session_map_key(self, session_id: str) -> str:
        return f"{self.prefix}sessions:{session_id}"

    def _lock_key(self, name: str) -> str:
        return f"{self.prefix}lock:{name}"

    # ------------------------------------------------------------------ #
    # distributed lock : SET NX + Lua
    # ------------------------------------------------------------------ #
    async def acquire_lock(
        self, lock_name: str, client_id: str, timeout: int | None = None
    ) -> bool:
        """
        True  -> 成功获得 / 续期锁
        False -> 获取失败
        """
        timeout = timeout or self.lock_timeout
        client = await self._get_client()
        key = self._lock_key(lock_name)

        # 初次尝试
        if await client.set(key, client_id, nx=True, ex=timeout):
            return True

        # 若已持有则续期
        return bool(
            await client.eval(
                """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("expire", KEYS[1], ARGV[2])
                else
                    return 0
                end
                """,
                1,
                key,
                client_id,
                str(timeout),
            )
        )

    async def release_lock(self, lock_name: str, client_id: str):
        client = await self._get_client()
        await client.eval(
            """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """,
            1,
            self._lock_key(lock_name),
            client_id,
        )

    @asynccontextmanager
    async def with_lock(self, lock_name: str, timeout: int | None = None):
        """异步上下文管理器：忙等直到拿到分布式锁。"""
        while True:
            if await self.acquire_lock(lock_name, self.client_id, timeout):
                break
            await asyncio.sleep(random.uniform(1, 2))

        try:
            yield
        finally:
            await self.release_lock(lock_name, self.client_id)

    # ------------------------------------------------------------------ #
    # allocate (init + 随机分配)
    # ------------------------------------------------------------------ #
    async def allocate_port_group(self, session_id: str) -> Optional[List[int]]:
        """
        1. 进入全局锁 "alloc_lock"。
        2. 若尚未初始化（检查 sentinel），立即初始化占位键。
        3. 若会话已有分配，直接返回。
        4. 按 **随机顺序** 遍历端口组，Lua 抢占首个空闲。
        """
        async with self.with_lock("alloc_lock", timeout=10):
            client = await self._get_client()
            session_key = self._session_map_key(session_id)

            # ---- step 1: lazy init pool (once) ------------------------- #
            sentinel = f"{self.prefix}__port_pool_inited__"
            if not await client.exists(sentinel):
                for group in self.port_groups:
                    await client.set(
                        self._port_group_key(group[0]),
                        "",  # 占位
                        ex=self.session_expiry,
                        nx=True,
                    )
                await client.set(sentinel, "1")

            # ---- step 2: session already has a group ------------------ #
            current_port = await client.get(session_key)
            if current_port is not None:
                start_port = int(current_port)
                return list(range(start_port, start_port + 4))

            # ---- step 3: random order scan ---------------------------- #
            groups = self.port_groups[:]
            random.shuffle(groups)

            lua_allocate = """
            -- KEYS[1] = port_group_key
            -- KEYS[2] = session_key
            -- ARGV[1] = session_id
            -- ARGV[2] = start_port
            -- ARGV[3] = ttl
            local cur = redis.call('get', KEYS[1])
            if (not cur) or (cur == '') then
                -- 没人占用 / 占位键仍为空，直接写入
                redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[3])
                redis.call('set', KEYS[2], ARGV[2], 'EX', ARGV[3])
                return ARGV[2]
            else
                return nil
            end
            """

            for group in groups:
                start_port = group[0]
                group_key = self._port_group_key(start_port)

                result = await client.eval(
                    lua_allocate,
                    2,
                    group_key,
                    session_key,
                    session_id,
                    str(start_port),
                    str(self.session_expiry),
                )
                if result:
                    return group     # 成功分配

            return None              # 全部占用

    # ------------------------------------------------------------------ #
    # renew
    # ------------------------------------------------------------------ #
    async def renew_port_group(self, session_id: str):
        """续期：只操作自己的两个键，不需要全局锁。"""
        client = await self._get_client()
        session_key = self._session_map_key(session_id)

        lua_renew = """
        -- KEYS[1] = sessions:{sid}
        -- ARGV[1] = session_id
        -- ARGV[2] = port_group_prefix
        -- ARGV[3] = ttl
        local start_port = redis.call('get', KEYS[1])
        if not start_port then
            return 0
        end
        local group_key = ARGV[2] .. start_port
        if redis.call('get', group_key) ~= ARGV[1] then
            return 0
        end
        redis.call('expire', KEYS[1], ARGV[3])
        redis.call('expire', group_key, ARGV[3])
        return 1
        """

        await client.eval(
            lua_renew,
            1,
            session_key,
            session_id,
            f"{self.prefix}port_group:",
            str(self.session_expiry),
        )

    # ------------------------------------------------------------------ #
    # release
    # ------------------------------------------------------------------ #
    async def release_port_group(self, session_id: str):
        """释放端口组：仅删除自己键，无需全局锁。"""
        client = await self._get_client()
        session_key = self._session_map_key(session_id)

        lua_release = """
        -- KEYS[1] = sessions:{sid}
        -- ARGV[1] = session_id
        -- ARGV[2] = port_group_prefix
        local start_port = redis.call('get', KEYS[1])
        if not start_port then
            return 0
        end
        local group_key = ARGV[2] .. start_port
        if redis.call('get', group_key) ~= ARGV[1] then
            return 0
        end
        redis.call('del', KEYS[1])
        redis.call('del', group_key)
        return 1
        """

        await client.eval(
            lua_release,
            1,
            session_key,
            session_id,
            f"{self.prefix}port_group:",
        )

        

from typing import Optional, List
import asyncio
import threading

class PortAllocatorSync:
    def __init__(self, redis_provider):
        self.provider = redis_provider
        self._loop = None
        self._loop_thread = None

    def _ensure_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
            self._loop_thread.start()
        return self._loop

    def _run(self, coro, loop: Optional[asyncio.AbstractEventLoop]):
        if loop is None:
            loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def allocate(self, session_id: str, loop: Optional[asyncio.AbstractEventLoop] = None) -> Optional[List[int]]:
        return self._run(self.provider.allocate_port_group(session_id), loop)

    def renew(self, session_id: str, loop: Optional[asyncio.AbstractEventLoop] = None):
        return self._run(self.provider.renew_port_group(session_id), loop)

    def release(self, session_id: str, loop: Optional[asyncio.AbstractEventLoop] = None):
        return self._run(self.provider.release_port_group(session_id), loop)

    def shutdown(self):
        """优雅关闭内部事件循环"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop_thread.join()
            self._loop.close()
            self._loop = None
            self._loop_thread = None
'''
import asyncio
import random
import threading
import time


REDIS_CONN = dict(host="127.0.0.1", port=6379, decode_responses=True)

# 8000-8019 共 5 组，每组 4 个端口；足够 3×3 并发测试
PORT_START, PORT_END = 18000, 19000


async def allocate_release_cycle(provider: RedisStateProvider, tag: str):
    """
    申请 3 组端口 -> 随机等待 -> 释放 -> 再申请 3 组 -> 随机等待 -> 全部释放
    """
    def rand_sleep():
        return asyncio.sleep(random.uniform(1, 3))

    # ---------- 第 1 轮 ----------
    first_batch = []
    for i in range(3):
        sid = f"{tag}-1-{i}"
        pg = await provider.allocate_port_group(sid)
        print(f"[{tag}] 1st allocate #{i}: {pg}")
        first_batch.append((sid, pg))
    await rand_sleep()

    for sid, _ in first_batch:
        await provider.release_port_group(sid)
        print(f"[{tag}] 1st release {sid}")

    # ---------- 第 2 轮 ----------
    second_batch = []
    for i in range(3):
        sid = f"{tag}-2-{i}"
        pg = await provider.allocate_port_group(sid)
        print(f"[{tag}] 2nd allocate #{i}: {pg}")
        second_batch.append((sid, pg))
    await rand_sleep()

    for sid, _ in second_batch:
        await provider.release_port_group(sid)
        print(f"[{tag}] 2nd release {sid}")


def thread_worker(tid: int):
    """在线程中启动一个新的事件循环运行异步任务。"""
    provider = RedisStateProvider(
        connection=REDIS_CONN,
        prefix="test",
        port_start=PORT_START,
        port_end=PORT_END,
        session_expiry=10,  # TTL 10 秒够用
    )
    asyncio.run(allocate_release_cycle(provider, f"Thread-{tid}"))


def main():
    threads = []
    for i in range(3):  # 启 3 个线程
        t = threading.Thread(target=thread_worker, args=(i,), daemon=True)
        t.start()
        threads.append(t)

    # 等待所有线程结束
    for t in threads:
        t.join()
    print("=== all done ===")


if __name__ == "__main__":
    main()'''