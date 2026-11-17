from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contractfit.api import (
    configure_sam_attachment_downloader,
    configure_store,
    router,
)
from contractfit.config import get_settings
from contractfit.domain import Opportunity
from contractfit.sam_attachments import DownloadedSamAttachment
from contractfit.sam_models import SamOpportunitySnapshot
from contractfit.store import InMemoryStore


class FakeDownloader:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.version = "original"

    def download(self, url: str) -> DownloadedSamAttachment:
        self.urls.append(url)
        return DownloadedSamAttachment(
            filename="sam-solicitation.txt",
            content_type="text/plain",
            data=b"\n".join(
                [
                    b"Title: SAM HVAC inspection",
                    b"Agency: General Services Administration",
                    b"Response deadline: 2027-02-10",
                    b"Scope: Inspect and maintain commercial HVAC systems.",
                    f"Version: {self.version}".encode(),
                ]
            ),
        )


def _register(client: TestClient, email: str, organization: str) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_lists_and_analyzes_versioned_sam_attachment_per_organization(
    tmp_path: Path,
) -> None:
    settings = get_settings()
    previous_directory = settings.upload_directory
    previous_mode = settings.processing_mode
    settings.upload_directory = str(tmp_path)
    settings.processing_mode = "inline"
    store = InMemoryStore()
    configure_store(store)
    downloader = FakeDownloader()
    configure_sam_attachment_downloader(downloader)
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id="notice-attachment-test",
            title="SAM HVAC inspection",
        )
    )
    resource_url = "https://api.sam.gov/resources/solicitation.txt"
    store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=opportunity.id,
            content_sha256="a" * 64,
            normalized_payload={
                "resource_links": ["https://[", "relative/file.txt", resource_url]
            },
        )
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    try:
        first_headers = _register(client, "first-sam@example.com", "First SAM User")
        second_headers = _register(client, "second-sam@example.com", "Second SAM User")

        attachments = client.get(
            f"/api/opportunities/{opportunity.id}/attachments",
            headers=first_headers,
        )
        assert attachments.status_code == 200
        assert len(attachments.json()) == 1
        attachment = attachments.json()[0]
        assert attachment["url"] == resource_url

        first = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=first_headers,
        )
        assert first.status_code == 201
        assert first.json()["duplicate"] is False
        assert first.json()["document"]["origin_opportunity_id"] == str(opportunity.id)
        assert first.json()["document"]["origin_url"] == resource_url
        assert first.json()["document"]["origin_snapshot_sha256"] == "a" * 64
        assert first.json()["job"]["status"] == "completed"

        duplicate = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=first_headers,
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["duplicate"] is True
        assert duplicate.json()["document"]["id"] == first.json()["document"]["id"]

        second = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=second_headers,
        )
        assert second.status_code == 201
        assert second.json()["duplicate"] is False
        assert second.json()["document"]["organization_id"] != first.json()["document"][
            "organization_id"
        ]
        assert downloader.urls == [resource_url, resource_url]

        store.save_sam_snapshot(
            SamOpportunitySnapshot(
                opportunity_id=opportunity.id,
                content_sha256="b" * 64,
                normalized_payload={"resource_links": [resource_url]},
            )
        )
        downloader.version = "amended"
        amended = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=first_headers,
        )
        assert amended.status_code == 201
        assert amended.json()["duplicate"] is False
        assert amended.json()["document"]["origin_snapshot_sha256"] == "b" * 64
        assert downloader.urls == [resource_url, resource_url, resource_url]

        store.save_sam_snapshot(
            SamOpportunitySnapshot(
                opportunity_id=opportunity.id,
                content_sha256="c" * 64,
                normalized_payload={"resource_links": [resource_url]},
            )
        )
        same_bytes = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=first_headers,
        )
        assert same_bytes.status_code == 201
        assert same_bytes.json()["duplicate"] is True
        assert same_bytes.json()["document"]["id"] == amended.json()["document"]["id"]
        assert downloader.urls == [resource_url, resource_url, resource_url, resource_url]

        repeated = client.post(
            f"/api/opportunities/{opportunity.id}/attachments/{attachment['id']}/analyze",
            headers=first_headers,
        )
        assert repeated.status_code == 201
        assert repeated.json()["document"]["id"] == same_bytes.json()["document"]["id"]
        assert downloader.urls == [resource_url, resource_url, resource_url, resource_url]
    finally:
        configure_sam_attachment_downloader(None)
        settings.upload_directory = previous_directory
        settings.processing_mode = previous_mode
