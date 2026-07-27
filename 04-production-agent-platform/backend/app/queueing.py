from __future__ import annotations

import os
from collections import deque
from typing import Protocol


class QueueAdapter(Protocol):
    def push(self, execution_id: str) -> None: ...
    def pop(self) -> str | None: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._items: deque[str] = deque()

    def push(self, execution_id: str) -> None:
        self._items.append(execution_id)

    def pop(self) -> str | None:
        return self._items.popleft() if self._items else None


class RedisQueue:
    def __init__(self, url: str, key: str = "agent-platform:executions") -> None:
        from redis import Redis
        self.client = Redis.from_url(url, decode_responses=True)
        self.key = key

    def push(self, execution_id: str) -> None:
        self.client.rpush(self.key, execution_id)

    def pop(self) -> str | None:
        item = self.client.lpop(self.key)
        return str(item) if item else None


def build_queue() -> QueueAdapter:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            queue = RedisQueue(redis_url)
            queue.client.ping()
            return queue
        except Exception:
            pass
    return InMemoryQueue()
