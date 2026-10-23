from __future__ import annotations

from io import BytesIO

import pymupdf
from docx import Document
from pydantic import BaseModel, Field


class DocumentParseError(ValueError):
    """Raised when a document cannot be parsed safely."""


class ParsedPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str
    needs_ocr: bool = False


class DocumentParser:
    """Convert supported document bytes into page-oriented text."""

    def parse(self, filename: str, content_type: str, data: bytes) -> list[ParsedPage]:
        normalized_type = content_type.partition(";")[0].strip().lower()

        try:
            if normalized_type == "application/pdf":
                return self._parse_pdf(data)
            if normalized_type == (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                return self._parse_docx(data)
            if normalized_type == "text/plain":
                return [ParsedPage(page_number=1, text=data.decode("utf-8"))]
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError(f"Could not parse {filename!r}: {exc}") from exc

        raise DocumentParseError(f"Unsupported content type: {content_type!r}")

    @staticmethod
    def _parse_pdf(data: bytes) -> list[ParsedPage]:
        with pymupdf.open(  # type: ignore[no-untyped-call]
            stream=data, filetype="pdf"
        ) as document:
            pages: list[ParsedPage] = []
            for index, page in enumerate(document):
                text = page.get_text("text")
                non_whitespace_length = sum(not character.isspace() for character in text)
                pages.append(
                    ParsedPage(
                        page_number=index + 1,
                        text=text,
                        needs_ocr=non_whitespace_length < 20,
                    )
                )
            return pages

    @staticmethod
    def _parse_docx(data: bytes) -> list[ParsedPage]:
        document = Document(BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return [ParsedPage(page_number=1, text=text)]
