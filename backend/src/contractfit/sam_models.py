from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SamIngestionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SamIngestionRun(BaseModel):
    """Auditable result of one bounded SAM.gov catalog synchronization."""

    id: UUID = Field(default_factory=uuid4)
    posted_from: date
    posted_to: date
    status: SamIngestionStatus = SamIngestionStatus.RUNNING
    pages_fetched: int = Field(default=0, ge=0)
    records_fetched: int = Field(default=0, ge=0)
    created_count: int = Field(default=0, ge=0)
    updated_count: int = Field(default=0, ge=0)
    unchanged_count: int = Field(default=0, ge=0)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "SamIngestionRun":
        if self.posted_from > self.posted_to:
            raise ValueError("posted_from must be on or before posted_to")
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        if self.finished_at is not None and (
            self.finished_at.tzinfo is None or self.finished_at.utcoffset() is None
        ):
            raise ValueError("finished_at must be timezone-aware")
        if self.status is SamIngestionStatus.RUNNING:
            if self.finished_at is not None or self.error_message is not None:
                raise ValueError("running ingestion cannot contain terminal data")
        elif self.finished_at is None:
            raise ValueError("terminal ingestion requires finished_at")
        if self.status is SamIngestionStatus.COMPLETED and self.error_message is not None:
            raise ValueError("completed ingestion cannot contain an error")
        if self.status is SamIngestionStatus.FAILED and not self.error_message:
            raise ValueError("failed ingestion requires an error")
        return self


class SamOpportunitySnapshot(BaseModel):
    """Immutable normalized provider state used for amendment detection."""

    id: UUID = Field(default_factory=uuid4)
    opportunity_id: UUID
    content_sha256: str = Field(min_length=64, max_length=64)
    normalized_payload: dict[str, Any]
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def timestamp_must_be_aware(self) -> "SamOpportunitySnapshot":
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return self
