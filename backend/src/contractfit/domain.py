from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NEEDS_REVIEW = "needs_review"


class Evidence(BaseModel):
    document_id: UUID
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    supporting_text: str


class SourceDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    content: str
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Requirement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    category: str
    description: str
    mandatory: bool
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


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
    capability_statement: str = ""


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
