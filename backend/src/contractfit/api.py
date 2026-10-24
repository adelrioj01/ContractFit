from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from contractfit.config import get_settings
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    DocumentStatus,
    Evidence,
    MatchResult,
    Opportunity,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStage,
    SourceDocument,
)
from contractfit.evaluation import EvaluationCase, EvaluationReport, evaluate
from contractfit.evaluation_dataset import EVALUATION_CASES
from contractfit.extraction import RequirementExtractor
from contractfit.file_storage import FileStorageError, LocalFileStorage
from contractfit.job_queue import InMemoryJobQueue, ProcessingJobQueue
from contractfit.matching import OpportunityMatcher
from contractfit.processing import DocumentProcessor
from contractfit.review import ReviewItem, ReviewReason, ReviewStatus
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION
from contractfit.store import ContractFitStore, InMemoryStore

router = APIRouter(prefix="/api")
_store: ContractFitStore = InMemoryStore()
extractor = RequirementExtractor()
_job_queue: ProcessingJobQueue = InMemoryJobQueue()
_document_processor: DocumentProcessor | None = None


def configure_store(store: ContractFitStore) -> None:
    global _document_processor, _store
    _store = store
    _document_processor = None


def configure_processing(
    queue: ProcessingJobQueue, processor: DocumentProcessor | None = None
) -> None:
    global _document_processor, _job_queue
    _job_queue = queue
    _document_processor = processor


def get_store() -> ContractFitStore:
    return _store


class ImportTextRequest(BaseModel):
    filename: str = "solicitation.txt"
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=20)


class DocumentUploadResponse(BaseModel):
    document: SourceDocument
    duplicate: bool
    job: ProcessingJob | None = None
    opportunity: Opportunity | None = None


class CreateReviewRequest(BaseModel):
    organization_id: UUID
    opportunity_id: UUID | None = None
    field_name: str = Field(min_length=1)
    extracted_value: str | None = None
    confidence: float = Field(ge=0, le=1)
    mandatory: bool = False
    reason: ReviewReason
    evidence: list[Evidence] = Field(min_length=1)


class ResolveReviewRequest(BaseModel):
    organization_id: UUID
    reviewer_id: UUID
    corrected_value: str = Field(min_length=1)
    note: str | None = None


class DismissReviewRequest(BaseModel):
    organization_id: UUID
    reviewer_id: UUID
    note: str | None = None


def _processor() -> DocumentProcessor:
    global _document_processor
    if _document_processor is None:
        settings = get_settings()
        _document_processor = DocumentProcessor(
            _store,
            LocalFileStorage(
                Path(settings.upload_directory), max_bytes=settings.upload_max_bytes
            ),
        )
    return _document_processor


def _matcher() -> OpportunityMatcher:
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from contractfit.ai import OllamaSemanticScorer

        return OpportunityMatcher(
            OllamaSemanticScorer(settings.ollama_base_url, settings.ollama_model)
        )
    return OpportunityMatcher()


def seed_demo() -> None:
    _store.reset()
    _store.save_profile(SAMPLE_PROFILE.model_copy(deep=True))
    document = _store.save_document(
        SourceDocument(filename="sample-hvac-solicitation.txt", content=SAMPLE_SOLICITATION)
    )
    _store.save_opportunity(extractor.extract(document, source_id="DEMO-HVAC-001"))


@router.post("/demo/reset", status_code=201)
def reset_demo() -> dict[str, int]:
    seed_demo()
    return {"profiles": 1, "opportunities": len(_store.list_opportunities())}


@router.get("/profile", response_model=CompanyProfile)
def get_profile() -> CompanyProfile:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="No contractor profile configured")
    return profile


@router.put("/profile", response_model=CompanyProfile)
def put_profile(profile: CompanyProfile) -> CompanyProfile:
    return _store.save_profile(profile)


@router.post("/opportunities/import-text", response_model=Opportunity, status_code=201)
def import_text(request: ImportTextRequest) -> Opportunity:
    document = _store.save_document(
        SourceDocument(filename=request.filename, content=request.content)
    )
    opportunity = extractor.extract(document, source_id=request.source_id)
    return _store.save_opportunity(opportunity)


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(file: Annotated[UploadFile, File()]) -> DocumentUploadResponse:
    settings = get_settings()
    filename = file.filename or ""
    content_type = (file.content_type or "").partition(";")[0].strip().lower()
    data = file.file.read(settings.upload_max_bytes + 1)
    file.file.close()
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.upload_max_bytes}-byte limit",
        )

    try:
        stored = LocalFileStorage(
            Path(settings.upload_directory), max_bytes=settings.upload_max_bytes
        ).store(filename, content_type, data)
    except FileStorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = _store.find_document_by_sha256(stored.sha256)
    if existing is not None:
        job = next(
            iter(_store.list_processing_jobs(document_id=existing.id)),
            None,
        )
        opportunity = next(
            (
                item
                for item in _store.list_opportunities()
                if item.document_id == existing.id
            ),
            None,
        )
        return DocumentUploadResponse(
            document=existing, duplicate=True, job=job, opportunity=opportunity
        )

    document = _store.save_document(
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
    job = _store.save_processing_job(
        ProcessingJob(
            document_id=document.id,
            status=ProcessingJobStatus.QUEUED,
            stage=ProcessingStage.PARSING,
        )
    )
    opportunity = None
    if settings.processing_mode == "inline":
        job = _processor().process(job.id)
        document = _store.get_document(document.id) or document
        opportunity = next(
            (
                item
                for item in _store.list_opportunities()
                if item.document_id == document.id
            ),
            None,
        )
    else:
        _job_queue.enqueue(job.id)
    return DocumentUploadResponse(
        document=document,
        duplicate=stored.duplicate,
        job=job,
        opportunity=opportunity,
    )


@router.get("/documents", response_model=list[SourceDocument])
def list_documents() -> list[SourceDocument]:
    return _store.list_documents()


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPage])
def list_document_pages(document_id: UUID) -> list[DocumentPage]:
    document = _store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _store.list_document_pages(document_id)


@router.get("/processing-jobs", response_model=list[ProcessingJob])
def list_processing_jobs(document_id: UUID | None = None) -> list[ProcessingJob]:
    return _store.list_processing_jobs(document_id=document_id)


@router.get("/processing-jobs/{job_id}", response_model=ProcessingJob)
def get_processing_job(job_id: UUID) -> ProcessingJob:
    job = _store.get_processing_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job


@router.post("/processing-jobs/{job_id}/retry", response_model=ProcessingJob)
def retry_processing_job(job_id: UUID) -> ProcessingJob:
    job = get_processing_job(job_id)
    if job.status not in {
        ProcessingJobStatus.FAILED,
        ProcessingJobStatus.NEEDS_REVIEW,
    }:
        raise HTTPException(status_code=409, detail="Job is not retryable")
    job = _store.save_processing_job(
        job.model_copy(
            update={
                "status": ProcessingJobStatus.QUEUED,
                "stage": ProcessingStage.PARSING,
                "attempts": 0,
                "error_message": None,
                "updated_at": datetime.now(UTC),
            }
        )
    )
    if get_settings().processing_mode == "inline":
        job = _processor().process(job.id)
    else:
        _job_queue.enqueue(job.id)
    return job


@router.get("/opportunities", response_model=list[Opportunity])
def list_opportunities() -> list[Opportunity]:
    return _store.list_opportunities()


@router.post("/reviews", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
def create_review(request: CreateReviewRequest) -> ReviewItem:
    return _store.save_review_item(ReviewItem.model_validate(request.model_dump()))


@router.get("/reviews", response_model=list[ReviewItem])
def list_reviews(
    organization_id: UUID,
    review_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    opportunity_id: UUID | None = None,
) -> list[ReviewItem]:
    return _store.list_review_items(
        organization_id,
        status=review_status,
        opportunity_id=opportunity_id,
    )


@router.get("/reviews/{review_id}", response_model=ReviewItem)
def get_review(review_id: UUID, organization_id: UUID) -> ReviewItem:
    item = _store.get_review_item(review_id, organization_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/reviews/{review_id}/resolve", response_model=ReviewItem)
def resolve_review(review_id: UUID, request: ResolveReviewRequest) -> ReviewItem:
    item = get_review(review_id, request.organization_id)
    try:
        updated = item.resolve(
            reviewer_id=request.reviewer_id,
            corrected_value=request.corrected_value,
            note=request.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _store.save_review_item(updated)


@router.post("/reviews/{review_id}/dismiss", response_model=ReviewItem)
def dismiss_review(review_id: UUID, request: DismissReviewRequest) -> ReviewItem:
    item = get_review(review_id, request.organization_id)
    try:
        updated = item.dismiss(reviewer_id=request.reviewer_id, note=request.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _store.save_review_item(updated)


@router.get("/matches", response_model=list[MatchResult])
def list_matches() -> list[MatchResult]:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    matcher = _matcher()
    return [matcher.match(profile, item) for item in _store.list_opportunities()]


@router.get("/evaluation", response_model=EvaluationReport)
def get_evaluation() -> EvaluationReport:
    profile = _store.get_profile()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    return evaluate(cases, profile)
