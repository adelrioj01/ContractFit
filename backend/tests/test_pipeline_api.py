from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.api import (
    CreatePipelineItemRequest,
    UpdatePipelineItemRequest,
    configure_store,
    create_pipeline_item,
    list_pipeline_items,
    router,
    update_pipeline_item,
)
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity
from contractfit.pipeline import PipelineStatus
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


def make_identity(email: str) -> AuthIdentity:
    organization = Organization(name=f"{email} Facilities")
    user = UserAccount(
        email=email,
        display_name="Bid manager",
        password_hash="not-used",
    )
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


def test_pipeline_create_update_and_list_are_persistent(
    store: ContractFitStore,
) -> None:
    configure_store(store)
    identity = store.register_identity(make_identity("owner@example.com"))
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="real-1", title="HVAC maintenance")
    )

    item = create_pipeline_item(
        CreatePipelineItemRequest(
            opportunity_id=opportunity.id,
            next_action="Review the statement of work",
        ),
        identity,
    )

    assert item.organization_id == identity.organization.id
    assert item.owner_user_id == identity.user.id
    assert item.status is PipelineStatus.NEW
    assert list_pipeline_items(identity) == [item]

    updated = update_pipeline_item(
        item.id,
        UpdatePipelineItemRequest(
            status=PipelineStatus.EVALUATING,
            next_action="Confirm technician availability",
            notes="Good territory fit",
        ),
        identity,
    )

    assert updated.status is PipelineStatus.EVALUATING
    assert updated.next_action == "Confirm technician availability"
    assert updated.notes == "Good territory fit"
    assert list_pipeline_items(identity) == [updated]


def test_pipeline_prevents_duplicates_and_cross_organization_access(
    store: ContractFitStore,
) -> None:
    configure_store(store)
    owner = store.register_identity(make_identity("owner@example.com"))
    other = store.register_identity(make_identity("other@example.com"))
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id=str(uuid4()), title="Boiler service")
    )
    item = create_pipeline_item(
        CreatePipelineItemRequest(opportunity_id=opportunity.id), owner
    )

    with pytest.raises(HTTPException) as duplicate_error:
        create_pipeline_item(CreatePipelineItemRequest(opportunity_id=opportunity.id), owner)
    assert duplicate_error.value.status_code == 409

    assert list_pipeline_items(other) == []
    with pytest.raises(HTTPException) as access_error:
        update_pipeline_item(
            item.id,
            UpdatePipelineItemRequest(status=PipelineStatus.NO_GO),
            other,
        )
    assert access_error.value.status_code == 404


def test_pipeline_http_routes_require_authentication_and_round_trip() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/pipeline/items").status_code == 401

    register = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Pipeline Facilities",
            "email": "pipeline@example.com",
            "display_name": "Pipeline owner",
            "password": "a-secure-test-password",
        },
    )
    assert register.status_code == 201
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="http-1", title="Chiller service")
    )

    created = client.post(
        "/api/pipeline/items",
        headers=headers,
        json={"opportunity_id": str(opportunity.id)},
    )
    assert created.status_code == 201

    updated = client.patch(
        f"/api/pipeline/items/{created.json()['id']}",
        headers=headers,
        json={"status": "pursue", "next_action": "Schedule site visit"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "pursue"
    invalid = client.patch(
        f"/api/pipeline/items/{created.json()['id']}",
        headers=headers,
        json={"status": None},
    )
    assert invalid.status_code == 422
    assert client.get("/api/pipeline/items", headers=headers).json() == [updated.json()]
