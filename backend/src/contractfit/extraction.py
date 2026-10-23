import re
from datetime import date
from decimal import Decimal
from typing import ClassVar
from uuid import uuid4

from contractfit.domain import DocumentPage, Evidence, Opportunity, Requirement, SourceDocument


class RequirementExtractor:
    """Evidence-preserving baseline extractor used locally and in evaluation."""

    _fields: ClassVar[dict[str, re.Pattern[str]]] = {
        "deadline": re.compile(
            r"(?:response deadline|due date):\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
        ),
        "location": re.compile(r"(?:place of performance|location):\s*(.+)", re.IGNORECASE),
        "set_aside": re.compile(r"set-aside:\s*(.+)", re.IGNORECASE),
        "certification": re.compile(r"required certification:\s*(.+)", re.IGNORECASE),
        "value": re.compile(r"estimated value:\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE),
        "scope": re.compile(r"scope:\s*(.+)", re.IGNORECASE),
        "agency": re.compile(r"agency:\s*(.+)", re.IGNORECASE),
        "title": re.compile(r"title:\s*(.+)", re.IGNORECASE),
    }

    def extract(
        self,
        document: SourceDocument,
        source_id: str,
        pages: list[DocumentPage] | None = None,
    ) -> Opportunity:
        matches: dict[str, tuple[str, str]] = {}
        requirements: list[Requirement] = []

        page_inputs: list[tuple[int | None, str]] = (
            [(page.page_number, page.text) for page in pages]
            if pages is not None
            else [(None, document.content)]
        )
        for page_number, text in page_inputs:
            for line_number, raw_line in enumerate(text.splitlines(), start=1):
                line = raw_line.strip()
                for category, pattern in self._fields.items():
                    match = pattern.search(line)
                    if not match:
                        continue
                    value = match.group(1).strip()
                    matches[category] = (value, line)
                    if category in {
                        "deadline",
                        "location",
                        "set_aside",
                        "certification",
                        "value",
                    }:
                        requirements.append(
                            Requirement(
                                category=category,
                                description=value,
                                mandatory=True,
                                confidence=0.98,
                                evidence=Evidence(
                                    document_id=document.id,
                                    page=page_number,
                                    section=f"line {line_number}",
                                    supporting_text=line,
                                ),
                            )
                        )

        title = matches.get("title", (document.filename, ""))[0]
        deadline_value = matches.get("deadline", (None, ""))[0]
        value_text = matches.get("value", (None, ""))[0]
        return Opportunity(
            id=uuid4(),
            source="uploaded_document",
            source_id=source_id,
            title=title,
            agency=matches.get("agency", (None, ""))[0],
            response_deadline=date.fromisoformat(deadline_value) if deadline_value else None,
            place_of_performance=matches.get("location", (None, ""))[0],
            set_aside=matches.get("set_aside", (None, ""))[0],
            estimated_value=Decimal(value_text.replace(",", "")) if value_text else None,
            scope=matches.get("scope", ("", ""))[0],
            document_id=document.id,
            requirements=requirements,
        )
