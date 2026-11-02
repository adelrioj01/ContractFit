from datetime import date
from decimal import Decimal

import pytest

from contractfit.domain import EligibilityStatus, SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.matching import OpportunityMatcher
from contractfit.sample_data import (
    REAL_FEMA_SOLICITATION,
    SAMPLE_PROFILE,
    SAMPLE_SOLICITATION,
)


def test_matching_applies_hard_gates_and_explains_score() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sample.txt",
            content=SAMPLE_SOLICITATION,
        ),
        "sample-1",
    )
    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    assert result.eligibility == EligibilityStatus.ELIGIBLE
    assert result.fit_score >= 70
    assert len(result.gates) == 6
    assert result.gates[-1].name == "past_performance"
    assert result.gates[-1].status == EligibilityStatus.ELIGIBLE
    assert result.explanation


def test_matching_accepts_embedding_similarity_without_bypassing_hard_gates() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sample.txt",
            content=SAMPLE_SOLICITATION,
        ),
        "embedding-1",
    )
    result = OpportunityMatcher().match(
        SAMPLE_PROFILE,
        opportunity,
        semantic_override=(0.91, "Embedding cosine similarity is 91%.", "embedding-cosine:test"),
    )

    assert result.scoring_method == "embedding-cosine:test"
    assert result.eligibility == EligibilityStatus.ELIGIBLE
    assert result.fit_score > 90
    assert "91%" in result.explanation


def test_real_fema_denton_notice_is_no_go_after_its_deadline() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sam-70FB8026Q00000053.txt",
            content=REAL_FEMA_SOLICITATION,
        ),
        "SAM-70FB8026Q00000053",
    )

    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    gates = {gate.name: gate for gate in result.gates}

    assert opportunity.title.startswith("HVAC Maintenance (Denton, TX)")
    assert gates["deadline"].status == EligibilityStatus.INELIGIBLE
    assert gates["location"].status == EligibilityStatus.ELIGIBLE
    assert gates["set_aside"].status == EligibilityStatus.ELIGIBLE
    assert result.eligibility == EligibilityStatus.INELIGIBLE
    assert result.fit_score <= 39


def test_missing_past_performance_requires_review_instead_of_false_failure() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="sample.txt",
            content=SAMPLE_SOLICITATION,
        ),
        "missing-past-performance",
    )
    profile = SAMPLE_PROFILE.model_copy(update={"past_performance": []})

    result = OpportunityMatcher().match(profile, opportunity)
    gate = next(item for item in result.gates if item.name == "past_performance")

    assert gate.status == EligibilityStatus.NEEDS_REVIEW
    assert "not been demonstrated" in gate.reason
    assert result.eligibility == EligibilityStatus.NEEDS_REVIEW


def test_conflicting_deadlines_require_review_without_a_misleading_citation() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="conflicting.txt",
            content="""Title: Conflicting deadline
Response deadline: 2099-02-15
Due date: 2099-03-01
Place of performance: Dallas, Texas
Set-aside: Small Business
Required certification: EPA 608
Estimated value: $200,000
Scope: Commercial HVAC preventive maintenance.""",
        ),
        "conflicting-deadline",
    )

    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    gate = next(item for item in result.gates if item.name == "deadline")

    assert gate.status == EligibilityStatus.NEEDS_REVIEW
    assert gate.evidence is None
    assert result.eligibility == EligibilityStatus.NEEDS_REVIEW


def test_gate_evidence_matches_the_exact_value_that_was_evaluated() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="ordered-evidence.txt",
            content="""Response deadline: 2099-02-15
Due date: 2099-03-01
Place of performance: Dallas, Texas
Set-aside: Small Business
Estimated value: $200,000
Scope: Commercial HVAC preventive maintenance.""",
        ),
        "ordered-evidence",
    ).model_copy(update={"response_deadline": date(2099, 3, 1)})

    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    gate = next(item for item in result.gates if item.name == "deadline")

    assert gate.evidence is not None
    assert gate.evidence.supporting_text == "Due date: 2099-03-01"
    assert 'deadline [document ' in result.explanation
    assert '"Due date: 2099-03-01"' in result.explanation


@pytest.mark.parametrize(
    ("field_name", "evaluated_value", "gate_name", "expected_text"),
    [
        (
            "place_of_performance",
            "Miami, Florida",
            "location",
            "Location: Miami, Florida",
        ),
        ("set_aside", "8(a)", "set_aside", "Set-aside: 8(a)"),
        (
            "estimated_value",
            Decimal(350000),
            "contract_value",
            "Estimated value: $350,000",
        ),
    ],
)
def test_other_gate_evidence_matches_the_exact_evaluated_value(
    field_name: str, evaluated_value: object, gate_name: str, expected_text: str
) -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(
            organization_id=SAMPLE_PROFILE.organization_id,
            filename="ordered-evidence.txt",
            content="""Place of performance: Dallas, Texas
Location: Miami, Florida
Set-aside: Small Business
Set-aside: 8(a)
Estimated value: $200,000
Estimated value: $350,000
Scope: Commercial HVAC preventive maintenance.""",
        ),
        "ordered-other-evidence",
    ).model_copy(update={field_name: evaluated_value})

    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    gate = next(item for item in result.gates if item.name == gate_name)

    assert gate.evidence is not None
    assert gate.evidence.supporting_text == expected_text
