from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contractfit.api import configure_store, router
from contractfit.config import get_settings
from contractfit.store import InMemoryStore


def _register(client: TestClient, email: str, organization: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "organization_name": organization,
            "email": email,
            "display_name": organization,
            "password": "a-secure-test-password",
        },
    )
    assert response.status_code == 201
    return str(response.json()["access_token"])


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_document_routes_require_authentication() -> None:
    configure_store(InMemoryStore())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/processing-jobs").status_code == 401
    assert client.get("/api/opportunities").status_code == 401
    assert client.post(
        "/api/documents/upload",
        files={"file": ("notice.txt", b"Title: Private notice", "text/plain")},
    ).status_code == 401


def test_document_pipeline_is_isolated_by_organization(tmp_path: Path) -> None:
    settings = get_settings()
    previous_directory = settings.upload_directory
    previous_mode = settings.processing_mode
    settings.upload_directory = str(tmp_path)
    settings.processing_mode = "inline"
    configure_store(InMemoryStore())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    content = b"\n".join(
        [
            b"Title: Shared bytes, private records",
            b"Agency: City Facilities",
            b"Response deadline: 2027-04-30",
            b"Place of performance: Texas",
            b"Scope: Preventive maintenance",
        ]
    )

    try:
        first_token = _register(client, "first-docs@example.com", "First Facilities")
        second_token = _register(client, "second-docs@example.com", "Second Facilities")

        first_upload = client.post(
            "/api/documents/upload",
            headers=_authorization(first_token),
            files={"file": ("notice.txt", content, "text/plain")},
        )
        second_upload = client.post(
            "/api/documents/upload",
            headers=_authorization(second_token),
            files={"file": ("notice.txt", content, "text/plain")},
        )

        assert first_upload.status_code == 201
        assert second_upload.status_code == 201
        first_payload = first_upload.json()
        second_payload = second_upload.json()
        assert first_payload["duplicate"] is False
        assert second_payload["duplicate"] is False
        assert first_payload["document"]["id"] != second_payload["document"]["id"]
        assert (
            first_payload["document"]["organization_id"]
            != second_payload["document"]["organization_id"]
        )

        first_documents = client.get(
            "/api/documents", headers=_authorization(first_token)
        ).json()
        second_documents = client.get(
            "/api/documents", headers=_authorization(second_token)
        ).json()
        assert [item["id"] for item in first_documents] == [
            first_payload["document"]["id"]
        ]
        assert [item["id"] for item in second_documents] == [
            second_payload["document"]["id"]
        ]

        first_document_id = first_payload["document"]["id"]
        first_job_id = first_payload["job"]["id"]
        assert client.get(
            f"/api/documents/{first_document_id}/pages",
            headers=_authorization(second_token),
        ).status_code == 404
        assert client.get(
            f"/api/processing-jobs/{first_job_id}",
            headers=_authorization(second_token),
        ).status_code == 404

        first_opportunities = client.get(
            "/api/opportunities", headers=_authorization(first_token)
        ).json()
        second_opportunities = client.get(
            "/api/opportunities", headers=_authorization(second_token)
        ).json()
        assert {item["document_id"] for item in first_opportunities} == {
            first_payload["document"]["id"]
        }
        assert {item["document_id"] for item in second_opportunities} == {
            second_payload["document"]["id"]
        }
    finally:
        settings.upload_directory = previous_directory
        settings.processing_mode = previous_mode
