import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, Set, Sequence, List

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

app = FastAPI()

allocated_ports: Dict[int, datetime] = {}  # port: expiry
allocation_lock = asyncio.Lock()

TTL = timedelta(minutes=20)  # preserve allocated ports for 20 minutes


class AllocationResponse(BaseModel):
    ports: List[int]


async def get_used_ports(port_range: Sequence[int]) -> Set[int]:
    used: Set[int] = set()

    # add locally cached allocated ports
    for port in allocated_ports.keys():
        used.add(port)

    # use lsof to get list of used ports
    proc = await asyncio.create_subprocess_exec(
        'lsof', '-iTCP', '-sTCP:LISTEN', '-nP',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(500, 'Failed to check used ports')

    lines = stdout.decode()
    matches = re.finditer(r':(\d+)\s', lines, re.MULTILINE)
    for match in matches:
        try:
            port = int(match.group(1))
            used.add(port)
        except:
            pass
    return used


async def cleanup_expired_ports():
    now = datetime.now()
    for port, expiry in list(allocated_ports.items()):
        if expiry < now:
            del allocated_ports[port]


@app.post("/allocate", response_model=AllocationResponse)
async def allocate_port(
    start: int = Body(ge=1, le=65535),
    end: int = Body(ge=1, le=65535),
    seq: int = Body(default=1, ge=1),
):
    if start > end:
        raise HTTPException(400, 'invalid port range')

    port_range = range(start, end + 1)

    async with allocation_lock:
        await cleanup_expired_ports()
        used = await get_used_ports(port_range)
        available = set(port_range) - used
        if not available:
            raise HTTPException(503, 'No available ports in this range')

        # Allocate a single port
        if seq == 1:
            port = available.pop()
            allocated_ports[port] = datetime.now() + TTL
            return AllocationResponse(ports=[port])

        # Allocate a sequence of ports
        sorted_available = sorted(available)
        for i in range(len(sorted_available) - seq + 1):
            ports = sorted_available[i:i + seq]
            if all(ports[j] + 1 == ports[j + 1] for j in range(seq - 1)):
                for port in ports:
                    allocated_ports[port] = datetime.now() + TTL
                return AllocationResponse(ports=ports)

        raise HTTPException(503, 'No ports are available to satisfy the sequence request')
