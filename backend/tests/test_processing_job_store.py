from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import (
    Opportunity,
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
    organization_id = uuid4()
    document = store.save_document(
        SourceDocument(
            organization_id=organization_id,
            filename="notice.txt",
            content="scope",
        )
    )
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
    organization_id = uuid4()
    first_document = store.save_document(
        SourceDocument(
            organization_id=organization_id,
            filename="first.txt",
            content="one",
        )
    )
    second_document = store.save_document(
        SourceDocument(
            organization_id=organization_id,
            filename="second.txt",
            content="two",
        )
    )
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
    assert [
        job.id for job in store.list_processing_jobs(document_id=first_document.id)
    ] == [first_job.id]

    store.reset()
    assert store.list_processing_jobs() == []


def test_documents_and_jobs_are_scoped_by_organization() -> None:
    store = build_store()
    first_organization_id = uuid4()
    second_organization_id = uuid4()
    first_document = store.save_document(
        SourceDocument(
            organization_id=first_organization_id,
            filename="same.txt",
            content="one",
            sha256="a" * 64,
        )
    )
    second_document = store.save_document(
        SourceDocument(
            organization_id=second_organization_id,
            filename="same.txt",
            content="two",
            sha256="a" * 64,
        )
    )
    first_job = store.save_processing_job(ProcessingJob(document_id=first_document.id))
    second_job = store.save_processing_job(ProcessingJob(document_id=second_document.id))
    public_opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="public-1", title="Public opportunity")
    )
    first_opportunity = store.save_opportunity(
        Opportunity(
            source="upload",
            source_id="private-1",
            title="First private opportunity",
            document_id=first_document.id,
        )
    )
    second_opportunity = store.save_opportunity(
        Opportunity(
            source="upload",
            source_id="private-2",
            title="Second private opportunity",
            document_id=second_document.id,
        )
    )

    first_match = store.find_document_by_sha256("a" * 64, first_organization_id)
    second_match = store.find_document_by_sha256("a" * 64, second_organization_id)
    assert first_match is not None
    assert second_match is not None
    assert first_match.id == first_document.id
    assert second_match.id == second_document.id
    assert store.get_document(first_document.id, second_organization_id) is None
    assert store.get_processing_job(first_job.id, second_organization_id) is None
    assert [item.id for item in store.list_documents(first_organization_id)] == [
        first_document.id
    ]
    assert [item.id for item in store.list_processing_jobs(first_organization_id)] == [
        first_job.id
    ]
    assert [item.id for item in store.list_processing_jobs(second_organization_id)] == [
        second_job.id
    ]
    assert {item.id for item in store.list_opportunities(first_organization_id)} == {
        public_opportunity.id,
        first_opportunity.id,
    }
    assert {item.id for item in store.list_opportunities(second_organization_id)} == {
        public_opportunity.id,
        second_opportunity.id,
    }
