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
