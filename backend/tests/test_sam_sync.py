from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from contractfit.sam_ingestion import (
    SamOpportunityPage,
    SamOpportunityRecord,
    SamRequestError,
)
from contractfit.sam_models import SamIngestionStatus
from contractfit.sam_sync import SamIngestionService, SamSyncError
from contractfit.store import InMemoryStore


def opportunity_record(notice_id: str, title: str) -> SamOpportunityRecord:
    return SamOpportunityRecord(
        notice_id=notice_id,
        title=title,
        solicitation_number=f"SOL-{notice_id}",
        department="General Services Administration",
        agency="Public Buildings Service",
        office="Region 7",
        posted_date=date(2026, 10, 20),
        response_deadline=datetime(2026, 11, 20, 17, tzinfo=UTC),
        notice_type="Solicitation",
        set_aside_code="SBA",
        set_aside_description="Total Small Business Set-Aside",
        naics_code="561720",
        classification_code="S201",
        description_url=f"https://api.sam.gov/{notice_id}",
        opportunity_url=f"https://sam.gov/opp/{notice_id}/view",
        active=True,
    )


class FakeSource:
    def __init__(self, records: list[SamOpportunityRecord]) -> None:
        self.records = records
        self.offsets: list[int] = []

    def query_active_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        limit: int = 100,
        offset: int = 0,
    ) -> SamOpportunityPage:
        self.offsets.append(offset)
        page_records = self.records[offset : offset + limit]
        return SamOpportunityPage(
            records=tuple(page_records),
            total_records=len(self.records),
            limit=limit,
            offset=offset,
        )


class FailingSource:
    def query_active_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        limit: int = 100,
        offset: int = 0,
    ) -> SamOpportunityPage:
        raise SamRequestError("SAM.gov request returned HTTP 429")


def test_sync_paginates_deduplicates_and_records_amendments() -> None:
    store = InMemoryStore()
    source = FakeSource(
        [
            opportunity_record("one", "Cleaning services"),
            opportunity_record("two", "Grounds maintenance"),
            opportunity_record("three", "Window washing"),
        ]
    )
    service = SamIngestionService(source, store, page_size=2)
    date_range = {"posted_from": date(2026, 10, 1), "posted_to": date(2026, 10, 26)}

    first = service.synchronize(**date_range)

    assert source.offsets == [0, 2]
    assert first.status is SamIngestionStatus.COMPLETED
    assert (first.pages_fetched, first.records_fetched) == (2, 3)
    assert (first.created_count, first.updated_count, first.unchanged_count) == (3, 0, 0)
    assert len(store.list_opportunities()) == 3

    source.offsets.clear()
    second = service.synchronize(**date_range)
    assert (second.created_count, second.updated_count, second.unchanged_count) == (0, 0, 3)

    source.records[0] = replace(source.records[0], title="Cleaning services - amended")
    third = service.synchronize(**date_range)
    assert (third.created_count, third.updated_count, third.unchanged_count) == (0, 1, 2)
    amended = store.get_opportunity_by_source("sam.gov", "one")
    assert amended is not None
    assert amended.title == "Cleaning services - amended"
    assert len(store.list_sam_snapshots(amended.id)) == 2
    assert len(store.list_sam_ingestion_runs()) == 3


def test_sync_persists_sanitized_failure() -> None:
    store = InMemoryStore()
    service = SamIngestionService(FailingSource(), store)

    with pytest.raises(SamSyncError, match="HTTP 429"):
        service.synchronize(posted_from=date(2026, 10, 1), posted_to=date(2026, 10, 26))

    run = store.list_sam_ingestion_runs()[0]
    assert run.status is SamIngestionStatus.FAILED
    assert run.finished_at is not None
    assert run.error_message == "SAM.gov request returned HTTP 429"
