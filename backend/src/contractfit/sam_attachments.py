from __future__ import annotations

from collections.abc import Iterator
from email.message import Message
from pathlib import Path
from urllib.parse import unquote

import httpx
from pydantic import BaseModel


class SamAttachmentError(RuntimeError):
    """A public SAM attachment could not be downloaded safely."""


class DownloadedSamAttachment(BaseModel):
    filename: str
    content_type: str
    data: bytes


_SUPPORTED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}


class SamAttachmentDownloader:
    def __init__(
        self,
        *,
        api_key: str,
        max_bytes: int,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be blank")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.api_key = api_key
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds
        self.client = client

    def download(self, url: str) -> DownloadedSamAttachment:
        requested_url = _validated_sam_url(url).copy_merge_params(
            {"api_key": self.api_key}
        )
        if self.client is not None:
            return self._download(self.client, requested_url)
        with httpx.Client(follow_redirects=False) as client:
            return self._download(client, requested_url)

    def _download(
        self, client: httpx.Client, url: httpx.URL
    ) -> DownloadedSamAttachment:
        try:
            with client.stream("GET", url, timeout=self.timeout_seconds) as response:
                if response.status_code != 200:
                    raise SamAttachmentError(
                        f"SAM.gov attachment returned HTTP {response.status_code}"
                    )
                _validated_sam_url(str(response.url))
                content_type = response.headers.get("content-type", "").partition(";")[0]
                content_type = content_type.strip().lower()
                extension = _SUPPORTED_CONTENT_TYPES.get(content_type)
                if extension is None:
                    raise SamAttachmentError(
                        f"Unsupported SAM attachment content type: {content_type or 'unknown'}"
                    )
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        raise SamAttachmentError(
                            "SAM.gov attachment has an invalid content length"
                        ) from None
                    if declared_size > self.max_bytes:
                        raise SamAttachmentError(
                            f"SAM.gov attachment exceeds the {self.max_bytes}-byte limit"
                        )
                data = _read_bounded(response.iter_bytes(), self.max_bytes)
                filename = _attachment_filename(response, extension)
        except SamAttachmentError:
            raise
        except (httpx.HTTPError, OSError):
            raise SamAttachmentError("SAM.gov attachment download failed") from None
        return DownloadedSamAttachment(
            filename=filename,
            content_type=content_type,
            data=data,
        )


def _validated_sam_url(url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except (TypeError, ValueError):
        raise SamAttachmentError("Invalid SAM.gov attachment URL") from None
    hostname = (parsed.host or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "sam.gov" or hostname.endswith(".sam.gov")
    ):
        raise SamAttachmentError("Attachment URL is not hosted by SAM.gov")
    return parsed


def _read_bounded(chunks: Iterator[bytes], max_bytes: int) -> bytes:
    data = bytearray()
    for chunk in chunks:
        data.extend(chunk)
        if len(data) > max_bytes:
            raise SamAttachmentError(
                f"SAM.gov attachment exceeds the {max_bytes}-byte limit"
            )
    if not data:
        raise SamAttachmentError("SAM.gov attachment is empty")
    return bytes(data)


def _attachment_filename(response: httpx.Response, extension: str) -> str:
    disposition = response.headers.get("content-disposition")
    filename: str | None = None
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        filename = message.get_filename()
    if not filename:
        filename = Path(unquote(response.url.path)).name
    if not filename or Path(filename).suffix.lower() != extension:
        filename = f"sam-attachment{extension}"
    return filename
