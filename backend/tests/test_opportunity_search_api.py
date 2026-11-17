from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contractfit.api import configure_store, router
from contractfit.domain import Opportunity
from contractfit.store import InMemoryStore


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Search Test Facilities",
            "email": "search@example.com",
            "display_name": "Search Tester",
            "password": "a-secure-test-password",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_opportunity_catalog_filters_synchronized_records() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    headers = _register(client)
    today = date.today()

    store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id="ACTIVE-HVAC",
            title="HVAC preventive maintenance",
            agency="Department of Example",
            response_deadline=today + timedelta(days=10),
            set_aside="Total Small Business",
            scope="NAICS 238220",
        )
    )
    store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id="EXPIRED-ROOF",
            title="Roof replacement",
            response_deadline=today - timedelta(days=1),
        )
    )
    store.save_opportunity(
        Opportunity(
            source="uploaded_document",
            source_id="NO-DEADLINE",
            title="Boiler inspection",
        )
    )

    active = client.get(
        "/api/opportunities",
        headers=headers,
        params={
            "q": "hvac 238220",
            "source": "SAM.GOV",
            "deadline_status": "active",
            "has_set_aside": "true",
        },
    )
    assert active.status_code == 200
    assert [item["source_id"] for item in active.json()] == ["ACTIVE-HVAC"]

    expired = client.get(
        "/api/opportunities",
        headers=headers,
        params={"deadline_status": "expired"},
    )
    assert [item["source_id"] for item in expired.json()] == ["EXPIRED-ROOF"]

    unknown = client.get(
        "/api/opportunities",
        headers=headers,
        params={"deadline_status": "unknown"},
    )
    assert [item["source_id"] for item in unknown.json()] == ["NO-DEADLINE"]

    uploaded = client.get(
        "/api/opportunities",
        headers=headers,
        params={"source": "uploaded_document"},
    )
    assert [item["source_id"] for item in uploaded.json()] == ["NO-DEADLINE"]


def test_opportunity_catalog_rejects_invalid_deadline_status() -> None:
    configure_store(InMemoryStore())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    headers = _register(client)

    response = client.get(
        "/api/opportunities",
        headers=headers,
        params={"deadline_status": "soon"},
    )

    assert response.status_code == 422
