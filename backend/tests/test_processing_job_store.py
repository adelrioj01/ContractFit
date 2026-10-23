from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import (
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStage,
    SourceDocument,
)
from contractfit.sql_store import SqlAlchemyStore


def build_store() -> SqlAlchemyStore:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SqlAlchemyStore(build_session_factory(engine))


def test_processing_job_round_trip_and_update() -> None:
    store = build_store()
    document = store.save_document(SourceDocument(filename="notice.txt", content="scope"))
    created_at = datetime.now(UTC) - timedelta(minutes=1)
    job = ProcessingJob(document_id=document.id, created_at=created_at, updated_at=created_at)

    store.save_processing_job(job)
    saved = store.get_processing_job(job.id)

    assert saved is not None
    assert saved.document_id == document.id
    assert saved.status is ProcessingJobStatus.QUEUED
    assert saved.stage is ProcessingStage.PARSING
    assert saved.attempts == 0
    assert saved.max_attempts == 3
    assert saved.created_at == created_at

    updated = job.model_copy(
        update={
            "status": ProcessingJobStatus.PROCESSING,
            "stage": ProcessingStage.OCR,
            "attempts": 1,
            "updated_at": datetime.now(UTC),
        }
    )
    store.save_processing_job(updated)

    saved_update = store.get_processing_job(job.id)
    assert saved_update is not None
    assert saved_update.status is ProcessingJobStatus.PROCESSING
    assert saved_update.stage is ProcessingStage.OCR
    assert saved_update.attempts == 1


def test_processing_job_listing_can_filter_by_document() -> None:
    store = build_store()
    first_document = store.save_document(SourceDocument(filename="first.txt", content="one"))
    second_document = store.save_document(SourceDocument(filename="second.txt", content="two"))
    first_job = ProcessingJob(document_id=first_document.id)
    second_job = ProcessingJob(
        document_id=second_document.id,
        status=ProcessingJobStatus.FAILED,
        error_message="parser failed",
    )
    store.save_processing_job(first_job)
    store.save_processing_job(second_job)

    saved_first_document = store.get_document(first_document.id)
    saved_second_document = store.get_document(second_document.id)
    assert saved_first_document is not None
    assert saved_second_document is not None
    assert saved_first_document.id == first_document.id
    assert saved_second_document.id == second_document.id
    assert {job.id for job in store.list_processing_jobs()} == {first_job.id, second_job.id}
    assert [job.id for job in store.list_processing_jobs(first_document.id)] == [first_job.id]

    store.reset()
    assert store.list_processing_jobs() == []
