"""Organization-owned relevance feedback for catalog opportunities."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FeedbackRating(StrEnum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    UNSURE = "unsure"


class OpportunityFeedback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    rating: FeedbackRating
    reason: str | None = Field(default=None, max_length=1000)
    submitted_by_user_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
