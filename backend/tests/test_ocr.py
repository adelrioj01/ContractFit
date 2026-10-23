from __future__ import annotations

import subprocess
from typing import Any
from uuid import uuid4

import pymupdf
import pytest

from contractfit.domain import DocumentPage
from contractfit.ocr import DocumentOcrProcessor, OcrError, TesseractOcrEngine


def _pdf_with_different_page_sizes() -> bytes:
    document = pymupdf.open()
    document.new_page(width=200, height=300)
    document.new_page(width=400, height=300)
    data = document.tobytes()
    document.close()
    return data


class FakeOcrEngine:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.images: list[bytes] = []

    def extract_text(self, image: bytes) -> str:
        self.images.append(image)
        return next(self.responses)


def test_processes_only_flagged_page_and_preserves_identity() -> None:
    document_id = uuid4()
    normal = DocumentPage(
        document_id=document_id,
        page_number=1,
        text="Already searchable",
        needs_ocr=False,
    )
    scanned = DocumentPage(
        document_id=document_id,
        page_number=2,
        text="",
        needs_ocr=True,
    )
    engine = FakeOcrEngine(["Recovered requirement text"])

    result = DocumentOcrProcessor(engine, render_dpi=72).process(
        _pdf_with_different_page_sizes(), [normal, scanned]
    )

    assert len(engine.images) == 1
    rendered = pymupdf.open(stream=engine.images[0], filetype="png")
    assert rendered[0].rect.width == pytest.approx(400)
    rendered.close()
    assert result[0] == normal
    assert result[0] is not normal
    assert result[1].id == scanned.id
    assert result[1].document_id == scanned.document_id
    assert result[1].page_number == 2
    assert result[1].text == "Recovered requirement text"
    assert result[1].needs_ocr is False


def test_empty_ocr_result_keeps_page_pending_and_retains_existing_text() -> None:
    page = DocumentPage(
        document_id=uuid4(), page_number=1, text="scan", needs_ocr=True
    )

    result = DocumentOcrProcessor(FakeOcrEngine(["  "])).process(
        _pdf_with_different_page_sizes(), [page]
    )

    assert result[0].text == "scan"
    assert result[0].needs_ocr is True


def test_skips_opening_pdf_when_no_page_needs_ocr() -> None:
    page = DocumentPage(
        document_id=uuid4(), page_number=1, text="searchable", needs_ocr=False
    )
    engine = FakeOcrEngine([])

    result = DocumentOcrProcessor(engine).process(b"not a PDF", [page])

    assert result == [page]
    assert engine.images == []


def test_rejects_page_number_outside_pdf() -> None:
    page = DocumentPage(document_id=uuid4(), page_number=3, text="", needs_ocr=True)

    with pytest.raises(OcrError, match="no page 3"):
        DocumentOcrProcessor(FakeOcrEngine([])).process(
            _pdf_with_different_page_sizes(), [page]
        )


def test_tesseract_invocation_is_argument_based_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, b"  recognized text\n", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = TesseractOcrEngine(
        executable="custom-tesseract",
        language="eng+spa",
        timeout_seconds=12,
        page_segmentation_mode=6,
    )

    assert engine.extract_text(b"png bytes") == "recognized text"
    assert captured["command"] == [
        "custom-tesseract",
        "stdin",
        "stdout",
        "-l",
        "eng+spa",
        "--psm",
        "6",
    ]
    assert captured["input"] == b"png bytes"
    assert captured["timeout"] == 12
    assert "shell" not in captured


def test_tesseract_failures_are_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)

    with pytest.raises(OcrError, match="was not found"):
        TesseractOcrEngine(executable="missing").extract_text(b"image")


def test_tesseract_nonzero_exit_is_an_ocr_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 1, b"", b"bad language data")

    monkeypatch.setattr(subprocess, "run", failed)

    with pytest.raises(OcrError, match="bad language data"):
        TesseractOcrEngine().extract_text(b"image")
