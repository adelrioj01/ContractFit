from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from contractfit.api import configure_store, router
from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity, SourceDocument
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


def _client(store: ContractFitStore) -> TestClient:
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _register(client: TestClient, email: str) -> tuple[dict[str, str], UUID]:
    response = client.post(
        "/api/auth/register",
        json={
            "organization_name": f"{email} Facilities",
            "email": email,
            "display_name": "Bid manager",
            "password": "a-secure-test-password",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    current_user = client.get("/api/auth/me", headers=headers)
    assert current_user.status_code == 200
    return headers, UUID(current_user.json()["organization_id"])


@pytest.fixture(params=["memory", "sql"])
def store_context(
    request: pytest.FixtureRequest,
) -> tuple[ContractFitStore, Callable[[], ContractFitStore]]:
    if request.param == "memory":
        store = InMemoryStore()
        return store, lambda: store

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory: Callable[[], Session] = build_session_factory(engine)
    return SqlAlchemyStore(session_factory), lambda: SqlAlchemyStore(session_factory)


def test_feedback_upsert_is_persistent_and_organization_scoped(
    store_context: tuple[ContractFitStore, Callable[[], ContractFitStore]],
) -> None:
    store, rebuild_store = store_context
    client = _client(store)
    owner_headers, _ = _register(client, "feedback-owner@example.com")
    other_headers, _ = _register(client, "feedback-other@example.com")
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="feedback-public", title="HVAC maintenance")
    )
    endpoint = f"/api/opportunities/{opportunity.id}/feedback"

    assert client.get(endpoint).status_code == 401
    assert client.put(endpoint, json={"rating": "relevant"}).status_code == 401

    created = client.put(
        endpoint,
        headers=owner_headers,
        json={"rating": "relevant", "reason": "Strong service and territory fit"},
    )
    assert created.status_code in {200, 201}
    created_payload = created.json()
    assert created_payload["opportunity_id"] == str(opportunity.id)
    assert created_payload["rating"] == "relevant"
    assert created_payload["reason"] == "Strong service and territory fit"
    assert client.get(endpoint, headers=owner_headers).json() == created_payload

    updated = client.put(
        endpoint,
        headers=owner_headers,
        json={"rating": "unsure", "reason": "Needs a capacity review"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == created_payload["id"]
    assert updated.json()["rating"] == "unsure"
    assert updated.json()["reason"] == "Needs a capacity review"

    assert client.get(endpoint, headers=other_headers).status_code == 404
    other_feedback = client.put(
        endpoint,
        headers=other_headers,
        json={"rating": "not_relevant"},
    )
    assert other_feedback.status_code in {200, 201}
    assert other_feedback.json()["id"] != created_payload["id"]
    assert other_feedback.json()["organization_id"] != created_payload["organization_id"]

    reloaded_client = _client(rebuild_store())
    persisted = reloaded_client.get(endpoint, headers=owner_headers)
    assert persisted.status_code == 200
    assert persisted.json()["id"] == created_payload["id"]
    assert persisted.json()["rating"] == "unsure"


def test_feedback_rejects_unknown_and_cross_organization_opportunities(
    store_context: tuple[ContractFitStore, Callable[[], ContractFitStore]],
) -> None:
    store, _ = store_context
    client = _client(store)
    owner_headers, owner_organization_id = _register(client, "private-owner@example.com")
    other_headers, _ = _register(client, "private-other@example.com")
    document = store.save_document(
        SourceDocument(
            organization_id=owner_organization_id,
            filename="private.txt",
            content="Private solicitation",
        )
    )
    opportunity = store.save_opportunity(
        Opportunity(
            source="upload",
            source_id="feedback-private",
            title="Private opportunity",
            document_id=document.id,
        )
    )

    private_endpoint = f"/api/opportunities/{opportunity.id}/feedback"
    assert client.put(
        private_endpoint,
        headers=owner_headers,
        json={"rating": "relevant"},
    ).status_code in {200, 201}
    assert client.get(private_endpoint, headers=other_headers).status_code == 404
    assert client.put(
        private_endpoint,
        headers=other_headers,
        json={"rating": "not_relevant"},
    ).status_code == 404

    unknown_endpoint = f"/api/opportunities/{uuid4()}/feedback"
    assert client.get(unknown_endpoint, headers=owner_headers).status_code == 404
    assert client.put(
        unknown_endpoint,
        headers=owner_headers,
        json={"rating": "relevant"},
    ).status_code == 404


def test_feedback_validates_rating_and_reason() -> None:
    store = InMemoryStore()
    client = _client(store)
    headers, _ = _register(client, "feedback-validation@example.com")
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="feedback-validation", title="Validation")
    )
    endpoint = f"/api/opportunities/{opportunity.id}/feedback"

    assert client.put(
        endpoint,
        headers=headers,
        json={"rating": "maybe"},
    ).status_code == 422
    assert client.put(
        endpoint,
        headers=headers,
        json={"rating": "relevant", "reason": "x" * 1001},
    ).status_code == 422
