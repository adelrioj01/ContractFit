from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any, Protocol

from contractfit.domain import Opportunity
from contractfit.sam_ingestion import (
    SamIngestionError,
    SamOpportunityPage,
    SamOpportunityRecord,
)
from contractfit.sam_models import (
    SamIngestionRun,
    SamIngestionStatus,
    SamOpportunitySnapshot,
)
from contractfit.store import ContractFitStore

SAM_SOURCE = "sam.gov"


class SamOpportunitySource(Protocol):
    def query_active_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        limit: int = 100,
        offset: int = 0,
    ) -> SamOpportunityPage: ...


class SamSyncError(RuntimeError):
    """Raised after a failed synchronization has been recorded safely."""


class SamIngestionService:
    def __init__(
        self,
        source: SamOpportunitySource,
        store: ContractFitStore,
        *,
        page_size: int = 100,
    ) -> None:
        if not 1 <= page_size <= 1_000:
            raise ValueError("page_size must be between 1 and 1000")
        self.source = source
        self.store = store
        self.page_size = page_size

    def synchronize(self, *, posted_from: date, posted_to: date) -> SamIngestionRun:
        run = self.store.save_sam_ingestion_run(
            SamIngestionRun(posted_from=posted_from, posted_to=posted_to)
        )
        pages_fetched = 0
        records_fetched = 0
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        offset = 0

        try:
            while True:
                page = self.source.query_active_opportunities(
                    posted_from=posted_from,
                    posted_to=posted_to,
                    limit=self.page_size,
                    offset=offset,
                )
                pages_fetched += 1
                records_fetched += len(page.records)
                for record in page.records:
                    outcome = self._persist_record(record)
                    if outcome == "created":
                        created_count += 1
                    elif outcome == "updated":
                        updated_count += 1
                    else:
                        unchanged_count += 1
                if page.next_offset is None:
                    break
                offset = page.next_offset
        except Exception as exc:
            failed = SamIngestionRun.model_validate(
                {
                    **run.model_dump(),
                    "status": SamIngestionStatus.FAILED,
                    "pages_fetched": pages_fetched,
                    "records_fetched": records_fetched,
                    "created_count": created_count,
                    "updated_count": updated_count,
                    "unchanged_count": unchanged_count,
                    "finished_at": datetime.now(UTC),
                    "error_message": _safe_error(exc),
                }
            )
            self.store.save_sam_ingestion_run(failed)
            raise SamSyncError(failed.error_message) from exc

        completed = SamIngestionRun.model_validate(
            {
                **run.model_dump(),
                "status": SamIngestionStatus.COMPLETED,
                "pages_fetched": pages_fetched,
                "records_fetched": records_fetched,
                "created_count": created_count,
                "updated_count": updated_count,
                "unchanged_count": unchanged_count,
                "finished_at": datetime.now(UTC),
            }
        )
        return self.store.save_sam_ingestion_run(completed)

    def _persist_record(self, record: SamOpportunityRecord) -> str:
        payload = normalized_sam_payload(record)
        content_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = self.store.get_opportunity_by_source(SAM_SOURCE, record.notice_id)
        if existing is not None:
            latest = self.store.get_latest_sam_snapshot(existing.id)
            if latest is not None and latest.content_sha256 == content_sha256:
                return "unchanged"

        opportunity = opportunity_from_sam(record, existing=existing)
        self.store.save_opportunity(opportunity)
        self.store.save_sam_snapshot(
            SamOpportunitySnapshot(
                opportunity_id=opportunity.id,
                content_sha256=content_sha256,
                normalized_payload=payload,
            )
        )
        return "created" if existing is None else "updated"


def normalized_sam_payload(record: SamOpportunityRecord) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in asdict(record).items():
        if isinstance(value, (date, datetime)):
            payload[key] = value.isoformat()
        else:
            payload[key] = value
    return payload


def opportunity_from_sam(
    record: SamOpportunityRecord,
    *,
    existing: Opportunity | None = None,
) -> Opportunity:
    scope_parts = [
        value
        for value in (
            f"Solicitation {record.solicitation_number}" if record.solicitation_number else None,
            record.notice_type,
            f"NAICS {record.naics_code}" if record.naics_code else None,
            (
                f"Classification {record.classification_code}"
                if record.classification_code
                else None
            ),
        )
        if value is not None
    ]
    opportunity_data: dict[str, Any] = {
        "source": SAM_SOURCE,
        "source_id": record.notice_id,
        "title": record.title,
        "agency": record.agency or record.department or record.office,
        "response_deadline": (
            record.response_deadline.date() if record.response_deadline else None
        ),
        "set_aside": record.set_aside_description or record.set_aside_code,
        "scope": " · ".join(scope_parts),
        "source_url": record.opportunity_url or record.description_url,
        "requirements": existing.requirements if existing else [],
    }
    if existing is not None:
        return Opportunity(id=existing.id, **opportunity_data)
    return Opportunity(**opportunity_data)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, SamIngestionError):
        return str(exc)[:1_000]
    return f"{type(exc).__name__}: SAM.gov synchronization failed"
