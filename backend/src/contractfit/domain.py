from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NEEDS_REVIEW = "needs_review"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


class ProcessingJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ProcessingStage(StrEnum):
    PARSING = "parsing"
    OCR = "ocr"
    EXTRACTION = "extraction"


class Evidence(BaseModel):
    document_id: UUID
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    supporting_text: str


class SourceDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    filename: str
    content: str
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    storage_key: str | None = None
    content_type: str = "text/plain"
    size_bytes: int = Field(default=0, ge=0)
    status: DocumentStatus = DocumentStatus.READY
    page_count: int = Field(default=1, ge=0)
    error_message: str | None = None
    origin_opportunity_id: UUID | None = None
    origin_url: str | None = None
    origin_snapshot_sha256: str | None = Field(
        default=None, min_length=64, max_length=64
    )


class DocumentPage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: int = Field(ge=1)
    text: str
    needs_ocr: bool = False


class ProcessingJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    status: ProcessingJobStatus = ProcessingJobStatus.QUEUED
    stage: ProcessingStage = ProcessingStage.PARSING
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Requirement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    category: str
    description: str
    mandatory: bool
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class PastPerformanceProject(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    client: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    service_categories: list[str] = Field(default_factory=list)
    state: str | None = Field(default=None, max_length=100)
    contract_value: Decimal | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    reference_available: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> "PastPerformanceProject":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("past-performance end_date must not precede start_date")
        return self


class CompanyProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    name: str
    service_categories: list[str]
    states: list[str]
    maximum_distance_miles: int | None = Field(default=None, ge=0)
    minimum_contract_value: Decimal | None = Field(default=None, ge=0)
    maximum_contract_value: Decimal | None = Field(default=None, ge=0)
    licenses: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    set_asides: list[str] = Field(default_factory=list)
    naics_codes: list[str] = Field(default_factory=list)
    insurance_coverages: list[str] = Field(default_factory=list)
    contract_preferences: list[str] = Field(default_factory=list)
    past_performance: list[PastPerformanceProject] = Field(default_factory=list)
    capability_statement: str = ""

    @model_validator(mode="after")
    def validate_contract_capacity(self) -> "CompanyProfile":
        if (
            self.minimum_contract_value is not None
            and self.maximum_contract_value is not None
            and self.maximum_contract_value < self.minimum_contract_value
        ):
            raise ValueError(
                "maximum_contract_value must be greater than or equal to minimum_contract_value"
            )
        return self


class ProfileCompleteness(BaseModel):
    percentage: int = Field(ge=0, le=100)
    completed_sections: list[str]
    missing_sections: list[str]


def assess_profile_completeness(profile: CompanyProfile) -> ProfileCompleteness:
    sections = {
        "Services": bool(profile.service_categories),
        "Service territory": bool(profile.states),
        "Contract capacity": (
            profile.minimum_contract_value is not None
            or profile.maximum_contract_value is not None
        ),
        "Licenses and certifications": bool(profile.licenses or profile.certifications),
        "Insurance": bool(profile.insurance_coverages),
        "Set-aside status": bool(profile.set_asides),
        "NAICS codes": bool(profile.naics_codes),
        "Capability statement": bool(profile.capability_statement.strip()),
        "Past performance": bool(profile.past_performance),
    }
    completed = [name for name, present in sections.items() if present]
    missing = [name for name, present in sections.items() if not present]
    return ProfileCompleteness(
        percentage=round(len(completed) / len(sections) * 100),
        completed_sections=completed,
        missing_sections=missing,
    )


class Opportunity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: str
    source_id: str
    title: str
    agency: str | None = None
    response_deadline: date | None = None
    place_of_performance: str | None = None
    set_aside: str | None = None
    estimated_value: Decimal | None = Field(default=None, ge=0)
    scope: str = ""
    source_url: str | None = None
    document_id: UUID | None = None
    requirements: list[Requirement] = Field(default_factory=list)


class GateResult(BaseModel):
    name: str
    status: EligibilityStatus
    reason: str
    evidence: Evidence | None = None


class MatchResult(BaseModel):
    opportunity_id: UUID
    profile_id: UUID
    eligibility: EligibilityStatus
    fit_score: float = Field(ge=0, le=100)
    scoring_method: str
    gates: list[GateResult]
    strengths: list[str]
    gaps: list[str]
    explanation: str
