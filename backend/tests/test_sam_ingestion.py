from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from contractfit.sam_ingestion import (
    SamOpportunitiesClient,
    SamRequestError,
    SamResponseError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeHttpClient:
    def __init__(
        self, response: FakeResponse | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, Mapping[str, str | int], float]] = []

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append((url, params, timeout))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _payload() -> dict[str, Any]:
    return {
        "totalRecords": 3,
        "opportunitiesData": [
            {
                "noticeId": "notice-123",
                "title": "  Janitorial services  ",
                "solicitationNumber": "SOL-42",
                "department": "GENERAL SERVICES ADMINISTRATION",
                "subTier": "PUBLIC BUILDINGS SERVICE",
                "office": "PBS R7",
                "postedDate": "2026-10-01",
                "responseDeadLine": "2026-11-04T17:00:00Z",
                "type": "Solicitation",
                "typeOfSetAside": "SBA",
                "typeOfSetAsideDescription": "Total Small Business Set-Aside",
                "naicsCode": "561720",
                "classificationCode": "S201",
                "description": "https://sam.gov/api/prod/opps/v3/opportunities/resources",
                "uiLink": "https://sam.gov/opp/notice-123/view",
                "active": "true",
            }
        ],
    }


def test_queries_active_opportunities_and_normalizes_record() -> None:
    http = FakeHttpClient(FakeResponse(200, _payload()))
    client = SamOpportunitiesClient(http, api_key="secret-key", timeout_seconds=9)

    page = client.query_active_opportunities(
        posted_from=date(2026, 10, 1),
        posted_to=date(2026, 10, 23),
        limit=1,
        offset=1,
    )

    _, params, timeout = http.calls[0]
    assert params == {
        "postedFrom": "10/01/2026",
        "postedTo": "10/23/2026",
        "active": "true",
        "limit": 1,
        "offset": 1,
        "api_key": "secret-key",
    }
    assert timeout == 9
    assert page.total_records == 3
    assert page.next_offset == 2
    record = page.records[0]
    assert record.notice_id == "notice-123"
    assert record.title == "Janitorial services"
    assert record.agency == "PUBLIC BUILDINGS SERVICE"
    assert record.posted_date == date(2026, 10, 1)
    assert record.response_deadline == datetime(
        2026, 11, 4, 17, tzinfo=UTC
    )
    assert record.active is True


def test_optional_fields_are_normalized_without_sam_shape_leaking() -> None:
    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "totalRecords": "1",
                "opportunitiesData": [
                    {"noticeId": "n-1", "title": "Bridge inspection", "active": False}
                ],
            },
        )
    )

    record = SamOpportunitiesClient(http).query_active_opportunities(
        posted_from=date(2026, 1, 1), posted_to=date(2026, 1, 1)
    ).records[0]

    assert record.solicitation_number is None
    assert record.response_deadline is None
    assert record.active is False


@pytest.mark.parametrize("limit", [0, 1001, True])
def test_rejects_invalid_page_size_without_calling_http(limit: int) -> None:
    http = FakeHttpClient()

    with pytest.raises(ValueError, match="limit"):
        SamOpportunitiesClient(http).query_active_opportunities(
            posted_from=date(2026, 1, 1),
            posted_to=date(2026, 1, 2),
            limit=limit,
        )

    assert http.calls == []


def test_rejects_invalid_date_range_and_offset() -> None:
    http = FakeHttpClient()
    client = SamOpportunitiesClient(http)

    with pytest.raises(ValueError, match="posted_from"):
        client.query_active_opportunities(
            posted_from=date(2026, 2, 1), posted_to=date(2026, 1, 1)
        )
    with pytest.raises(ValueError, match="offset"):
        client.query_active_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 2, 1), offset=-1
        )
    assert http.calls == []


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "must be an object"),
        ({"totalRecords": 1}, "opportunitiesData"),
        ({"totalRecords": "bad", "opportunitiesData": []}, "totalRecords"),
        (
            {"totalRecords": 1, "opportunitiesData": [{"title": "Missing ID"}]},
            "index 0: noticeId",
        ),
        (
            {
                "totalRecords": 1,
                "opportunitiesData": [
                    {"noticeId": "n", "title": "Bad date", "postedDate": "tomorrow"}
                ],
            },
            "postedDate",
        ),
    ],
)
def test_rejects_malformed_responses(payload: Any, message: str) -> None:
    client = SamOpportunitiesClient(FakeHttpClient(FakeResponse(200, payload)))

    with pytest.raises(SamResponseError, match=message):
        client.query_active_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 1, 2)
        )


def test_invalid_json_is_a_response_error() -> None:
    client = SamOpportunitiesClient(
        FakeHttpClient(FakeResponse(200, ValueError("decoder details")))
    )

    with pytest.raises(SamResponseError, match="invalid JSON"):
        client.query_active_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 1, 2)
        )


def test_http_failure_does_not_expose_api_key() -> None:
    api_key = "do-not-leak-this-key"
    request = httpx.Request("GET", f"https://example.test?api_key={api_key}")
    client = SamOpportunitiesClient(
        FakeHttpClient(error=httpx.RequestError("request failed", request=request)),
        api_key=api_key,
    )

    with pytest.raises(SamRequestError) as captured:
        client.query_active_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 1, 2)
        )

    assert api_key not in str(captured.value)
    assert captured.value.__cause__ is None


def test_non_success_status_is_a_sanitized_request_error() -> None:
    client = SamOpportunitiesClient(
        FakeHttpClient(FakeResponse(429, {"message": "quota exceeded"})),
        api_key="secret",
    )

    with pytest.raises(SamRequestError, match="HTTP 429") as captured:
        client.query_active_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 1, 2)
        )

    assert "secret" not in str(captured.value)


def test_last_page_has_no_next_offset() -> None:
    payload = _payload()
    payload["totalRecords"] = 2
    page = SamOpportunitiesClient(FakeHttpClient(FakeResponse(200, payload))).query_active_opportunities(
        posted_from=date(2026, 1, 1),
        posted_to=date(2026, 1, 2),
        limit=1,
        offset=1,
    )

    assert page.next_offset is None

