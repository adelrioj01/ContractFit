from pathlib import Path

from contractfit.domain import (
    DocumentStatus,
    ProcessingJob,
    ProcessingJobStatus,
    SourceDocument,
)
from contractfit.file_storage import LocalFileStorage
from contractfit.processing import DocumentProcessor
from contractfit.store import InMemoryStore


def test_processor_extracts_document_and_is_idempotent(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    content = b"\n".join(
        [
            b"Title: Courthouse HVAC Maintenance",
            b"Agency: Travis County",
            b"Response deadline: 2027-02-01",
            b"Place of performance: Texas",
            b"Scope: Preventive maintenance",
        ]
    )
    stored = storage.store("notice.txt", "text/plain", content)
    store = InMemoryStore()
    document = store.save_document(
        SourceDocument(
            filename=stored.original_filename,
            content="",
            sha256=stored.sha256,
            storage_key=stored.storage_key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            status=DocumentStatus.UPLOADED,
            page_count=0,
        )
    )
    job = store.save_processing_job(ProcessingJob(document_id=document.id))
    processor = DocumentProcessor(store, storage)

    result = processor.process(job.id)

    assert result.status == ProcessingJobStatus.COMPLETED
    assert result.attempts == 1
    assert store.get_document(document.id).status == DocumentStatus.READY  # type: ignore[union-attr]
    assert store.list_document_pages(document.id)[0].page_number == 1
    assert store.list_opportunities()[0].requirements[0].evidence.page == 1

    repeated = processor.process(job.id)
    assert repeated == result
    assert len(store.list_opportunities()) == 1


def test_processor_retries_then_marks_malformed_document_failed(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    stored = storage.store("broken.pdf", "application/pdf", b"%PDF-not-valid")
    store = InMemoryStore()
    document = store.save_document(
        SourceDocument(
            filename=stored.original_filename,
            content="",
            sha256=stored.sha256,
            storage_key=stored.storage_key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            status=DocumentStatus.UPLOADED,
            page_count=0,
        )
    )
    job = store.save_processing_job(ProcessingJob(document_id=document.id))
    processor = DocumentProcessor(store, storage)

    assert processor.process(job.id).status == ProcessingJobStatus.QUEUED
    assert processor.process(job.id).status == ProcessingJobStatus.QUEUED
    result = processor.process(job.id)

    assert result.status == ProcessingJobStatus.FAILED
    assert result.attempts == 3
    saved_document = store.get_document(document.id)
    assert saved_document is not None
    assert saved_document.status == DocumentStatus.FAILED
    assert saved_document.error_message
