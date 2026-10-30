from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.api import configure_store, router
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity
from contractfit.sam_ingestion import SamOpportunityRecord
from contractfit.sam_models import SamOpportunitySnapshot
from contractfit.sam_sync import normalized_sam_payload
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore
from contractfit.watching import (
    AlertStatus,
    AlertType,
    OpportunityWatch,
    refresh_opportunity_alerts,
)


def make_identity(email: str) -> AuthIdentity:
    organization = Organization(name=f"{email} Facilities")
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


def test_watches_and_alerts_are_isolated_and_deduplicated(store: ContractFitStore) -> None:
    owner = store.register_identity(make_identity("owner@example.com"))
    other = store.register_identity(make_identity("other@example.com"))
    today = date(2026, 10, 30)
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id=str(uuid4()),
            title="Federal chiller maintenance",
            response_deadline=today + timedelta(days=7),
        )
    )
    watch = store.save_opportunity_watch(
        OpportunityWatch(
            organization_id=owner.organization.id,
            opportunity_id=opportunity.id,
        )
    )

    first = refresh_opportunity_alerts(store, owner.organization.id, today=today)
    second = refresh_opportunity_alerts(store, owner.organization.id, today=today)

    assert first == second
    assert len(first) == 1
    assert first[0].watch_id == watch.id
    assert first[0].alert_type is AlertType.DEADLINE_REMINDER
    assert first[0].status is AlertStatus.UNREAD
    assert store.list_opportunity_watches(other.organization.id) == []
    assert refresh_opportunity_alerts(store, other.organization.id, today=today) == []


def test_changed_snapshot_creates_exact_field_diff(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("watcher@example.com"))
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id=str(uuid4()), title="Grounds maintenance")
    )
    observed = datetime(2026, 10, 30, 12, tzinfo=UTC)

    def payload(deadline: datetime, links: tuple[str, ...], title: str) -> dict[str, object]:
        return normalized_sam_payload(
            SamOpportunityRecord(
                notice_id=opportunity.source_id,
                title=title,
                solicitation_number=None,
                department=None,
                agency=None,
                office=None,
                posted_date=None,
                response_deadline=deadline,
                notice_type=None,
                set_aside_code=None,
                set_aside_description=None,
                naics_code=None,
                classification_code=None,
                description_url=None,
                opportunity_url=None,
                resource_links=links,
                active=True,
            )
        )

    store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=opportunity.id,
            content_sha256="a" * 64,
            normalized_payload=payload(
                datetime(2026, 11, 10, 17, tzinfo=UTC),
                ("https://sam.gov/solicitation.pdf",),
                opportunity.title,
            ),
            observed_at=observed,
        )
    )
    store.save_opportunity_watch(
        OpportunityWatch(
            organization_id=identity.organization.id,
            opportunity_id=opportunity.id,
            created_at=observed + timedelta(minutes=1),
        )
    )
    store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=opportunity.id,
            content_sha256="b" * 64,
            normalized_payload=payload(
                datetime(2026, 11, 12, 17, tzinfo=UTC),
                (
                    "https://sam.gov/solicitation.pdf",
                    "https://sam.gov/amendment-1.pdf",
                ),
                opportunity.title,
            ),
            observed_at=observed + timedelta(minutes=2),
        )
    )
    store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=opportunity.id,
            content_sha256="c" * 64,
            normalized_payload=payload(
                datetime(2026, 11, 12, 17, tzinfo=UTC),
                (
                    "https://sam.gov/solicitation.pdf",
                    "https://sam.gov/amendment-1.pdf",
                ),
                "Grounds maintenance - revised",
            ),
            observed_at=observed + timedelta(minutes=3),
        )
    )

    alerts = refresh_opportunity_alerts(store, identity.organization.id, today=date(2026, 10, 30))
    assert {alert.alert_type for alert in alerts} == {
        AlertType.DEADLINE_CHANGED,
        AlertType.ATTACHMENTS_CHANGED,
        AlertType.AMENDMENT,
    }
    refresh_opportunity_alerts(store, identity.organization.id, today=date(2026, 10, 30))
    assert len(store.list_opportunity_alerts(identity.organization.id)) == 3


def test_late_visit_uses_most_recent_deadline_milestone(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("late@example.com"))
    today = date(2026, 10, 30)
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id=str(uuid4()),
            title="Late reminder",
            response_deadline=today + timedelta(days=6),
        )
    )
    store.save_opportunity_watch(
        OpportunityWatch(
            organization_id=identity.organization.id,
            opportunity_id=opportunity.id,
        )
    )
    alerts = refresh_opportunity_alerts(store, identity.organization.id, today=today)
    assert len(alerts) == 1
    assert ":7" in alerts[0].dedupe_key


def test_removing_watch_cascades_alerts_and_allows_rewatch(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity("rewatch@example.com"))
    today = date(2026, 10, 30)
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id=str(uuid4()),
            title="Rewatch opportunity",
            response_deadline=today + timedelta(days=3),
        )
    )
    store.save_opportunity_watch(
        OpportunityWatch(organization_id=identity.organization.id, opportunity_id=opportunity.id)
    )
    assert len(refresh_opportunity_alerts(store, identity.organization.id, today=today)) == 1
    assert store.delete_opportunity_watch(opportunity.id, identity.organization.id)
    assert store.list_opportunity_alerts(identity.organization.id) == []
    store.save_opportunity_watch(
        OpportunityWatch(organization_id=identity.organization.id, opportunity_id=opportunity.id)
    )
    assert len(refresh_opportunity_alerts(store, identity.organization.id, today=today)) == 1


def test_watch_http_routes_require_authentication_and_update_alert() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/watches").status_code == 401
    register = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Alert Facilities",
            "email": "alerts@example.com",
            "display_name": "Alert owner",
            "password": "a-secure-test-password",
        },
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id="alert-http-1",
            title="Boiler inspection",
            response_deadline=date.today() + timedelta(days=3),
        )
    )
    created = client.post(f"/api/watches/{opportunity.id}", headers=headers)
    assert created.status_code == 201
    alerts = client.get("/api/alerts", headers=headers)
    assert alerts.status_code == 200
    assert len(alerts.json()) == 1
    alert_id = alerts.json()[0]["id"]
    updated = client.patch(f"/api/alerts/{alert_id}", headers=headers, json={"status": "resolved"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    assert client.delete(f"/api/watches/{opportunity.id}", headers=headers).status_code == 204
