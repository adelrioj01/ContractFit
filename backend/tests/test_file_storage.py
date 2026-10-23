import hashlib
from pathlib import Path

import pytest

from contractfit.file_storage import FileStorageError, LocalFileStorage

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_store_uses_hash_path_and_round_trips(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    data = b"%PDF-1.7\ncontract opportunity"
    digest = hashlib.sha256(data).hexdigest()

    stored = storage.store("solicitation.PDF", PDF_TYPE, data)

    assert stored.sha256 == digest
    assert stored.storage_key == f"{digest[:2]}/{digest[2:4]}/{digest}.pdf"
    assert stored.size_bytes == len(data)
    assert stored.original_filename == "solicitation.PDF"
    assert stored.duplicate is False
    assert storage.read(stored.storage_key) == data


def test_duplicate_is_reported_without_rewriting(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    data = b"plain solicitation"
    first = storage.store("notice.txt", "text/plain", data)
    path = tmp_path / Path(*first.storage_key.split("/"))
    original_mtime = path.stat().st_mtime_ns

    second = storage.store("renamed.txt", "text/plain", data)

    assert second.storage_key == first.storage_key
    assert second.original_filename == "renamed.txt"
    assert second.duplicate is True
    assert path.stat().st_mtime_ns == original_mtime


@pytest.mark.parametrize(
    ("filename", "content_type", "data"),
    [
        ("empty.txt", "text/plain", b""),
        ("archive.zip", "application/zip", b"data"),
        ("../notice.pdf", PDF_TYPE, b"data"),
        (r"folder\notice.pdf", PDF_TYPE, b"data"),
        ("notice.pdf.exe", PDF_TYPE, b"data"),
        ("CON.txt", "text/plain", b"data"),
        ("bad\x00name.txt", "text/plain", b"data"),
    ],
)
def test_rejects_invalid_uploads(
    tmp_path: Path, filename: str, content_type: str, data: bytes
) -> None:
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(FileStorageError):
        storage.store(filename, content_type, data)


def test_rejects_oversized_file(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_bytes=3)

    with pytest.raises(FileStorageError, match="exceeds"):
        storage.store("notice.txt", "text/plain", b"four")


def test_all_allowed_content_types_use_fixed_extensions(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    cases = [
        ("notice.pdf", PDF_TYPE, b"pdf", ".pdf"),
        ("notice.docx", DOCX_TYPE, b"docx", ".docx"),
        ("notice.txt", "text/plain", b"text", ".txt"),
    ]

    for filename, content_type, data, extension in cases:
        stored = storage.store(filename, content_type, data)
        assert stored.storage_key.endswith(extension)


@pytest.mark.parametrize(
    "storage_key",
    [
        "../secret.txt",
        "aa/bb/../../secret.txt",
        r"aa\bb\secret.txt",
        "aa/bb/not-a-hash.pdf",
        f"ff/ff/{'a' * 64}.pdf",
    ],
)
def test_read_rejects_invalid_or_traversing_keys(tmp_path: Path, storage_key: str) -> None:
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(FileStorageError, match="Invalid storage key"):
        storage.read(storage_key)


def test_read_rejects_symlink_escape(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "files")
    digest = "a" * 64
    directory = storage.root / "aa"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (directory / "aa").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this platform")

    with pytest.raises(FileStorageError, match="escapes"):
        storage.read(f"aa/aa/{digest}.pdf")
