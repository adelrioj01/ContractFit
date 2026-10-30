"""Organization-owned opportunity watches and deterministic alerts."""

from datetime import UTC, date, datetime
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from contractfit.store import ContractFitStore


class AlertType(StrEnum):
    AMENDMENT = "amendment"
    DEADLINE_CHANGED = "deadline_changed"
    DEADLINE_REMINDER = "deadline_reminder"
    ATTACHMENTS_CHANGED = "attachments_changed"


class AlertStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    RESOLVED = "resolved"


class OpportunityWatch(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OpportunityAlert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    watch_id: UUID
    alert_type: AlertType
    status: AlertStatus = AlertStatus.UNREAD
    title: str = Field(max_length=255)
    message: str = Field(max_length=2000)
    changed_fields: dict[str, object] = Field(default_factory=dict)
    dedupe_key: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def snapshot_changes(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    """Return user-relevant SAM fields whose normalized values changed."""
    tracked = {
        "response_deadline": "Deadline",
        "resource_links": "Documents",
        "title": "Title",
        "set_aside_code": "Set-aside",
        "set_aside_description": "Set-aside description",
        "description_url": "Description",
    }
    changes: dict[str, object] = {}
    for key, label in tracked.items():
        before = previous.get(key)
        after = current.get(key)
        if before != after:
            changes[key] = {"label": label, "before": before, "after": after}
    return changes


def deadline_threshold(deadline: date | None, today: date) -> int | None:
    if deadline is None:
        return None
    remaining = (deadline - today).days
    if remaining < 0:
        return None
    return next((threshold for threshold in (1, 3, 7, 14) if remaining <= threshold), None)


def refresh_opportunity_alerts(
    store: "ContractFitStore", organization_id: UUID, *, today: date | None = None
) -> list[OpportunityAlert]:
    """Materialize missing alerts for an organization's watches, without duplicates."""
    effective_today = today or date.today()
    for watch in store.list_opportunity_watches(organization_id):
        opportunity = store.get_opportunity(watch.opportunity_id, organization_id)
        if opportunity is None:
            continue
        threshold = deadline_threshold(opportunity.response_deadline, effective_today)
        if threshold is not None:
            deadline = opportunity.response_deadline
            assert deadline is not None
            days_remaining = (deadline - effective_today).days
            key = f"deadline:{opportunity.id}:{deadline}:{threshold}"
            if store.get_opportunity_alert_by_dedupe_key(key, organization_id) is None:
                store.save_opportunity_alert(
                    OpportunityAlert(
                        organization_id=organization_id,
                        opportunity_id=opportunity.id,
                        watch_id=watch.id,
                        alert_type=AlertType.DEADLINE_REMINDER,
                        title=f"Deadline in {days_remaining} day{'s' if days_remaining != 1 else ''}",
                        message=f"{opportunity.title} is due on {deadline.isoformat()}.",
                        changed_fields={"response_deadline": deadline.isoformat()},
                        dedupe_key=key,
                    )
                )

        snapshots = store.list_sam_snapshots(opportunity.id)
        for previous, current in pairwise(snapshots):
            if current.observed_at <= watch.created_at:
                continue
            changes = snapshot_changes(previous.normalized_payload, current.normalized_payload)
            if not changes:
                continue
            categories: list[tuple[AlertType, str, dict[str, object]]] = []
            deadline_change = changes.get("response_deadline")
            resource_links = changes.get("resource_links")
            remaining = {
                key: value
                for key, value in changes.items()
                if key not in {"response_deadline", "resource_links"}
            }
            if deadline_change is not None:
                categories.append(
                    (
                        AlertType.DEADLINE_CHANGED,
                        "Deadline changed",
                        {"response_deadline": deadline_change},
                    )
                )
            if resource_links is not None:
                categories.append(
                    (
                        AlertType.ATTACHMENTS_CHANGED,
                        "Documents changed",
                        {"resource_links": resource_links},
                    )
                )
            if remaining:
                categories.append((AlertType.AMENDMENT, "Opportunity amended", remaining))
            for alert_type, title, fields in categories:
                key = f"snapshot:{opportunity.id}:{current.content_sha256}:{alert_type.value}"
                if store.get_opportunity_alert_by_dedupe_key(key, organization_id) is None:
                    labels = ", ".join(
                        str(item.get("label", field))
                        for field, item in fields.items()
                        if isinstance(item, dict)
                    )
                    store.save_opportunity_alert(
                        OpportunityAlert(
                            organization_id=organization_id,
                            opportunity_id=opportunity.id,
                            watch_id=watch.id,
                            alert_type=alert_type,
                            title=title,
                            message=f"{opportunity.title}: {labels or 'source details'} changed.",
                            changed_fields=fields,
                            dedupe_key=key,
                            created_at=current.observed_at,
                            updated_at=current.observed_at,
                        )
                    )
    return store.list_opportunity_alerts(organization_id)
