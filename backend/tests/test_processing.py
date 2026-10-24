from pathlib import Path

from contractfit.domain import (
    DocumentPage,
    DocumentStatus,
    Opportunity,
    ProcessingJob,
    ProcessingJobStatus,
    SourceDocument,
)
from contractfit.extraction import RequirementExtractor
from contractfit.file_storage import LocalFileStorage
from contractfit.processing import DocumentProcessor
from contractfit.sample_data import SAMPLE_PROFILE
from contractfit.store import InMemoryStore


class LowConfidenceExtractor(RequirementExtractor):
    def extract(
        self,
        document: SourceDocument,
        source_id: str,
        pages: list[DocumentPage] | None = None,
    ) -> Opportunity:
        opportunity = super().extract(document, source_id, pages)
        opportunity.requirements = [
            requirement.model_copy(update={"confidence": 0.4})
            for requirement in opportunity.requirements
        ]
        return opportunity


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


def test_processor_creates_review_for_low_confidence_requirement(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    content = b"Title: HVAC contract\nResponse deadline: 2027-02-01"
    stored = storage.store("notice.txt", "text/plain", content)
    store = InMemoryStore()
    store.save_profile(SAMPLE_PROFILE.model_copy(deep=True))
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
    processor = DocumentProcessor(store, storage, extractor=LowConfidenceExtractor())

    processor.process(job.id)

    reviews = store.list_review_items(SAMPLE_PROFILE.organization_id)
    assert len(reviews) == 1
    assert reviews[0].opportunity_id == store.list_opportunities()[0].id
    assert reviews[0].evidence[0].document_id == document.id
