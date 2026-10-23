from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel


class FileStorageError(ValueError):
    """Raised when a file cannot be safely accepted or retrieved."""


class StoredFile(BaseModel):
    sha256: str
    storage_key: str
    size_bytes: int
    content_type: str
    original_filename: str
    duplicate: bool


_CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}
_STORAGE_KEY_PATTERN = re.compile(
    r"^(?P<first>[0-9a-f]{2})/(?P<second>[0-9a-f]{2})/"
    r"(?P<digest>[0-9a-f]{64})(?P<extension>\.pdf|\.docx|\.txt)$"
)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_RESERVED_CHARACTERS = set('<>:"|?*')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class LocalFileStorage:
    def __init__(self, root: Path, max_bytes: int = 20 * 1024 * 1024) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.root = root.resolve()
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, filename: str, content_type: str, data: bytes) -> StoredFile:
        safe_filename = self._validate_filename(filename, content_type)
        if not data:
            raise FileStorageError("File is empty")
        if len(data) > self.max_bytes:
            raise FileStorageError(f"File exceeds the {self.max_bytes}-byte limit")

        extension = _CONTENT_TYPE_EXTENSIONS.get(content_type)
        if extension is None:
            raise FileStorageError(f"Unsupported content type: {content_type}")

        digest = hashlib.sha256(data).hexdigest()
        storage_key = f"{digest[:2]}/{digest[2:4]}/{digest}{extension}"
        destination = self._path_for_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.is_file():
            return self._result(
                digest, storage_key, data, content_type, safe_filename, duplicate=True
            )

        temporary = destination.parent / f".upload-{uuid4().hex}.tmp"
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())

            try:
                # A hard link publishes the completed file atomically without replacing
                # a file another worker may have stored concurrently.
                os.link(temporary, destination)
                duplicate = False
            except FileExistsError:
                duplicate = True
            except PermissionError:
                # Sandboxed Windows environments may disallow hard links. An exclusive
                # create preserves the no-overwrite/deduplication guarantee there.
                try:
                    destination_descriptor = os.open(
                        destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    )
                except FileExistsError:
                    duplicate = True
                else:
                    with os.fdopen(destination_descriptor, "wb") as destination_handle:
                        destination_handle.write(data)
                        destination_handle.flush()
                        os.fsync(destination_handle.fileno())
                    duplicate = False
        except OSError as exc:
            raise FileStorageError("Unable to store file") from exc
        finally:
            temporary.unlink(missing_ok=True)

        return self._result(
            digest, storage_key, data, content_type, safe_filename, duplicate=duplicate
        )

    def read(self, storage_key: str) -> bytes:
        path = self._path_for_key(storage_key)
        try:
            return path.read_bytes()
        except (FileNotFoundError, IsADirectoryError) as exc:
            raise FileStorageError("Stored file does not exist") from exc
        except OSError as exc:
            raise FileStorageError("Unable to read stored file") from exc

    def _path_for_key(self, storage_key: str) -> Path:
        match = _STORAGE_KEY_PATTERN.fullmatch(storage_key)
        if match is None:
            raise FileStorageError("Invalid storage key")
        digest = match.group("digest")
        if match.group("first") != digest[:2] or match.group("second") != digest[2:4]:
            raise FileStorageError("Invalid storage key")

        path = (self.root / Path(*storage_key.split("/"))).resolve()
        if self.root not in path.parents:
            raise FileStorageError("Storage key escapes the storage root")
        return path

    @staticmethod
    def _validate_filename(filename: str, content_type: str) -> str:
        name = filename.strip()
        if not name or name in {".", ".."}:
            raise FileStorageError("Filename is required")
        if len(name) > 255:
            raise FileStorageError("Filename is too long")
        if "/" in name or "\\" in name or _CONTROL_CHARACTERS.search(name):
            raise FileStorageError("Filename contains unsafe characters")
        if any(character in _WINDOWS_RESERVED_CHARACTERS for character in name):
            raise FileStorageError("Filename contains unsafe characters")
        if name.endswith((".", " ")):
            raise FileStorageError("Filename has an unsafe suffix")
        if name.split(".", maxsplit=1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise FileStorageError("Filename is reserved")

        expected_extension = _CONTENT_TYPE_EXTENSIONS.get(content_type)
        if expected_extension is None:
            raise FileStorageError(f"Unsupported content type: {content_type}")
        if Path(name).suffix.lower() != expected_extension:
            raise FileStorageError("Filename extension does not match content type")
        return name

    @staticmethod
    def _result(
        digest: str,
        storage_key: str,
        data: bytes,
        content_type: str,
        filename: str,
        *,
        duplicate: bool,
    ) -> StoredFile:
        return StoredFile(
            sha256=digest,
            storage_key=storage_key,
            size_bytes=len(data),
            content_type=content_type,
            original_filename=filename,
            duplicate=duplicate,
        )
