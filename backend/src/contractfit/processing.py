from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from contractfit.document_parser import DocumentParser
from contractfit.domain import (
    DocumentPage,
    DocumentStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStage,
)
from contractfit.extraction import RequirementExtractor
from contractfit.file_storage import LocalFileStorage
from contractfit.ocr import DocumentOcrProcessor, OcrError
from contractfit.review import build_requirement_reviews
from contractfit.store import ContractFitStore


class ProcessingError(RuntimeError):
    """Raised when a requested processing job or document does not exist."""


class DocumentProcessor:
    """Run the idempotent document parsing, OCR, and extraction pipeline."""

    def __init__(
        self,
        store: ContractFitStore,
        file_storage: LocalFileStorage,
        *,
        parser: DocumentParser | None = None,
        extractor: RequirementExtractor | None = None,
        ocr: DocumentOcrProcessor | None = None,
    ) -> None:
        self.store = store
        self.file_storage = file_storage
        self.parser = parser or DocumentParser()
        self.extractor = extractor or RequirementExtractor()
        self.ocr = ocr

    def process(self, job_id: UUID) -> ProcessingJob:
        job = self.store.get_processing_job(job_id)
        if job is None:
            raise ProcessingError(f"Processing job {job_id} does not exist")
        if job.status in {
            ProcessingJobStatus.COMPLETED,
            ProcessingJobStatus.NEEDS_REVIEW,
        }:
            return job

        document = self.store.get_document(job.document_id)
        if document is None or document.storage_key is None:
            return self._fail(
                job.model_copy(update={"attempts": job.attempts + 1}),
                "Source document or stored file is unavailable",
            )

        job = self._save_job(
            job,
            status=ProcessingJobStatus.PROCESSING,
            stage=ProcessingStage.PARSING,
            attempts=job.attempts + 1,
            error_message=None,
        )
        self.store.save_document(document.model_copy(update={"status": DocumentStatus.PROCESSING}))

        try:
            data = self.file_storage.read(document.storage_key)
            parsed_pages = self.parser.parse(document.filename, document.content_type, data)
            pages = [
                DocumentPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                    needs_ocr=page.needs_ocr,
                )
                for page in parsed_pages
            ]

            ocr_error: str | None = None
            if any(page.needs_ocr for page in pages) and self.ocr is not None:
                job = self._save_job(job, stage=ProcessingStage.OCR)
                try:
                    pages = self.ocr.process(data, pages)
                except OcrError as exc:
                    ocr_error = str(exc)

            job = self._save_job(job, stage=ProcessingStage.EXTRACTION)
            has_text = any(page.text.strip() for page in pages)
            requires_review = any(page.needs_ocr for page in pages) or not has_text
            document = document.model_copy(
                update={
                    "content": "\n\n".join(page.text for page in pages),
                    "page_count": len(pages),
                    "status": (
                        DocumentStatus.NEEDS_OCR if requires_review else DocumentStatus.READY
                    ),
                    "error_message": ocr_error,
                }
            )
            self.store.save_document(document)
            self.store.save_document_pages(pages)

            if has_text:
                source_id = (
                    f"UPLOAD-{str(document.organization_id)[:8].upper()}-"
                    f"{(document.sha256 or str(document.id))[:12].upper()}"
                )
                opportunity = self.extractor.extract(document, source_id=source_id, pages=pages)
                existing = next(
                    (
                        item
                        for item in self.store.list_opportunities(document.organization_id)
                        if item.document_id == document.id
                    ),
                    None,
                )
                if existing is not None:
                    opportunity.id = existing.id
                self.store.save_opportunity(opportunity)
                profile = self.store.get_profile(document.organization_id)
                if profile is not None:
                    existing_fields = {
                        item.field_name
                        for item in self.store.list_review_items(
                            profile.organization_id,
                            opportunity_id=opportunity.id,
                        )
                    }
                    for review in build_requirement_reviews(
                        opportunity, profile.organization_id
                    ):
                        if review.field_name not in existing_fields:
                            self.store.save_review_item(review)

            return self._save_job(
                job,
                status=(
                    ProcessingJobStatus.NEEDS_REVIEW
                    if requires_review
                    else ProcessingJobStatus.COMPLETED
                ),
                error_message=ocr_error,
            )
        except Exception as exc:  # noqa: BLE001 - job boundary must persist every failure
            return self._fail(job, str(exc))

    def _fail(self, job: ProcessingJob, message: str) -> ProcessingJob:
        terminal = job.attempts >= job.max_attempts
        updated = self._save_job(
            job,
            status=(ProcessingJobStatus.FAILED if terminal else ProcessingJobStatus.QUEUED),
            error_message=message,
        )
        document = self.store.get_document(job.document_id)
        if document is not None:
            self.store.save_document(
                document.model_copy(
                    update={
                        "status": (
                            DocumentStatus.FAILED if terminal else DocumentStatus.UPLOADED
                        ),
                        "error_message": message,
                    }
                )
            )
        return updated

    def _save_job(self, job: ProcessingJob, **updates: object) -> ProcessingJob:
        updates["updated_at"] = datetime.now(UTC)
        return self.store.save_processing_job(job.model_copy(update=updates))
