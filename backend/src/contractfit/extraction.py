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
        matches: dict[str, list[tuple[str, str]]] = {}
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
                    matches.setdefault(category, []).append((value, line))
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

        scalar_categories = {"deadline", "location", "set_aside", "value"}
        conflicting_categories = {
            category
            for category in scalar_categories
            if len(
                {
                    self._normalized_scalar(category, value)
                    for value, _ in matches.get(category, [])
                }
            )
            > 1
        }
        requirements = [
            requirement.model_copy(update={"confidence": 0.5})
            if requirement.category in conflicting_categories
            else requirement
            for requirement in requirements
        ]

        title = self._latest_value(matches, "title") or document.filename
        deadline_value = self._resolved_scalar(matches, "deadline")
        value_text = self._resolved_scalar(matches, "value")
        return Opportunity(
            id=uuid4(),
            source="uploaded_document",
            source_id=source_id,
            title=title,
            agency=self._latest_value(matches, "agency"),
            response_deadline=date.fromisoformat(deadline_value) if deadline_value else None,
            place_of_performance=self._resolved_scalar(matches, "location"),
            set_aside=self._resolved_scalar(matches, "set_aside"),
            estimated_value=Decimal(value_text.replace(",", "")) if value_text else None,
            scope=self._latest_value(matches, "scope") or "",
            document_id=document.id,
            requirements=requirements,
        )

    @staticmethod
    def _latest_value(
        matches: dict[str, list[tuple[str, str]]], category: str
    ) -> str | None:
        values = matches.get(category, [])
        return values[-1][0] if values else None

    @classmethod
    def _resolved_scalar(
        cls, matches: dict[str, list[tuple[str, str]]], category: str
    ) -> str | None:
        values = matches.get(category, [])
        if not values:
            return None
        normalized = {cls._normalized_scalar(category, value) for value, _ in values}
        return values[-1][0] if len(normalized) == 1 else None

    @staticmethod
    def _normalized_scalar(category: str, value: str) -> str:
        if category == "value":
            return str(Decimal(value.replace(",", "")))
        return " ".join(value.casefold().split())
