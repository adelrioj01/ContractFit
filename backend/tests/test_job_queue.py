from collections import deque
from uuid import UUID, uuid4

import pytest
from redis.exceptions import RedisError

from contractfit.job_queue import InMemoryJobQueue, JobQueueError, RedisJobQueue


class FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, deque[str | bytes]] = {}
        self.sets: dict[str, set[str]] = {}
        self.fail_operation: str | None = None

    def _fail_if_requested(self, operation: str) -> None:
        if self.fail_operation == operation:
            raise RedisError(f"{operation} failed")

    def sadd(self, key: str, value: str) -> int:
        self._fail_if_requested("sadd")
        values = self.sets.setdefault(key, set())
        before = len(values)
        values.add(value)
        return len(values) - before

    def srem(self, key: str, value: str) -> int:
        self._fail_if_requested("srem")
        values = self.sets.setdefault(key, set())
        existed = value in values
        values.discard(value)
        return int(existed)

    def rpush(self, key: str, value: str) -> int:
        self._fail_if_requested("rpush")
        values = self.lists.setdefault(key, deque())
        values.append(value)
        return len(values)

    def lpop(self, key: str) -> str | bytes | None:
        self._fail_if_requested("lpop")
        values = self.lists.setdefault(key, deque())
        return values.popleft() if values else None

    def blpop(self, keys: list[str], timeout: int) -> list[str | bytes] | None:
        del timeout
        key = keys[0]
        value = self.lpop(key)
        return [key, value] if value is not None else None


def install_fake_redis(monkeypatch: pytest.MonkeyPatch, fake: FakeRedis) -> None:
    monkeypatch.setattr(
        "contractfit.job_queue.Redis.from_url",
        lambda *_args, **_kwargs: fake,
    )


def test_in_memory_queue_is_fifo_and_deduplicated() -> None:
    queue = InMemoryJobQueue()
    first = uuid4()
    second = uuid4()

    assert queue.enqueue(first) is True
    assert queue.enqueue(first) is False
    assert queue.enqueue(second) is True
    assert queue.dequeue() == first
    assert queue.dequeue() == second
    assert queue.dequeue() is None


def test_in_memory_job_can_be_enqueued_again_after_dequeue() -> None:
    queue = InMemoryJobQueue()
    job_id = uuid4()

    assert queue.enqueue(job_id) is True
    assert queue.dequeue() == job_id
    assert queue.enqueue(job_id) is True


def test_redis_queue_is_fifo_and_removes_pending_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis()
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue.from_url("redis://unused", queue_key="jobs")
    first = uuid4()
    second = uuid4()

    assert queue.enqueue(first) is True
    assert queue.enqueue(first) is False
    assert queue.enqueue(second) is True
    assert queue.dequeue() == first
    assert queue.enqueue(first) is True
    assert queue.dequeue(timeout_seconds=1) == second


def test_redis_queue_rejects_invalid_uuid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    fake.lists["jobs"] = deque(["not-a-uuid"])
    fake.sets["jobs:pending"] = {"not-a-uuid"}
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue("redis://unused", queue_key="jobs")

    with pytest.raises(JobQueueError, match="invalid job UUID"):
        queue.dequeue()

    assert "not-a-uuid" not in fake.sets["jobs:pending"]


def test_redis_errors_are_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    fake.fail_operation = "sadd"
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue("redis://unused")

    with pytest.raises(JobQueueError, match="enqueue failed"):
        queue.enqueue(uuid4())


def test_redis_rpush_failure_rolls_back_pending_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis()
    fake.fail_operation = "rpush"
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue("redis://unused")
    job_id = uuid4()

    with pytest.raises(JobQueueError, match="enqueue failed"):
        queue.enqueue(job_id)

    assert str(job_id) not in fake.sets["contractfit:processing_jobs:pending"]


def test_redis_dequeue_accepts_byte_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    fake = FakeRedis()
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue("redis://unused", queue_key="jobs")
    fake.lists["jobs"] = deque([str(job_id).encode("utf-8")])

    assert queue.dequeue() == UUID(str(job_id))


def test_negative_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    install_fake_redis(monkeypatch, fake)
    queue = RedisJobQueue("redis://unused")

    with pytest.raises(ValueError, match="non-negative"):
        queue.dequeue(timeout_seconds=-1)
