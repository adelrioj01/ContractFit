"""Organization-owned bid pipeline records and transitions."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PipelineStatus(StrEnum):
    NEW = "new"
    EVALUATING = "evaluating"
    PURSUE = "pursue"
    NO_GO = "no_go"
    PREPARING_BID = "preparing_bid"
    SUBMITTED = "submitted"


class PipelineItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    status: PipelineStatus = PipelineStatus.NEW
    owner_user_id: UUID | None = None
    next_action: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
