import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal, Protocol
from uuid import UUID, uuid4

import httpx
import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from contractfit.amendments import AmendmentComparison, compare_amendments
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
from contractfit.compliance import (
    BusinessEvidence,
    ComplianceItem,
    ComplianceStatus,
    RequirementPriority,
    compliance_item_from_requirement,
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
    ProfileCompleteness,
    Requirement,
    SourceDocument,
    assess_profile_completeness,
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
from contractfit.file_storage import FileStorageError, LocalFileStorage, StoredFile
from contractfit.job_queue import InMemoryJobQueue, ProcessingJobQueue
from contractfit.matching import OpportunityMatcher
from contractfit.notifications import NotificationDelivery, NotificationPreference
from contractfit.pipeline import PipelineItem, PipelineStatus
from contractfit.processing import DocumentProcessor
from contractfit.review import ReviewItem, ReviewReason, ReviewStatus
from contractfit.sam_attachments import (
    DownloadedSamAttachment,
    SamAttachmentDownloader,
    SamAttachmentError,
)
from contractfit.sample_data import (
    REAL_FEMA_SOLICITATION,
    REAL_FEMA_SOURCE_URL,
    SAMPLE_PROFILE,
    SAMPLE_SOLICITATION,
    SYNTHETIC_COMPANY_SEEDS,
    SYNTHETIC_OPPORTUNITIES,
)
from contractfit.store import ContractFitStore, InMemoryStore
from contractfit.watching import (
    AlertStatus,
    AlertType,
    OpportunityAlert,
    OpportunityWatch,
    refresh_opportunity_alerts,
)

router = APIRouter(prefix="/api")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
_store: ContractFitStore = InMemoryStore()
extractor = RequirementExtractor()
_job_queue: ProcessingJobQueue = InMemoryJobQueue()
_document_processor: DocumentProcessor | None = None
_configured_sam_attachment_downloader: "SamAttachmentSource | None" = None
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


class SamAttachmentSource(Protocol):
    def download(self, url: str) -> DownloadedSamAttachment: ...


def configure_sam_attachment_downloader(
    downloader: SamAttachmentSource | None,
) -> None:
    global _configured_sam_attachment_downloader
    _configured_sam_attachment_downloader = downloader


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


class SamAttachmentReference(BaseModel):
    id: str
    filename: str
    url: str
    observed_at: datetime


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


class CreatePipelineItemRequest(BaseModel):
    opportunity_id: UUID
    status: PipelineStatus = PipelineStatus.NEW
    next_action: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)


class UpdatePipelineItemRequest(BaseModel):
    status: PipelineStatus | None = None
    next_action: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)


class UpdateComplianceItemRequest(BaseModel):
    status: ComplianceStatus | None = None
    priority: RequirementPriority | None = None
    business_evidence: list[BusinessEvidence] | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class OpportunityWorkspace(BaseModel):
    opportunity: Opportunity
    pipeline_item: PipelineItem | None
    compliance_items: list[ComplianceItem]
    documents: list[SourceDocument]


class UpdateOpportunityAlertRequest(BaseModel):
    status: AlertStatus


class UpdateNotificationPreferenceRequest(BaseModel):
    enabled: bool
    recipient_email: str = Field(min_length=3, max_length=320)
    alert_types: list[AlertType] = Field(default_factory=lambda: list(AlertType))


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
            LocalFileStorage(Path(settings.upload_directory), max_bytes=settings.upload_max_bytes),
        )
    return _document_processor


def _sam_attachment_source() -> SamAttachmentSource:
    if _configured_sam_attachment_downloader is not None:
        return _configured_sam_attachment_downloader
    settings = get_settings()
    if not (settings.sam_api_key and settings.sam_api_key.strip()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAM_API_KEY is required to download attachments",
        )
    return SamAttachmentDownloader(
        api_key=settings.sam_api_key,
        max_bytes=settings.upload_max_bytes,
        timeout_seconds=settings.sam_request_timeout_seconds,
    )


def _sam_attachment_references(opportunity_id: UUID) -> list[SamAttachmentReference]:
    snapshot = _store.get_latest_sam_snapshot(opportunity_id)
    if snapshot is None:
        return []
    raw_links = snapshot.normalized_payload.get("resource_links", [])
    if not isinstance(raw_links, (list, tuple)):
        return []
    references: list[SamAttachmentReference] = []
    for index, value in enumerate(raw_links, start=1):
        if not isinstance(value, str) or not value.strip():
            continue
        url = value.strip()
        try:
            parsed_url = httpx.URL(url)
        except httpx.InvalidURL:
            continue
        hostname = (parsed_url.host or "").lower()
        if parsed_url.scheme != "https" or not (
            hostname == "sam.gov" or hostname.endswith(".sam.gov")
        ):
            continue
        filename = Path(parsed_url.path).name or f"SAM attachment {index}"
        references.append(
            SamAttachmentReference(
                id=hashlib.sha256(url.encode("utf-8")).hexdigest(),
                filename=filename,
                url=url,
                observed_at=snapshot.observed_at,
            )
        )
    return references


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
    seed_demo_companies()
    document = _store.save_document(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sample-hvac-solicitation.txt",
            content=SAMPLE_SOLICITATION,
        )
    )
    _store.save_opportunity(extractor.extract(document, source_id="DEMO-HVAC-001"))
    real_document = _store.save_document(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sam-70FB8026Q00000053.txt",
            content=REAL_FEMA_SOLICITATION,
        )
    )
    real_opportunity = extractor.extract(
        real_document, source_id="SAM-70FB8026Q00000053"
    ).model_copy(update={"source_url": REAL_FEMA_SOURCE_URL})
    _store.save_opportunity(real_opportunity)
    seed_synthetic_catalog()


def seed_demo_companies() -> list[AuthIdentity]:
    identities: list[AuthIdentity] = []
    for seed in SYNTHETIC_COMPANY_SEEDS:
        existing = _store.get_identity_by_email(seed.email)
        if existing is None:
            existing = _store.register_identity(
                AuthIdentity(
                    user=UserAccount(
                        id=seed.user_id,
                        email=seed.email,
                        display_name=seed.display_name,
                        password_hash=hash_password(DEMO_PASSWORD),
                    ),
                    organization=Organization(
                        id=seed.profile.organization_id,
                        name=seed.profile.name,
                    ),
                    membership=OrganizationMembership(
                        organization_id=seed.profile.organization_id,
                        user_id=seed.user_id,
                        role=OrganizationRole.ADMIN,
                    ),
                )
            )
        if _store.get_profile(seed.profile.organization_id) is None:
            _store.save_profile(seed.profile.model_copy(deep=True))
        identities.append(existing)
    return identities


def seed_synthetic_catalog() -> None:
    for opportunity in SYNTHETIC_OPPORTUNITIES:
        if _store.get_opportunity_by_source(opportunity.source, opportunity.source_id) is None:
            _store.save_opportunity(opportunity.model_copy(deep=True))


def seed_demo_identity() -> AuthIdentity:
    identity = seed_demo_companies()[0]
    if identity.user.id != DEMO_USER_ID or identity.user.email != DEMO_EMAIL:
        raise RuntimeError("primary demo identity configuration is inconsistent")
    return identity


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
    if (
        identity.user.id != DEMO_USER_ID
        or identity.user.email.casefold() != DEMO_EMAIL.casefold()
        or identity.organization.id != SAMPLE_PROFILE.organization_id
    ):
        raise HTTPException(status_code=403, detail="Demo identity required")
    seed_demo()
    return {
        "profiles": len(SYNTHETIC_COMPANY_SEEDS),
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


@router.get("/profile/completeness", response_model=ProfileCompleteness)
def get_profile_completeness(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ProfileCompleteness:
    profile = _store.get_profile(identity.organization.id)
    if profile is None:
        return ProfileCompleteness(
            percentage=0,
            completed_sections=[],
            missing_sections=[
                "Services",
                "Service territory",
                "Contract capacity",
                "Licenses and certifications",
                "Insurance",
                "Set-aside status",
                "NAICS codes",
                "Capability statement",
                "Past performance",
            ],
        )
    return assess_profile_completeness(profile)


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


def _ingest_stored_document(
    stored: StoredFile,
    organization_id: UUID,
    *,
    origin_opportunity_id: UUID | None = None,
    origin_url: str | None = None,
    origin_snapshot_sha256: str | None = None,
) -> DocumentUploadResponse:
    existing = _store.find_document_by_sha256(stored.sha256, organization_id)
    if existing is not None:
        if origin_opportunity_id and origin_url and origin_snapshot_sha256:
            _store.save_document_origin(
                existing.id,
                origin_opportunity_id,
                origin_url,
                origin_snapshot_sha256,
                organization_id,
            )
        return _existing_document_upload(existing, organization_id)

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
            origin_opportunity_id=origin_opportunity_id,
            origin_url=origin_url,
            origin_snapshot_sha256=origin_snapshot_sha256,
        )
    )
    if origin_opportunity_id and origin_url and origin_snapshot_sha256:
        _store.save_document_origin(
            document.id,
            origin_opportunity_id,
            origin_url,
            origin_snapshot_sha256,
            organization_id,
        )
    job = _store.save_processing_job(
        ProcessingJob(
            document_id=document.id,
            status=ProcessingJobStatus.QUEUED,
            stage=ProcessingStage.PARSING,
        )
    )
    opportunity = None
    if get_settings().processing_mode == "inline":
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


def _existing_document_upload(
    document: SourceDocument, organization_id: UUID
) -> DocumentUploadResponse:
    job = next(
        iter(
            _store.list_processing_jobs(
                organization_id,
                document_id=document.id,
            )
        ),
        None,
    )
    opportunity = next(
        (
            item
            for item in _store.list_opportunities(organization_id)
            if item.document_id == document.id
        ),
        None,
    )
    return DocumentUploadResponse(
        document=document,
        duplicate=True,
        job=job,
        opportunity=opportunity,
    )


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

    return _ingest_stored_document(stored, identity.organization.id)


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
    q: Annotated[str | None, Query(max_length=200)] = None,
    source: Annotated[str | None, Query(max_length=100)] = None,
    deadline_status: Literal["active", "expired", "unknown"] | None = None,
    has_set_aside: bool | None = None,
) -> list[Opportunity]:
    opportunities = _store.list_opportunities(identity.organization.id)
    query_terms = q.casefold().split() if q else []
    normalized_source = source.strip().casefold() if source else None
    today = date.today()

    def matches(item: Opportunity) -> bool:
        searchable_text = " ".join(
            value
            for value in (
                item.title,
                item.agency or "",
                item.scope,
                item.source_id,
                item.set_aside or "",
                item.place_of_performance or "",
            )
        ).casefold()
        if query_terms and not all(term in searchable_text for term in query_terms):
            return False
        if normalized_source and item.source.casefold() != normalized_source:
            return False
        if has_set_aside is not None and bool(item.set_aside) is not has_set_aside:
            return False
        if deadline_status == "active" and (
            item.response_deadline is None or item.response_deadline < today
        ):
            return False
        if deadline_status == "expired" and (
            item.response_deadline is None or item.response_deadline >= today
        ):
            return False
        return not (deadline_status == "unknown" and item.response_deadline is not None)

    return sorted(
        (item for item in opportunities if matches(item)),
        key=lambda item: (
            item.response_deadline is None,
            item.response_deadline or date.max,
            item.title.casefold(),
        ),
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityWorkspace)
def get_opportunity_workspace(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> OpportunityWorkspace:
    organization_id = identity.organization.id
    opportunity = _store.get_opportunity(opportunity_id, organization_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    documents = [
        document
        for document in _store.list_documents(organization_id)
        if document.id == opportunity.document_id
        or document.origin_opportunity_id == opportunity.id
    ]
    return OpportunityWorkspace(
        opportunity=opportunity,
        pipeline_item=_store.get_pipeline_item_by_opportunity(
            opportunity_id, organization_id
        ),
        compliance_items=_store.list_compliance_items(opportunity_id, organization_id),
        documents=documents,
    )


def _requirements_for_snapshot(
    opportunity_id: UUID, snapshot_sha256: str, organization_id: UUID
) -> list[Requirement]:
    document_ids = {
        document.id
        for document in _store.list_documents_by_origin(
            opportunity_id, snapshot_sha256, organization_id
        )
    }
    requirements = [
        requirement
        for opportunity in _store.list_opportunities(organization_id)
        if opportunity.document_id in document_ids
        for requirement in opportunity.requirements
    ]
    return sorted(requirements, key=lambda item: (item.category, item.description, str(item.id)))


@router.get(
    "/opportunities/{opportunity_id}/amendments/compare",
    response_model=AmendmentComparison,
)
def compare_opportunity_amendments(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
    from_snapshot_id: Annotated[UUID | None, Query()] = None,
    to_snapshot_id: Annotated[UUID | None, Query()] = None,
) -> AmendmentComparison:
    _sam_opportunity(opportunity_id, identity)
    snapshots = _store.list_sam_snapshots(opportunity_id)
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=409,
            detail="At least two SAM.gov snapshots are required for comparison",
        )
    by_id = {snapshot.id: snapshot for snapshot in snapshots}
    previous = by_id.get(from_snapshot_id) if from_snapshot_id else snapshots[-2]
    current = by_id.get(to_snapshot_id) if to_snapshot_id else snapshots[-1]
    if previous is None or current is None:
        raise HTTPException(status_code=404, detail="Opportunity snapshot not found")
    organization_id = identity.organization.id
    try:
        return compare_amendments(
            opportunity_id,
            previous,
            current,
            _requirements_for_snapshot(
                opportunity_id, previous.content_sha256, organization_id
            ),
            _requirements_for_snapshot(
                opportunity_id, current.content_sha256, organization_id
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _csv_cell(value: object | None) -> str:
    """Render untrusted text without creating spreadsheet formulas."""

    if value is None:
        return ""
    rendered = str(value)
    if rendered.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{rendered}"
    return rendered


@router.get("/opportunities/{opportunity_id}/compliance/export.csv")
def export_compliance_matrix(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> Response:
    organization_id = identity.organization.id
    opportunity = _store.get_opportunity(opportunity_id, organization_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    documents = {
        document.id: document
        for document in _store.list_documents(organization_id)
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(
        [
            "opportunity_id",
            "opportunity_title",
            "requirement_id",
            "requirement",
            "category",
            "priority",
            "status",
            "owner_user_id",
            "owner_name",
            "owner_email",
            "due_date",
            "business_evidence_json",
            "notes",
            "source_document_id",
            "source_document_filename",
            "source_page",
            "source_section",
            "source_text",
        ]
    )
    for item in _store.list_compliance_items(opportunity_id, organization_id):
        owner = (
            _store.get_identity_by_user_id(item.owner_user_id)
            if item.owner_user_id is not None
            else None
        )
        if owner is not None and owner.organization.id != organization_id:
            owner = None
        document = documents.get(item.source_evidence.document_id)
        business_evidence = json.dumps(
            [entry.model_dump(mode="json") for entry in item.business_evidence],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        writer.writerow(
            [
                item.opportunity_id,
                _csv_cell(opportunity.title),
                item.requirement_id,
                _csv_cell(item.description),
                _csv_cell(item.category),
                item.priority.value,
                item.status.value,
                item.owner_user_id,
                _csv_cell(owner.user.display_name if owner else None),
                _csv_cell(owner.user.email if owner else None),
                item.due_date,
                _csv_cell(business_evidence),
                _csv_cell(item.notes),
                item.source_evidence.document_id,
                _csv_cell(document.filename if document else None),
                item.source_evidence.page,
                _csv_cell(item.source_evidence.section),
                _csv_cell(item.source_evidence.supporting_text),
            ]
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="compliance-{opportunity_id}.csv"'
            )
        },
    )


@router.post(
    "/opportunities/{opportunity_id}/compliance/initialize",
    response_model=list[ComplianceItem],
)
def initialize_compliance_matrix(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[ComplianceItem]:
    organization_id = identity.organization.id
    opportunity = _store.get_opportunity(opportunity_id, organization_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    pipeline_item = _store.get_pipeline_item_by_opportunity(opportunity_id, organization_id)
    allowed_statuses = {
        PipelineStatus.PURSUE,
        PipelineStatus.PREPARING_BID,
        PipelineStatus.SUBMITTED,
    }
    if pipeline_item is None or pipeline_item.status not in allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail="Mark the opportunity as pursue before creating its compliance matrix",
        )
    existing = {
        item.requirement_id: item
        for item in _store.list_compliance_items(opportunity_id, organization_id)
    }
    for requirement in opportunity.requirements:
        if requirement.id not in existing:
            item = compliance_item_from_requirement(
                requirement, organization_id, opportunity_id
            )
            try:
                existing[requirement.id] = _store.save_compliance_item(item)
            except ValueError as exc:
                winner = _store.get_compliance_item_by_requirement(
                    requirement.id, organization_id
                )
                if winner is None:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                existing[requirement.id] = winner
    return sorted(existing.values(), key=lambda item: (item.created_at, str(item.id)))


@router.patch("/compliance/items/{item_id}", response_model=ComplianceItem)
def update_compliance_item(
    item_id: UUID,
    request: UpdateComplianceItemRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ComplianceItem:
    item = _store.get_compliance_item(item_id, identity.organization.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance item not found")
    for field_name in ("status", "priority", "business_evidence"):
        if field_name in request.model_fields_set and getattr(request, field_name) is None:
            raise HTTPException(status_code=422, detail=f"{field_name} cannot be null")
    if request.owner_user_id is not None:
        owner = _store.get_identity_by_user_id(request.owner_user_id)
        if owner is None or owner.organization.id != identity.organization.id:
            raise HTTPException(status_code=404, detail="Owner not found")
    changes = {
        field_name: getattr(request, field_name)
        for field_name in request.model_fields_set
    }
    resulting_status = changes.get("status", item.status)
    resulting_evidence = changes.get("business_evidence", item.business_evidence)
    if resulting_status is ComplianceStatus.COVERED and not resulting_evidence:
        raise HTTPException(
            status_code=422,
            detail="Covered requirements must include business evidence",
        )
    changes["updated_at"] = datetime.now(UTC)
    return _store.save_compliance_item(
        ComplianceItem.model_validate({**item.model_dump(), **changes})
    )


@router.post("/pipeline/items", response_model=PipelineItem, status_code=201)
def create_pipeline_item(
    request: CreatePipelineItemRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> PipelineItem:
    organization_id = identity.organization.id
    if _store.get_opportunity(request.opportunity_id, organization_id) is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if _store.get_pipeline_item_by_opportunity(request.opportunity_id, organization_id) is not None:
        raise HTTPException(status_code=409, detail="Opportunity is already in the pipeline")
    item = PipelineItem(
        organization_id=organization_id,
        opportunity_id=request.opportunity_id,
        status=request.status,
        owner_user_id=identity.user.id,
        next_action=request.next_action,
        notes=request.notes,
    )
    try:
        return _store.save_pipeline_item(item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/pipeline/items", response_model=list[PipelineItem])
def list_pipeline_items(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[PipelineItem]:
    return _store.list_pipeline_items(identity.organization.id)


@router.patch("/pipeline/items/{item_id}", response_model=PipelineItem)
def update_pipeline_item(
    item_id: UUID,
    request: UpdatePipelineItemRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> PipelineItem:
    item = _store.get_pipeline_item(item_id, identity.organization.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Pipeline item not found")
    if "status" in request.model_fields_set and request.status is None:
        raise HTTPException(status_code=422, detail="Pipeline status cannot be null")
    changes = request.model_dump(exclude_unset=True)
    changes["updated_at"] = datetime.now(UTC)
    return _store.save_pipeline_item(item.model_copy(update=changes))


@router.post("/watches/{opportunity_id}", response_model=OpportunityWatch, status_code=201)
def create_opportunity_watch(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> OpportunityWatch:
    organization_id = identity.organization.id
    if _store.get_opportunity(opportunity_id, organization_id) is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if _store.get_opportunity_watch(opportunity_id, organization_id) is not None:
        raise HTTPException(status_code=409, detail="Opportunity is already watched")
    try:
        return _store.save_opportunity_watch(
            OpportunityWatch(organization_id=organization_id, opportunity_id=opportunity_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/watches", response_model=list[OpportunityWatch])
def list_opportunity_watches(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[OpportunityWatch]:
    return _store.list_opportunity_watches(identity.organization.id)


@router.delete("/watches/{opportunity_id}", status_code=204)
def delete_opportunity_watch(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> None:
    if not _store.delete_opportunity_watch(opportunity_id, identity.organization.id):
        raise HTTPException(status_code=404, detail="Opportunity watch not found")


@router.get("/alerts", response_model=list[OpportunityAlert])
def list_opportunity_alerts(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[OpportunityAlert]:
    return refresh_opportunity_alerts(_store, identity.organization.id)


@router.patch("/alerts/{alert_id}", response_model=OpportunityAlert)
def update_opportunity_alert(
    alert_id: UUID,
    request: UpdateOpportunityAlertRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> OpportunityAlert:
    alert = _store.get_opportunity_alert(alert_id, identity.organization.id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Opportunity alert not found")
    return _store.save_opportunity_alert(
        alert.model_copy(update={"status": request.status, "updated_at": datetime.now(UTC)})
    )


@router.get("/notification-preferences", response_model=NotificationPreference)
def get_notification_preferences(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> NotificationPreference:
    existing = _store.get_notification_preference(identity.organization.id)
    return existing or NotificationPreference(
        organization_id=identity.organization.id,
        recipient_email=identity.user.email,
    )


@router.put("/notification-preferences", response_model=NotificationPreference)
def put_notification_preferences(
    request: UpdateNotificationPreferenceRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> NotificationPreference:
    if identity.membership.role is not OrganizationRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Only organization admins can manage notifications"
        )
    existing = _store.get_notification_preference(identity.organization.id)
    now = datetime.now(UTC)
    return _store.save_notification_preference(
        NotificationPreference(
            organization_id=identity.organization.id,
            enabled=request.enabled,
            recipient_email=request.recipient_email,
            alert_types=request.alert_types,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
    )


@router.get("/notification-deliveries", response_model=list[NotificationDelivery])
def list_notification_deliveries(
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[NotificationDelivery]:
    return _store.list_notification_deliveries(identity.organization.id)


def _sam_opportunity(opportunity_id: UUID, identity: AuthIdentity) -> Opportunity:
    opportunity = _store.get_opportunity(opportunity_id, identity.organization.id)
    if opportunity is None or opportunity.source != "sam.gov":
        raise HTTPException(status_code=404, detail="SAM.gov opportunity not found")
    return opportunity


@router.get(
    "/opportunities/{opportunity_id}/attachments",
    response_model=list[SamAttachmentReference],
)
def list_sam_attachments(
    opportunity_id: UUID,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> list[SamAttachmentReference]:
    _sam_opportunity(opportunity_id, identity)
    return _sam_attachment_references(opportunity_id)


@router.post(
    "/opportunities/{opportunity_id}/attachments/{attachment_id}/analyze",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_sam_attachment(
    opportunity_id: UUID,
    attachment_id: str,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> DocumentUploadResponse:
    _sam_opportunity(opportunity_id, identity)
    snapshot = _store.get_latest_sam_snapshot(opportunity_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="SAM.gov attachment not found")
    attachment = next(
        (item for item in _sam_attachment_references(opportunity_id) if item.id == attachment_id),
        None,
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="SAM.gov attachment not found")
    existing = _store.find_document_by_origin(
        opportunity_id,
        attachment.url,
        snapshot.content_sha256,
        identity.organization.id,
    )
    if existing is not None:
        return _existing_document_upload(existing, identity.organization.id)
    try:
        downloaded = _sam_attachment_source().download(attachment.url)
        settings = get_settings()
        stored = LocalFileStorage(
            Path(settings.upload_directory), max_bytes=settings.upload_max_bytes
        ).store(
            downloaded.filename,
            downloaded.content_type,
            downloaded.data,
        )
    except SamAttachmentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ingest_stored_document(
        stored,
        identity.organization.id,
        origin_opportunity_id=opportunity_id,
        origin_url=attachment.url,
        origin_snapshot_sha256=snapshot.content_sha256,
    )


@router.post("/reviews", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
def create_review(
    request: CreateReviewRequest,
    identity: Annotated[AuthIdentity, Depends(get_current_identity)],
) -> ReviewItem:
    organization_id = identity.organization.id
    if (
        request.opportunity_id is not None
        and _store.get_opportunity(request.opportunity_id, organization_id) is None
    ):
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if any(
        _store.get_document(evidence.document_id, organization_id) is None
        for evidence in request.evidence
    ):
        raise HTTPException(status_code=404, detail="Evidence document not found")
    item = ReviewItem.model_validate({**request.model_dump(), "organization_id": organization_id})
    return _store.save_review_item(item)


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
