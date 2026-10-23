from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from contractfit.api import (
    configure_processing,
    configure_store,
    list_document_pages,
    upload_document,
)
from contractfit.config import get_settings
from contractfit.job_queue import InMemoryJobQueue
from contractfit.store import InMemoryStore


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_upload_extracts_page_evidence_and_deduplicates(tmp_path: Path) -> None:
    settings = get_settings()
    previous_directory = settings.upload_directory
    settings.upload_directory = str(tmp_path)
    configure_store(InMemoryStore())
    content = b"\n".join(
        [
            b"Title: Library HVAC Maintenance",
            b"Agency: City of Austin",
            b"Response deadline: 2027-01-15",
            b"Place of performance: Texas",
            b"Estimated value: $125,000",
            b"Scope: Preventive HVAC maintenance",
        ]
    )

    try:
        response = upload_document(make_upload("solicitation.txt", content, "text/plain"))
        assert response.duplicate is False
        assert response.document.status == "ready"
        assert response.document.page_count == 1
        assert response.job is not None
        assert response.job.status == "completed"
        assert response.opportunity is not None
        assert response.opportunity.title == "Library HVAC Maintenance"
        assert response.opportunity.requirements[0].evidence.page == 1

        pages = list_document_pages(response.document.id)
        assert pages[0].text.startswith("Title:")

        duplicate = upload_document(make_upload("solicitation.txt", content, "text/plain"))
        assert duplicate.duplicate is True
        assert duplicate.document.id == response.document.id
    finally:
        settings.upload_directory = previous_directory


def test_upload_rejects_unsupported_type(tmp_path: Path) -> None:
    settings = get_settings()
    previous_directory = settings.upload_directory
    settings.upload_directory = str(tmp_path)
    configure_store(InMemoryStore())

    try:
        with pytest.raises(HTTPException) as error:
            upload_document(
                make_upload("payload.exe", b"not allowed", "application/octet-stream")
            )
        assert error.value.status_code == 422
    finally:
        settings.upload_directory = previous_directory


def test_redis_mode_queues_document_without_processing_request(tmp_path: Path) -> None:
    settings = get_settings()
    previous_directory = settings.upload_directory
    previous_mode = settings.processing_mode
    settings.upload_directory = str(tmp_path)
    settings.processing_mode = "redis"
    queue = InMemoryJobQueue()
    configure_store(InMemoryStore())
    configure_processing(queue)

    try:
        response = upload_document(
            make_upload(
                "notice.txt",
                b"Title: Queued opportunity with enough source text",
                "text/plain",
            )
        )
        assert response.document.status == "uploaded"
        assert response.opportunity is None
        assert response.job is not None
        assert response.job.status == "queued"
        assert queue.dequeue() == response.job.id
    finally:
        settings.upload_directory = previous_directory
        settings.processing_mode = previous_mode
