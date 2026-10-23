from datetime import date
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


class Opportunity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: str
    source_id: str
    title: str
    response_deadline: date | None = None
    place_of_performance: str | None = None
    requirements: list[Requirement] = Field(default_factory=list)
