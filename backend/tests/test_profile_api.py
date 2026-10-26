from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contractfit.api import configure_store, router
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
