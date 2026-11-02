import pytest

from contractfit.domain import DocumentPage, SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.review import build_requirement_reviews
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION


def test_extracts_requirements_with_verbatim_evidence() -> None:
    document = SourceDocument(
        organization_id=SAMPLE_PROFILE.organization_id,
        filename="sample.txt",
        content=SAMPLE_SOLICITATION,
    )
    opportunity = RequirementExtractor().extract(document, "sample-1")
    assert {item.category for item in opportunity.requirements} == {
        "deadline",
        "location",
        "set_aside",
        "certification",
        "value",
    }
    assert all(
        item.evidence.supporting_text in document.content for item in opportunity.requirements
    )


def test_conflicting_scalar_values_become_unknown_and_require_review() -> None:
    document = SourceDocument(
        organization_id=SAMPLE_PROFILE.organization_id,
        filename="conflicting.txt",
        content="",
    )
    pages = [
        DocumentPage(
            document_id=document.id,
            page_number=1,
            text="Response deadline: 2099-02-15",
        ),
        DocumentPage(
            document_id=document.id,
            page_number=2,
            text="Due date: 2099-03-01",
        ),
    ]

    opportunity = RequirementExtractor().extract(document, "conflicting", pages=pages)
    deadlines = [item for item in opportunity.requirements if item.category == "deadline"]

    assert opportunity.response_deadline is None
    assert [item.evidence.page for item in deadlines] == [1, 2]
    assert [item.evidence.supporting_text for item in deadlines] == [
        "Response deadline: 2099-02-15",
        "Due date: 2099-03-01",
    ]
    assert all(item.confidence < 0.75 for item in deadlines)
    reviews = build_requirement_reviews(opportunity, SAMPLE_PROFILE.organization_id)
    assert {item.extracted_value for item in reviews} == {"2099-02-15", "2099-03-01"}


@pytest.mark.parametrize(
    ("category", "field_name", "lines"),
    [
        (
            "location",
            "place_of_performance",
            "Place of performance: Dallas, Texas\nLocation: Miami, Florida",
        ),
        (
            "set_aside",
            "set_aside",
            "Set-aside: Small Business\nSet-aside: 8(a)",
        ),
        (
            "value",
            "estimated_value",
            "Estimated value: $200,000\nEstimated value: $350,000",
        ),
    ],
)
def test_other_conflicting_scalar_categories_become_unknown(
    category: str, field_name: str, lines: str
) -> None:
    document = SourceDocument(
        organization_id=SAMPLE_PROFILE.organization_id,
        filename="conflicting.txt",
        content=lines,
    )

    opportunity = RequirementExtractor().extract(document, f"conflicting-{category}")
    requirements = [
        item for item in opportunity.requirements if item.category == category
    ]

    assert getattr(opportunity, field_name) is None
    assert len(requirements) == 2
    assert all(item.confidence < 0.75 for item in requirements)


def test_equivalent_scalar_duplicates_keep_the_structured_value() -> None:
    document = SourceDocument(
        organization_id=SAMPLE_PROFILE.organization_id,
        filename="duplicate.txt",
        content="Response deadline: 2099-02-15\nDue date: 2099-02-15",
    )

    opportunity = RequirementExtractor().extract(document, "duplicate")

    assert opportunity.response_deadline is not None
    assert opportunity.response_deadline.isoformat() == "2099-02-15"
    assert len(
        [item for item in opportunity.requirements if item.category == "deadline"]
    ) == 2
