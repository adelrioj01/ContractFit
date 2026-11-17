from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.api import UpdateNotificationPreferenceRequest, put_notification_preferences
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity
from contractfit.notifications import (
    DeliveryStatus,
    NotificationDelivery,
    NotificationPreference,
    dispatch_pending,
    materialize_deliveries,
)
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore
from contractfit.watching import AlertType, OpportunityAlert, OpportunityWatch


class RecordingSender:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.recipients: list[str] = []

    def send(self, delivery: NotificationDelivery) -> None:
        self.recipients.append(delivery.recipient_email)
        if self.fail:
            raise OSError("SMTP unavailable")


def make_identity(email: str) -> AuthIdentity:
    organization = Organization(name="Notification Facilities")
    user = UserAccount(email=email, display_name="Bid manager", password_hash="unused")
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest) -> ContractFitStore:
    if request.param == "memory":
        return InMemoryStore()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SqlAlchemyStore(build_session_factory(engine))


def seed_alert(
    store: ContractFitStore,
    identity: AuthIdentity,
    suffix: str = "default",
    created_at: datetime | None = None,
) -> OpportunityAlert:
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id=str(uuid4()), title="Chiller maintenance")
    )
    watch = store.save_opportunity_watch(
        OpportunityWatch(
            organization_id=identity.organization.id,
            opportunity_id=opportunity.id,
        )
    )
    data = {
        "organization_id": identity.organization.id,
        "opportunity_id": opportunity.id,
        "watch_id": watch.id,
        "alert_type": AlertType.DEADLINE_CHANGED,
        "title": "Deadline changed",
        "message": "The deadline moved from November 10 to November 12.",
        "dedupe_key": f"snapshot:test:deadline:{suffix}",
    }
    if created_at is not None:
        data["created_at"] = created_at
        data["updated_at"] = created_at
    return store.save_opportunity_alert(OpportunityAlert.model_validate(data))


def test_enabled_preference_materializes_one_tenant_scoped_delivery(
    store: ContractFitStore,
) -> None:
    identity = store.register_identity(make_identity("owner@example.com"))
    disabled = NotificationPreference(
        organization_id=identity.organization.id,
        recipient_email=identity.user.email,
    )
    store.save_notification_preference(disabled)
    historical = seed_alert(store, identity, "historical")
    assert materialize_deliveries(store, disabled) == []

    enabled = disabled.model_copy(
        update={"enabled": True, "updated_at": historical.created_at + timedelta(seconds=1)}
    )
    store.save_notification_preference(enabled)
    alert = seed_alert(store, identity, "new", created_at=enabled.updated_at + timedelta(seconds=1))
    first = materialize_deliveries(store, enabled)
    second = materialize_deliveries(store, enabled)
    assert first == second
    assert len(first) == 1
    assert first[0].alert_id == alert.id
    assert first[0].recipient_email == "owner@example.com"
    assert "Chiller maintenance" in first[0].body


def test_dispatch_records_success_and_bounded_failure(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("dispatch@example.com"))
    preference = store.save_notification_preference(
        NotificationPreference(
            organization_id=identity.organization.id,
            enabled=True,
            recipient_email=identity.user.email,
        )
    )
    seed_alert(store, identity)
    materialize_deliveries(store, preference)
    failing = RecordingSender(fail=True)
    failed = dispatch_pending(store, failing, max_attempts=1)
    assert failed[0].status is DeliveryStatus.FAILED
    assert failed[0].attempts == 1
    assert dispatch_pending(store, failing, max_attempts=1) == []

    failed_delivery = failed[0].model_copy(update={"status": DeliveryStatus.PENDING, "attempts": 0})
    store.save_notification_delivery(failed_delivery)
    sender = RecordingSender()
    sent = dispatch_pending(store, sender)
    assert sent[0].status is DeliveryStatus.SENT
    assert sent[0].sent_at is not None
    assert sender.recipients == ["dispatch@example.com"]


def test_alert_type_preferences_filter_delivery(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("filter@example.com"))
    preference = store.save_notification_preference(
        NotificationPreference(
            organization_id=identity.organization.id,
            enabled=True,
            recipient_email=identity.user.email,
            alert_types=[AlertType.ATTACHMENTS_CHANGED],
        )
    )
    seed_alert(store, identity)
    assert materialize_deliveries(store, preference) == []


def test_disabling_preference_cancels_claimed_delivery(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("cancel@example.com"))
    preference = store.save_notification_preference(
        NotificationPreference(
            organization_id=identity.organization.id,
            enabled=True,
            recipient_email=identity.user.email,
        )
    )
    seed_alert(store, identity)
    materialize_deliveries(store, preference)
    store.save_notification_preference(preference.model_copy(update={"enabled": False}))
    sender = RecordingSender()
    results = dispatch_pending(store, sender)
    assert results[0].status is DeliveryStatus.CANCELLED
    assert sender.recipients == []


def test_delivery_claim_prevents_two_workers_from_taking_same_row(
    store: ContractFitStore,
) -> None:
    identity = store.register_identity(make_identity("claim@example.com"))
    preference = store.save_notification_preference(
        NotificationPreference(
            organization_id=identity.organization.id,
            enabled=True,
            recipient_email=identity.user.email,
        )
    )
    seed_alert(store, identity)
    materialize_deliveries(store, preference)
    first_claim = store.claim_notification_deliveries(max_attempts=3)
    second_claim = store.claim_notification_deliveries(max_attempts=3)
    assert len(first_claim) == 1
    assert first_claim[0].status is DeliveryStatus.PROCESSING
    assert second_claim == []


def test_only_admin_can_change_organization_notifications(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("reviewer@example.com"))
    reviewer = identity.model_copy(
        update={
            "membership": identity.membership.model_copy(update={"role": OrganizationRole.REVIEWER})
        }
    )
    with pytest.raises(HTTPException) as error:
        put_notification_preferences(
            UpdateNotificationPreferenceRequest(
                enabled=True, recipient_email="outside@example.com"
            ),
            reviewer,
        )
    assert error.value.status_code == 403


@pytest.mark.parametrize(
    "invalid", ["missing-domain@", "a@b", "victim@example.com\nBcc:other@example.com"]
)
def test_recipient_validation_rejects_malformed_addresses(invalid: str) -> None:
    with pytest.raises(ValueError):
        NotificationPreference(organization_id=uuid4(), recipient_email=invalid)
