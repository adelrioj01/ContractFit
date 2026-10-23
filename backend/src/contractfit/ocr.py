from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Protocol

import pymupdf

from contractfit.domain import DocumentPage


class OcrError(RuntimeError):
    """Raised when OCR cannot be executed or a PDF page cannot be rendered."""


class OcrEngine(Protocol):
    """Extract searchable text from one encoded image."""

    def extract_text(self, image: bytes) -> str: ...


class TesseractOcrEngine:
    """Small, shell-free adapter around the local Tesseract executable."""

    def __init__(
        self,
        executable: str = "tesseract",
        language: str = "eng",
        timeout_seconds: float = 60,
        page_segmentation_mode: int = 3,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if page_segmentation_mode < 0:
            raise ValueError("page_segmentation_mode cannot be negative")
        self.executable = executable
        self.language = language
        self.timeout_seconds = timeout_seconds
        self.page_segmentation_mode = page_segmentation_mode

    def extract_text(self, image: bytes) -> str:
        if not image:
            raise OcrError("Cannot run OCR on an empty image")

        command = [
            self.executable,
            "stdin",
            "stdout",
            "-l",
            self.language,
            "--psm",
            str(self.page_segmentation_mode),
        ]
        try:
            result = subprocess.run(
                command,
                input=image,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise OcrError(f"Tesseract executable was not found: {self.executable!r}") from exc
        except subprocess.TimeoutExpired as exc:
            raise OcrError(
                f"Tesseract exceeded the {self.timeout_seconds:g}-second timeout"
            ) from exc
        except OSError as exc:
            raise OcrError(f"Tesseract could not be started: {exc}") from exc

        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise OcrError(detail or f"Tesseract exited with status {result.returncode}")
        return result.stdout.decode("utf-8", errors="replace").strip()


class DocumentOcrProcessor:
    """Render and OCR only the PDF pages previously marked as needing OCR."""

    def __init__(self, engine: OcrEngine, render_dpi: int = 200) -> None:
        if render_dpi <= 0:
            raise ValueError("render_dpi must be greater than zero")
        self.engine = engine
        self.render_dpi = render_dpi

    def process(self, pdf_data: bytes, pages: Sequence[DocumentPage]) -> list[DocumentPage]:
        pending = [page for page in pages if page.needs_ocr]
        if not pending:
            return [page.model_copy(deep=True) for page in pages]
        if not pdf_data:
            raise OcrError("Cannot process an empty PDF")

        try:
            with pymupdf.open(  # type: ignore[no-untyped-call]
                stream=pdf_data, filetype="pdf"
            ) as document:
                processed: list[DocumentPage] = []
                for page in pages:
                    if not page.needs_ocr:
                        processed.append(page.model_copy(deep=True))
                        continue
                    if page.page_number > document.page_count:
                        raise OcrError(
                            f"PDF has no page {page.page_number}; it has {document.page_count} pages"
                        )

                    pdf_page = document.load_page(page.page_number - 1)
                    pixmap = pdf_page.get_pixmap(dpi=self.render_dpi, alpha=False)
                    image = pixmap.tobytes("png")
                    text = self.engine.extract_text(image).strip()
                    processed.append(
                        page.model_copy(
                            update={
                                "text": text if text else page.text,
                                "needs_ocr": not bool(text),
                            },
                            deep=True,
                        )
                    )
                return processed
        except OcrError:
            raise
        except Exception as exc:
            raise OcrError(f"Could not render PDF for OCR: {exc}") from exc
