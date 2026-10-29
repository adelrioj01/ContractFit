import httpx
import pytest

from contractfit.sam_attachments import SamAttachmentDownloader, SamAttachmentError


def test_downloads_supported_attachment_with_api_key() -> None:
    observed_urls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_urls.append(request.url)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'attachment; filename="solicitation.pdf"',
            },
            content=b"%PDF-test",
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = SamAttachmentDownloader(
        api_key="private-key",
        max_bytes=100,
        timeout_seconds=5,
        client=client,
    )

    result = downloader.download("https://api.sam.gov/resources/file-1")

    assert observed_urls[0].params["api_key"] == "private-key"
    assert result.filename == "solicitation.pdf"
    assert result.content_type == "application/pdf"
    assert result.data == b"%PDF-test"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.sam.gov/resources/file-1",
        "https://sam.gov.example.com/resources/file-1",
        "https://example.com/resources/file-1",
    ],
)
def test_rejects_non_sam_or_insecure_urls(url: str) -> None:
    downloader = SamAttachmentDownloader(
        api_key="private-key",
        max_bytes=100,
        timeout_seconds=5,
    )

    with pytest.raises(SamAttachmentError, match="hosted by SAM.gov"):
        downloader.download(url)


def test_rejects_oversized_or_unsupported_attachments() -> None:
    def oversized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"too-large",
            request=request,
        )

    downloader = SamAttachmentDownloader(
        api_key="private-key",
        max_bytes=3,
        timeout_seconds=5,
        client=httpx.Client(transport=httpx.MockTransport(oversized)),
    )
    with pytest.raises(SamAttachmentError, match="exceeds"):
        downloader.download("https://api.sam.gov/resources/file-1")

    def unsupported(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/zip"},
            content=b"zip",
            request=request,
        )

    downloader = SamAttachmentDownloader(
        api_key="private-key",
        max_bytes=100,
        timeout_seconds=5,
        client=httpx.Client(transport=httpx.MockTransport(unsupported)),
    )
    with pytest.raises(SamAttachmentError, match="Unsupported"):
        downloader.download("https://api.sam.gov/resources/file-1")
