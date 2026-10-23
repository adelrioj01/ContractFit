from collections import deque
from threading import Lock
from typing import Protocol, cast
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError


class JobQueueError(RuntimeError):
    """Raised when a queue operation cannot be completed safely."""


class ProcessingJobQueue(Protocol):
    def enqueue(self, job_id: UUID) -> bool: ...

    def dequeue(self, timeout_seconds: int = 0) -> UUID | None: ...


class InMemoryJobQueue:
    """Thread-safe FIFO queue suitable for tests and single-process development."""

    def __init__(self) -> None:
        self._queue: deque[UUID] = deque()
        self._pending: set[UUID] = set()
        self._lock = Lock()

    def enqueue(self, job_id: UUID) -> bool:
        with self._lock:
            if job_id in self._pending:
                return False
            self._pending.add(job_id)
            self._queue.append(job_id)
            return True

    def dequeue(self, timeout_seconds: int = 0) -> UUID | None:
        del timeout_seconds  # In-memory consumers poll; blocking is provided by Redis.
        with self._lock:
            if not self._queue:
                return None
            job_id = self._queue.popleft()
            self._pending.remove(job_id)
            return job_id


class RedisJobQueue:
    """Redis-backed FIFO with a pending set that prevents duplicate enqueues."""

    def __init__(
        self,
        url: str,
        *,
        queue_key: str = "contractfit:processing_jobs",
        pending_key: str | None = None,
    ) -> None:
        self._client: Redis = Redis.from_url(url, decode_responses=True)
        self._queue_key = queue_key
        self._pending_key = pending_key or f"{queue_key}:pending"

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        queue_key: str = "contractfit:processing_jobs",
        pending_key: str | None = None,
    ) -> "RedisJobQueue":
        return cls(url, queue_key=queue_key, pending_key=pending_key)

    def enqueue(self, job_id: UUID) -> bool:
        payload = str(job_id)
        try:
            if not self._client.sadd(self._pending_key, payload):
                return False
            try:
                self._client.rpush(self._queue_key, payload)
            except RedisError:
                self._client.srem(self._pending_key, payload)
                raise
        except RedisError as exc:
            raise JobQueueError("Redis enqueue failed") from exc
        return True

    def dequeue(self, timeout_seconds: int = 0) -> UUID | None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")

        try:
            raw_payload: object | None
            if timeout_seconds == 0:
                raw_payload = self._client.lpop(self._queue_key)
            else:
                item = cast(
                    list[object] | None,
                    self._client.blpop([self._queue_key], timeout=timeout_seconds),
                )
                raw_payload = item[1] if item is not None else None

            if raw_payload is None:
                return None

            payload = (
                raw_payload.decode("utf-8")
                if isinstance(raw_payload, bytes)
                else str(raw_payload)
            )
            self._client.srem(self._pending_key, payload)
        except RedisError as exc:
            raise JobQueueError("Redis dequeue failed") from exc

        try:
            return UUID(payload)
        except (ValueError, AttributeError) as exc:
            raise JobQueueError("Redis queue contained an invalid job UUID") from exc
