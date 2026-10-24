"""Persistence-agnostic domain models for human review of extracted fields."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from contractfit.domain import Evidence, Opportunity


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReviewReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    MISSING_VALUE = "missing_value"
    CONFLICTING_VALUES = "conflicting_values"
    INVALID_FORMAT = "invalid_format"
    OCR_UNCERTAIN = "ocr_uncertain"
    OTHER = "other"


class ReviewPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_REASON_WEIGHT: dict[ReviewReason, int] = {
    ReviewReason.MISSING_VALUE: 30,
    ReviewReason.CONFLICTING_VALUES: 25,
    ReviewReason.INVALID_FORMAT: 20,
    ReviewReason.OCR_UNCERTAIN: 15,
    ReviewReason.LOW_CONFIDENCE: 10,
    ReviewReason.OTHER: 0,
}


def calculate_priority_score(*, mandatory: bool, confidence: float, reason: ReviewReason) -> int:
    """Return a stable 0-100 urgency score from explicit review inputs."""
    bounded_confidence = min(max(confidence, 0.0), 1.0)
    uncertainty = round((1.0 - bounded_confidence) * 30)
    return min(100, (40 if mandatory else 0) + _REASON_WEIGHT[reason] + uncertainty)


def priority_from_score(score: int) -> ReviewPriority:
    if score >= 75:
        return ReviewPriority.CRITICAL
    if score >= 50:
        return ReviewPriority.HIGH
    if score >= 25:
        return ReviewPriority.MEDIUM
    return ReviewPriority.LOW


class ReviewItem(BaseModel):
    """A field-level decision that requires traceable human judgment."""

    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID | None = None
    field_name: str = Field(min_length=1)
    extracted_value: str | None = None
    confidence: float = Field(ge=0, le=1)
    mandatory: bool = False
    reason: ReviewReason
    evidence: list[Evidence] = Field(min_length=1)
    status: ReviewStatus = ReviewStatus.PENDING
    corrected_value: str | None = None
    reviewer_id: UUID | None = None
    resolution_note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    @field_validator("field_name")
    @classmethod
    def field_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field_name must not be blank")
        return value

    @field_validator("corrected_value", "resolution_note")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("review text must not be blank")
        return value

    @field_validator("created_at", "updated_at", "resolved_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("review timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_review_state(self) -> "ReviewItem":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.resolved_at is not None and self.resolved_at < self.created_at:
            raise ValueError("resolved_at cannot precede created_at")

        decision_fields = (self.reviewer_id, self.resolved_at)
        if self.status is ReviewStatus.PENDING:
            if any(value is not None for value in decision_fields) or any(
                value is not None for value in (self.corrected_value, self.resolution_note)
            ):
                raise ValueError("pending reviews cannot contain resolution data")
        else:
            if self.reviewer_id is None or self.resolved_at is None:
                raise ValueError("terminal reviews require reviewer_id and resolved_at")
            if self.updated_at != self.resolved_at:
                raise ValueError("terminal review updated_at must equal resolved_at")

        if self.status is ReviewStatus.RESOLVED and self.corrected_value is None:
            raise ValueError("resolved reviews require corrected_value")
        if self.status is ReviewStatus.DISMISSED and self.corrected_value is not None:
            raise ValueError("dismissed reviews cannot contain corrected_value")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def priority_score(self) -> int:
        return calculate_priority_score(
            mandatory=self.mandatory,
            confidence=self.confidence,
            reason=self.reason,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def priority(self) -> ReviewPriority:
        return priority_from_score(self.priority_score)

    def resolve(
        self,
        *,
        reviewer_id: UUID,
        corrected_value: str,
        note: str | None = None,
        at: datetime | None = None,
    ) -> "ReviewItem":
        """Return a validated resolved copy; the original remains unchanged."""
        return self._transition(
            status=ReviewStatus.RESOLVED,
            reviewer_id=reviewer_id,
            corrected_value=corrected_value,
            note=note,
            at=at,
        )

    def dismiss(
        self,
        *,
        reviewer_id: UUID,
        note: str | None = None,
        at: datetime | None = None,
    ) -> "ReviewItem":
        """Return a validated dismissed copy; the original remains unchanged."""
        return self._transition(
            status=ReviewStatus.DISMISSED,
            reviewer_id=reviewer_id,
            corrected_value=None,
            note=note,
            at=at,
        )

    def _transition(
        self,
        *,
        status: ReviewStatus,
        reviewer_id: UUID,
        corrected_value: str | None,
        note: str | None,
        at: datetime | None,
    ) -> "ReviewItem":
        if self.status is not ReviewStatus.PENDING:
            raise ValueError(f"cannot transition review from {self.status}")
        transition_time = at or datetime.now(UTC)
        values = self.model_dump()
        values.update(
            status=status,
            reviewer_id=reviewer_id,
            corrected_value=corrected_value,
            resolution_note=note,
            updated_at=transition_time,
            resolved_at=transition_time,
        )
        return type(self).model_validate(values)


def review_sort_key(item: ReviewItem) -> tuple[int, float, datetime, str]:
    """Sort pending work by urgency, uncertainty, age, then stable identity."""
    return (-item.priority_score, item.confidence, item.created_at, str(item.id))


def build_requirement_reviews(
    opportunity: Opportunity,
    organization_id: UUID,
    *,
    confidence_threshold: float = 0.75,
) -> list[ReviewItem]:
    """Create review candidates for uncertain extracted requirements."""
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between zero and one")
    return [
        ReviewItem(
            organization_id=organization_id,
            opportunity_id=opportunity.id,
            field_name=f"requirement:{requirement.id}",
            extracted_value=requirement.description,
            confidence=requirement.confidence,
            mandatory=requirement.mandatory,
            reason=ReviewReason.LOW_CONFIDENCE,
            evidence=[requirement.evidence],
        )
        for requirement in opportunity.requirements
        if requirement.confidence < confidence_threshold
    ]

