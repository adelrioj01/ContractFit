import logging
import time

from contractfit.config import get_settings
from contractfit.database import build_engine, build_session_factory
from contractfit.domain import ProcessingJobStatus
from contractfit.job_queue import JobQueueError, RedisJobQueue
from contractfit.processing import ProcessingError
from contractfit.runtime import build_document_processor
from contractfit.sql_store import SqlAlchemyStore

logger = logging.getLogger(__name__)


def run_worker() -> None:
    settings = get_settings()
    if settings.storage_backend != "postgres":
        raise RuntimeError("The background worker requires STORAGE_BACKEND=postgres")

    store = SqlAlchemyStore(
        build_session_factory(build_engine(settings.database_url))
    )
    queue = RedisJobQueue.from_url(
        settings.redis_url, queue_key=settings.processing_queue_name
    )
    processor = build_document_processor(settings, store)

    for job in store.list_processing_jobs():
        if job.status in {
            ProcessingJobStatus.QUEUED,
            ProcessingJobStatus.PROCESSING,
        }:
            queue.enqueue(job.id)

    while True:
        try:
            job_id = queue.dequeue(timeout_seconds=5)
        except JobQueueError:
            logger.exception("Unable to dequeue a processing job")
            time.sleep(1)
            continue
        if job_id is None:
            continue
        try:
            result = processor.process(job_id)
        except ProcessingError:
            logger.warning("Discarding stale processing job %s", job_id)
            continue
        if result.status == ProcessingJobStatus.QUEUED:
            queue.enqueue(result.id)


if __name__ == "__main__":
    run_worker()
