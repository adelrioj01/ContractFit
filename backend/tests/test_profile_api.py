from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contractfit.api import configure_store, router
from contractfit.domain import CompanyProfile, PastPerformanceProject
from contractfit.sample_data import SAMPLE_PROFILE
from contractfit.store import InMemoryStore


def _registration(email: str, organization_name: str) -> dict[str, str]:
    return {
        "organization_name": organization_name,
        "email": email,
        "display_name": organization_name,
        "password": "a-secure-test-password",
    }


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _profile_payload(name: str) -> dict[str, object]:
    payload = SAMPLE_PROFILE.model_dump(mode="json")
    payload.update(
        {
            "id": str(uuid4()),
            "organization_id": str(uuid4()),
            "name": name,
        }
    )
    return payload


def test_profile_endpoints_require_authentication() -> None:
    configure_store(InMemoryStore())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile/completeness").status_code == 401
    assert client.put("/api/profile", json=_profile_payload("Hidden")).status_code == 401
    assert client.get("/api/matches").status_code == 401
    assert client.get("/api/evaluation").status_code == 401


def test_profiles_are_bound_to_authenticated_organization() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    first_token = client.post(
        "/api/auth/register",
        json=_registration("first@example.com", "First Facilities"),
    ).json()["access_token"]
    second_token = client.post(
        "/api/auth/register",
        json=_registration("second@example.com", "Second Facilities"),
    ).json()["access_token"]
    first_identity = store.get_identity_by_email("first@example.com")
    second_identity = store.get_identity_by_email("second@example.com")
    assert first_identity is not None
    assert second_identity is not None

    first_response = client.put(
        "/api/profile",
        headers=_authorization(first_token),
        json=_profile_payload("First Profile"),
    )
    assert client.get(
        "/api/profile", headers=_authorization(second_token)
    ).status_code == 404
    second_response = client.put(
        "/api/profile",
        headers=_authorization(second_token),
        json=_profile_payload("Second Profile"),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["organization_id"] == str(first_identity.organization.id)
    assert second_response.json()["organization_id"] == str(second_identity.organization.id)
    assert client.get(
        "/api/profile", headers=_authorization(first_token)
    ).json()["name"] == "First Profile"
    assert client.get(
        "/api/profile", headers=_authorization(second_token)
    ).json()["name"] == "Second Profile"
    completeness = client.get(
        "/api/profile/completeness", headers=_authorization(first_token)
    )
    assert completeness.status_code == 200
    assert completeness.json()["percentage"] == 100
    assert completeness.json()["missing_sections"] == []

    replacement_payload = _profile_payload("Updated First Profile")
    replacement_payload["id"] = str(uuid4())
    updated_response = client.put(
        "/api/profile",
        headers=_authorization(first_token),
        json=replacement_payload,
    )
    assert updated_response.json()["id"] == first_response.json()["id"]
    assert client.get(
        "/api/profile", headers=_authorization(second_token)
    ).json()["name"] == "Second Profile"


def test_profile_completeness_reports_missing_customer_evidence() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    token = client.post(
        "/api/auth/register",
        json=_registration("new@example.com", "New Facilities"),
    ).json()["access_token"]
    headers = _authorization(token)

    empty = client.get("/api/profile/completeness", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["percentage"] == 0
    assert "Past performance" in empty.json()["missing_sections"]

    payload = _profile_payload("Partially configured")
    payload["insurance_coverages"] = []
    payload["past_performance"] = []
    saved = client.put("/api/profile", headers=headers, json=payload)
    assert saved.status_code == 200
    partial = client.get("/api/profile/completeness", headers=headers).json()
    assert partial["percentage"] < 100
    assert partial["missing_sections"] == ["Insurance", "Past performance"]


def test_profile_rejects_invalid_capacity_and_project_dates() -> None:
    with pytest.raises(ValidationError, match="maximum_contract_value"):
        CompanyProfile(
            organization_id=uuid4(),
            name="Invalid capacity",
            service_categories=["HVAC"],
            states=["Texas"],
            minimum_contract_value=200000,
            maximum_contract_value=100000,
        )

    with pytest.raises(ValidationError, match="end_date"):
        PastPerformanceProject(
            title="Invalid chronology",
            description="Maintenance work",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 5, 1),
        )
