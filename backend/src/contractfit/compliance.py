"""Organization-owned compliance matrix records."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from contractfit.domain import Evidence, Requirement


class ComplianceStatus(StrEnum):
    PENDING = "pending"
    COVERED = "covered"
    MISSING_EVIDENCE = "missing_evidence"
    NOT_APPLICABLE = "not_applicable"


class RequirementPriority(StrEnum):
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"


class BusinessEvidence(BaseModel):
    """An explicit user-selected reference; never a generated company claim."""

    kind: str = Field(min_length=1, max_length=50)
    reference_id: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1, max_length=1000)


class ComplianceItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    requirement_id: UUID
    description: str = Field(min_length=1, max_length=4000)
    category: str = Field(min_length=1, max_length=255)
    priority: RequirementPriority
    status: ComplianceStatus = ComplianceStatus.PENDING
    source_evidence: Evidence
    business_evidence: list[BusinessEvidence] = Field(default_factory=list)
    owner_user_id: UUID | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_evidence_for_covered_status(self) -> "ComplianceItem":
        if self.status is ComplianceStatus.COVERED and not self.business_evidence:
            raise ValueError("covered requirements must include business evidence")
        return self


def compliance_item_from_requirement(
    requirement: Requirement, organization_id: UUID, opportunity_id: UUID
) -> ComplianceItem:
    """Create a deterministic editable row while preserving the source citation."""

    return ComplianceItem(
        organization_id=organization_id,
        opportunity_id=opportunity_id,
        requirement_id=requirement.id,
        description=requirement.description,
        category=requirement.category,
        priority=(
            RequirementPriority.MANDATORY
            if requirement.mandatory
            else RequirementPriority.RECOMMENDED
        ),
        source_evidence=requirement.evidence,
    )
