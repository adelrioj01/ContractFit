from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, cast

import httpx

SAM_OPPORTUNITIES_URL = "https://api.sam.gov/opportunities/v2/search"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PAGE_SIZE = 1_000


class SamIngestionError(RuntimeError):
    """Base error exposed by the SAM.gov ingestion boundary."""


class SamRequestError(SamIngestionError):
    """The SAM.gov request failed or returned a non-success status."""


class SamResponseError(SamIngestionError):
    """SAM.gov returned a response that cannot be safely normalized."""


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        timeout: float,
    ) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class SamOpportunityRecord:
    """Stable transport record decoupled from SAM.gov's response structure."""

    notice_id: str
    title: str
    solicitation_number: str | None
    department: str | None
    agency: str | None
    office: str | None
    posted_date: date | None
    response_deadline: datetime | None
    notice_type: str | None
    set_aside_code: str | None
    set_aside_description: str | None
    naics_code: str | None
    classification_code: str | None
    description_url: str | None
    opportunity_url: str | None
    active: bool


@dataclass(frozen=True, slots=True)
class SamOpportunityPage:
    records: tuple[SamOpportunityRecord, ...]
    total_records: int
    limit: int
    offset: int

    @property
    def next_offset(self) -> int | None:
        consumed = self.offset + len(self.records)
        return consumed if self.records and consumed < self.total_records else None


class SamOpportunitiesClient:
    """Small, synchronous adapter for the public SAM opportunities search API."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        api_key: str | None = None,
        base_url: str = SAM_OPPORTUNITIES_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if api_key is not None and not api_key.strip():
            raise ValueError("api_key must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._http_client = http_client
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    def query_active_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        limit: int = 100,
        offset: int = 0,
    ) -> SamOpportunityPage:
        """Fetch one page of active opportunities posted in an inclusive date range."""

        _validate_query(posted_from, posted_to, limit, offset)
        params: dict[str, str | int] = {
            "postedFrom": posted_from.strftime("%m/%d/%Y"),
            "postedTo": posted_to.strftime("%m/%d/%Y"),
            "active": "true",
            "limit": limit,
            "offset": offset,
        }
        if self._api_key is not None:
            params["api_key"] = self._api_key

        try:
            response = self._http_client.get(
                self._base_url,
                params=params,
                timeout=self._timeout_seconds,
            )
        except (httpx.HTTPError, OSError):
            # Do not propagate client exceptions: their URLs can contain the API key.
            raise SamRequestError("SAM.gov request failed") from None

        if not 200 <= response.status_code < 300:
            raise SamRequestError(
                f"SAM.gov request returned HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except (ValueError, TypeError):
            raise SamResponseError("SAM.gov returned invalid JSON") from None
        return _normalize_page(payload, limit=limit, offset=offset)


def _validate_query(
    posted_from: date,
    posted_to: date,
    limit: int,
    offset: int,
) -> None:
    if isinstance(posted_from, datetime) or not isinstance(posted_from, date):
        raise TypeError("posted_from must be a date")
    if isinstance(posted_to, datetime) or not isinstance(posted_to, date):
        raise TypeError("posted_to must be a date")
    if posted_from > posted_to:
        raise ValueError("posted_from must be on or before posted_to")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")


def _normalize_page(payload: Any, *, limit: int, offset: int) -> SamOpportunityPage:
    if not isinstance(payload, Mapping):
        raise SamResponseError("SAM.gov response must be an object")
    data = payload.get("opportunitiesData")
    if not isinstance(data, list):
        raise SamResponseError("SAM.gov response has no opportunitiesData list")

    total_records = _required_non_negative_int(payload.get("totalRecords"), "totalRecords")
    records: list[SamOpportunityRecord] = []
    for index, value in enumerate(data):
        if not isinstance(value, Mapping):
            raise SamResponseError(f"opportunity at index {index} must be an object")
        try:
            records.append(_normalize_record(cast(Mapping[str, Any], value)))
        except SamResponseError as error:
            raise SamResponseError(f"opportunity at index {index}: {error}") from None

    return SamOpportunityPage(
        records=tuple(records),
        total_records=total_records,
        limit=limit,
        offset=offset,
    )


def _normalize_record(raw: Mapping[str, Any]) -> SamOpportunityRecord:
    notice_id = _required_text(raw.get("noticeId"), "noticeId")
    title = _required_text(raw.get("title"), "title")
    return SamOpportunityRecord(
        notice_id=notice_id,
        title=title,
        solicitation_number=_optional_text(raw.get("solicitationNumber")),
        department=_optional_text(raw.get("department")),
        agency=_optional_text(raw.get("subTier")),
        office=_optional_text(raw.get("office")),
        posted_date=_optional_date(raw.get("postedDate"), "postedDate"),
        response_deadline=_optional_datetime(
            raw.get("responseDeadLine"), "responseDeadLine"
        ),
        notice_type=_optional_text(raw.get("type")),
        set_aside_code=_optional_text(raw.get("typeOfSetAside")),
        set_aside_description=_optional_text(raw.get("typeOfSetAsideDescription")),
        naics_code=_optional_text(raw.get("naicsCode")),
        classification_code=_optional_text(raw.get("classificationCode")),
        description_url=_optional_text(raw.get("description")),
        opportunity_url=_optional_text(raw.get("uiLink")),
        active=_optional_bool(raw.get("active"), default=True),
    )


def _required_text(value: Any, field: str) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise SamResponseError(f"{field} must be a non-empty string")
    return normalized


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _required_non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise SamResponseError(f"{field} must be a non-negative integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise SamResponseError(f"{field} must be a non-negative integer") from None
    if normalized < 0:
        raise SamResponseError(f"{field} must be a non-negative integer")
    return normalized


def _optional_date(value: Any, field: str) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise SamResponseError(f"{field} must be an ISO date") from None


def _optional_datetime(value: Any, field: str) -> datetime | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        raise SamResponseError(f"{field} must be an ISO datetime") from None


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise SamResponseError("active must be a boolean")

