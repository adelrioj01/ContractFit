from contractfit.domain import SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.sample_data import SAMPLE_SOLICITATION


def test_extracts_requirements_with_verbatim_evidence() -> None:
    document = SourceDocument(filename="sample.txt", content=SAMPLE_SOLICITATION)
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
