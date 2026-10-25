from contractfit.domain import EligibilityStatus, SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.matching import OpportunityMatcher
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION


def test_matching_applies_hard_gates_and_explains_score() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(filename="sample.txt", content=SAMPLE_SOLICITATION), "sample-1"
    )
    result = OpportunityMatcher().match(SAMPLE_PROFILE, opportunity)
    assert result.eligibility == EligibilityStatus.ELIGIBLE
    assert result.fit_score >= 70
    assert len(result.gates) == 5
    assert result.explanation


def test_matching_accepts_embedding_similarity_without_bypassing_hard_gates() -> None:
    opportunity = RequirementExtractor().extract(
        SourceDocument(filename="sample.txt", content=SAMPLE_SOLICITATION), "embedding-1"
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
