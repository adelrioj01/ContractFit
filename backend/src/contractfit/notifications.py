"""Deterministic email notification outbox for opportunity alerts."""

import re
from datetime import UTC, datetime
from email.message import EmailMessage
from enum import StrEnum
from smtplib import SMTP, SMTPException
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from contractfit.watching import AlertType, OpportunityAlert

if TYPE_CHECKING:
    from contractfit.store import ContractFitStore


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationPreference(BaseModel):
    organization_id: UUID
    enabled: bool = False
    recipient_email: str
    alert_types: list[AlertType] = Field(default_factory=lambda: list(AlertType))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("recipient_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
            normalized,
        ):
            raise ValueError("recipient_email must be valid")
        return normalized


class NotificationDelivery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    alert_id: UUID
    recipient_email: str
    subject: str = Field(max_length=255)
    body: str = Field(max_length=10000)
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = None


def delivery_for_alert(
    preference: NotificationPreference, alert: OpportunityAlert, opportunity_title: str
) -> NotificationDelivery | None:
    if not preference.enabled or alert.alert_type not in preference.alert_types:
        return None
    return NotificationDelivery(
        organization_id=preference.organization_id,
        alert_id=alert.id,
        recipient_email=preference.recipient_email,
        subject=f"ContractFit: {alert.title}",
        body=(
            f"{opportunity_title}\n\n{alert.message}\n\n"
            "Open ContractFit to review the source evidence and next action."
        ),
    )


class EmailSender(Protocol):
    def send(self, delivery: NotificationDelivery) -> None: ...


class SmtpEmailSender:
    def __init__(self, host: str, port: int, sender_email: str) -> None:
        self.host = host
        self.port = port
        self.sender_email = sender_email

    def send(self, delivery: NotificationDelivery) -> None:
        message = EmailMessage()
        message["From"] = self.sender_email
        message["To"] = delivery.recipient_email
        message["Subject"] = delivery.subject
        message.set_content(delivery.body)
        with SMTP(self.host, self.port, timeout=20) as client:
            client.send_message(message)


def materialize_deliveries(
    store: "ContractFitStore", preference: NotificationPreference
) -> list[NotificationDelivery]:
    for alert in store.list_opportunity_alerts(preference.organization_id):
        if alert.created_at < preference.updated_at:
            continue
        if store.get_notification_delivery_by_alert(alert.id, preference.organization_id):
            continue
        opportunity = store.get_opportunity(alert.opportunity_id, preference.organization_id)
        if opportunity is None:
            continue
        delivery = delivery_for_alert(preference, alert, opportunity.title)
        if delivery is not None:
            store.save_notification_delivery(delivery)
    return store.list_notification_deliveries(preference.organization_id)


def dispatch_pending(
    store: "ContractFitStore", sender: EmailSender, *, max_attempts: int = 3
) -> list[NotificationDelivery]:
    results: list[NotificationDelivery] = []
    for delivery in store.claim_notification_deliveries(max_attempts=max_attempts):
        now = datetime.now(UTC)
        preference = store.get_notification_preference(delivery.organization_id)
        alert = store.get_opportunity_alert(delivery.alert_id, delivery.organization_id)
        if (
            preference is None
            or not preference.enabled
            or preference.recipient_email != delivery.recipient_email
            or alert is None
            or alert.alert_type not in preference.alert_types
        ):
            results.append(
                store.save_notification_delivery(
                    delivery.model_copy(
                        update={"status": DeliveryStatus.CANCELLED, "updated_at": now}
                    )
                )
            )
            continue
        try:
            sender.send(delivery)
        except (OSError, SMTPException) as exc:
            updated = delivery.model_copy(
                update={
                    "status": DeliveryStatus.FAILED,
                    "attempts": delivery.attempts + 1,
                    "error_message": str(exc)[:500],
                    "updated_at": now,
                }
            )
        else:
            updated = delivery.model_copy(
                update={
                    "status": DeliveryStatus.SENT,
                    "attempts": delivery.attempts + 1,
                    "error_message": None,
                    "updated_at": now,
                    "sent_at": now,
                }
            )
        results.append(store.save_notification_delivery(updated))
    return results
