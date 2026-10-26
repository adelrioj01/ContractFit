from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
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
from contractfit.embeddings import (
    EmbeddingService,
    EmbeddingSimilarityScorer,
    OllamaEmbeddingProvider,
)
from contractfit.evaluation import (
    EvaluationCase,
    EvaluationReport,
    RankingComparisonReport,
    RankingEvaluationCase,
    compare_rankers,
    evaluate,
)
from contractfit.evaluation_dataset import EVALUATION_CASES, RANKING_EVALUATION_CASES
from contractfit.extraction import RequirementExtractor
from contractfit.file_storage import FileStorageError, LocalFileStorage
from contractfit.job_queue import InMemoryJobQueue, ProcessingJobQueue
from contractfit.matching import OpportunityMatcher
from contractfit.processing import DocumentProcessor
from contractfit.review import ReviewItem, ReviewReason, ReviewStatus
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION
from contractfit.store import ContractFitStore, InMemoryStore

router = APIRouter(prefix="/api")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
_store: ContractFitStore = InMemoryStore()
extractor = RequirementExtractor()
_job_queue: ProcessingJobQueue = InMemoryJobQueue()
_document_processor: DocumentProcessor | None = None
DEMO_EMAIL = "demo@contractfit.local"
DEMO_PASSWORD = "contractfit-demo-password"
DEMO_USER_ID = UUID("cd665135-9ab0-491e-9b65-707c33e429a4")


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
    opportunity_id: UUID | None = None
    field_name: str = Field(min_length=1)
    extracted_value: str | None = None
    confidence: float = Field(ge=0, le=1)
    mandatory: bool = False
    reason: ReviewReason
    evidence: list[Evidence] = Field(min_length=1)


class ResolveReviewRequest(BaseModel):
    corrected_value: str = Field(min_length=1)
    note: str | None = None


class DismissReviewRequest(BaseModel):
    note: str | None = None


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=128)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    organization_id: UUID
    organization_name: str
    role: OrganizationRole


def _token_for(identity: AuthIdentity) -> AccessTokenResponse:
    settings = get_settings()
    return AccessTokenResponse(
        access_token=create_access_token(
            identity,
            settings.auth_secret_key,
            expires_minutes=settings.auth_access_token_minutes,
        )
    )


def get_current_identity(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthIdentity:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token, get_settings().auth_secret_key)
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized from None
    identity = _store.get_identity_by_user_id(claims.sub)
    if (
        identity is None
        or not identity.user.is_active
        or identity.organization.id != claims.organization_id
        or identity.membership.role is not claims.role
    ):
        raise unauthorized
    return identity


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
    seed_demo_identity()
    _store.save_profile(SAMPLE_PROFILE.model_copy(deep=True))
    document = _store.save_document(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sample-hvac-solicitation.txt",
            content=SAMPLE_SOLICITATION,
        )
    )
    _store.save_opportunity(extractor.extract(document, source_id="DEMO-HVAC-001"))


def seed_demo_identity() -> AuthIdentity:
    existing = _store.get_identity_by_email(DEMO_EMAIL)
    if existing is not None:
        return existing
    organization = Organization(
        id=SAMPLE_PROFILE.organization_id,
        name=SAMPLE_PROFILE.name,
    )
    user = UserAccount(
        id=DEMO_USER_ID,
        email=DEMO_EMAIL,
        display_name="Demo reviewer",
        password_hash=hash_password(DEMO_PASSWORD),
    )
    return _store.register_identity(
        AuthIdentity(
            user=user,
            organization=organization,
            membership=OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.ADMIN,
            ),
        )
    )


@router.post("/auth/register", response_model=AccessTokenResponse, status_code=201)
def register(request: RegisterRequest) -> AccessTokenResponse:
    organization = Organization(name=request.organization_name)
    user = UserAccount(
        email=request.email,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
    )
    identity = AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )
    try:
        return _token_for(_store.register_identity(identity))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/auth/token", response_model=AccessTokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> AccessTokenResponse:
    identity = _store.get_identity_by_email(form.username)
    if (
        identity is None
        or not identity.user.is_active
        or not verify_password(form.password, identity.user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_for(identity)


@router.get("/auth/me", response_model=CurrentUserResponse)
def current_user(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=identity.user.id,
        email=identity.user.email,
        display_name=identity.user.display_name,
        organization_id=identity.organization.id,
        organization_name=identity.organization.name,
        role=identity.membership.role,
    )


@router.post("/demo/reset", status_code=201)
def reset_demo(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> dict[str, int]:
    if get_settings().app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if identity.membership.role is not OrganizationRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator role required")
    seed_demo()
    return {
        "profiles": 1,
        "opportunities": len(_store.list_opportunities(identity.organization.id)),
    }


@router.get("/profile", response_model=CompanyProfile)
def get_profile(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> CompanyProfile:
    profile = _store.get_profile(identity.organization.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No contractor profile configured")
    return profile


@router.put("/profile", response_model=CompanyProfile)
def put_profile(
    profile: CompanyProfile,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> CompanyProfile:
    existing = _store.get_profile(identity.organization.id)
    scoped_profile = profile.model_copy(
        update={
            "id": existing.id if existing is not None else uuid4(),
            "organization_id": identity.organization.id,
        }
    )
    return _store.save_profile(scoped_profile)


@router.post("/opportunities/import-text", response_model=Opportunity, status_code=201)
def import_text(
    request: ImportTextRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> Opportunity:
    document = _store.save_document(
        SourceDocument(
            organization_id=identity.organization.id,
            filename=request.filename,
            content=request.content,
        )
    )
    opportunity = extractor.extract(
        document,
        source_id=f"{identity.organization.id}:{request.source_id}",
    )
    return _store.save_opportunity(opportunity)


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: Annotated[UploadFile, File()],
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> DocumentUploadResponse:
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

    organization_id = identity.organization.id
    existing = _store.find_document_by_sha256(stored.sha256, organization_id)
    if existing is not None:
        job = next(
            iter(
                _store.list_processing_jobs(
                    organization_id,
                    document_id=existing.id,
                )
            ),
            None,
        )
        opportunity = next(
            (
                item
                for item in _store.list_opportunities(organization_id)
                if item.document_id == existing.id
            ),
            None,
        )
        return DocumentUploadResponse(
            document=existing, duplicate=True, job=job, opportunity=opportunity
        )

    document = _store.save_document(
        SourceDocument(
            organization_id=organization_id,
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
        document = _store.get_document(document.id, organization_id) or document
        opportunity = next(
            (
                item
                for item in _store.list_opportunities(organization_id)
                if item.document_id == document.id
            ),
            None,
        )
    else:
        _job_queue.enqueue(job.id)
    return DocumentUploadResponse(
        document=document,
        duplicate=False,
        job=job,
        opportunity=opportunity,
    )


@router.get("/documents", response_model=list[SourceDocument])
def list_documents(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[SourceDocument]:
    return _store.list_documents(identity.organization.id)


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPage])
def list_document_pages(
    document_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[DocumentPage]:
    organization_id = identity.organization.id
    document = _store.get_document(document_id, organization_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _store.list_document_pages(document_id, organization_id)


@router.get("/processing-jobs", response_model=list[ProcessingJob])
def list_processing_jobs(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
    document_id: UUID | None = None,
) -> list[ProcessingJob]:
    return _store.list_processing_jobs(
        identity.organization.id,
        document_id=document_id,
    )


@router.get("/processing-jobs/{job_id}", response_model=ProcessingJob)
def get_processing_job(
    job_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ProcessingJob:
    job = _store.get_processing_job(job_id, identity.organization.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job


@router.post("/processing-jobs/{job_id}/retry", response_model=ProcessingJob)
def retry_processing_job(
    job_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ProcessingJob:
    job = get_processing_job(job_id, identity)
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
def list_opportunities(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[Opportunity]:
    return _store.list_opportunities(identity.organization.id)


@router.post("/reviews", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
def create_review(
    request: CreateReviewRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ReviewItem:
    return _store.save_review_item(
        ReviewItem.model_validate(
            {**request.model_dump(), "organization_id": identity.organization.id}
        )
    )


@router.get("/reviews", response_model=list[ReviewItem])
def list_reviews(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
    review_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    opportunity_id: UUID | None = None,
) -> list[ReviewItem]:
    return _store.list_review_items(
        identity.organization.id,
        status=review_status,
        opportunity_id=opportunity_id,
    )


@router.get("/reviews/{review_id}", response_model=ReviewItem)
def get_review(
    review_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ReviewItem:
    item = _store.get_review_item(review_id, identity.organization.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/reviews/{review_id}/resolve", response_model=ReviewItem)
def resolve_review(
    review_id: UUID,
    request: ResolveReviewRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ReviewItem:
    item = get_review(review_id, identity)
    try:
        updated = item.resolve(
            reviewer_id=identity.user.id,
            corrected_value=request.corrected_value,
            note=request.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _store.save_review_item(updated)


@router.post("/reviews/{review_id}/dismiss", response_model=ReviewItem)
def dismiss_review(
    review_id: UUID,
    request: DismissReviewRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ReviewItem:
    item = get_review(review_id, identity)
    try:
        updated = item.dismiss(reviewer_id=identity.user.id, note=request.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _store.save_review_item(updated)


@router.get("/matches", response_model=list[MatchResult])
def list_matches(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[MatchResult]:
    profile = _store.get_profile(identity.organization.id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    matcher = _matcher()
    opportunities = _store.list_opportunities(identity.organization.id)
    settings = get_settings()
    embedding_scores: dict[UUID, float] = {}
    if settings.embedding_provider == "ollama":
        try:
            provider = OllamaEmbeddingProvider(
                settings.ollama_base_url,
                settings.embedding_model,
                settings.embedding_dimensions,
            )
            embedding_scores = EmbeddingService(provider, _store).score_opportunities(
                profile,
                opportunities,
                settings.embedding_match_limit,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            embedding_scores = {}

    results = [
        matcher.match(
            profile,
            item,
            semantic_override=(
                embedding_scores[item.id],
                f"Embedding cosine similarity is {embedding_scores[item.id]:.0%}.",
                f"embedding-cosine:{settings.embedding_model}",
            )
            if item.id in embedding_scores
            else None,
        )
        for item in opportunities
    ]
    return sorted(results, key=lambda item: item.fit_score, reverse=True)


@router.get("/evaluation", response_model=EvaluationReport)
def get_evaluation(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> EvaluationReport:
    profile = _store.get_profile(identity.organization.id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Create a contractor profile first")
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    return evaluate(cases, profile)


@router.get("/evaluation/ranking", response_model=RankingComparisonReport)
def get_ranking_evaluation() -> RankingComparisonReport:
    from contractfit.ai import LexicalSemanticScorer

    cases = [RankingEvaluationCase.model_validate(item) for item in RANKING_EVALUATION_CASES]
    lexical = LexicalSemanticScorer()
    settings = get_settings()
    if settings.embedding_provider != "ollama":
        return compare_rankers(
            cases,
            lexical,
            note="Enable EMBEDDING_PROVIDER=ollama to compare the configured embedding model.",
        )
    try:
        provider = OllamaEmbeddingProvider(
            settings.ollama_base_url,
            settings.embedding_model,
            settings.embedding_dimensions,
        )
        return compare_rankers(cases, lexical, EmbeddingSimilarityScorer(provider))
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return compare_rankers(
            cases,
            lexical,
            note="The configured embedding provider was unavailable; lexical results are shown.",
        )
