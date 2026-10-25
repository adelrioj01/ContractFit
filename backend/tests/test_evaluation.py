import pytest
from pydantic import ValidationError

from contractfit.ai import LexicalSemanticScorer
from contractfit.embeddings import EmbeddingSimilarityScorer
from contractfit.evaluation import (
    EvaluationCase,
    RankingEvaluationCase,
    compare_rankers,
    evaluate,
    evaluate_ranking,
)
from contractfit.evaluation_dataset import EVALUATION_CASES, RANKING_EVALUATION_CASES
from contractfit.sample_data import SAMPLE_PROFILE


class LabeledOracleEmbeddingProvider:
    """Deterministic test oracle; it is not presented as a model benchmark."""

    name = "labeled-oracle-fixture"

    def __init__(self, cases: list[RankingEvaluationCase]) -> None:
        self.dimensions = len(cases)
        self.vectors: dict[str, list[float]] = {}
        for index, case in enumerate(cases):
            vector = [0.0] * self.dimensions
            vector[index] = 1.0
            self.vectors[case.query] = vector
            for candidate in case.candidates:
                if candidate.id in case.relevant_ids:
                    self.vectors[candidate.text] = vector

    def embed(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0] * self.dimensions)


def test_labeled_evaluation_meets_baseline() -> None:
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    report = evaluate(cases, SAMPLE_PROFILE)
    assert report.extraction_recall == 1
    assert report.citation_validity == 1
    assert report.eligibility_accuracy == 1


def test_labeled_ranking_evaluation_compares_lexical_and_embedding_metrics() -> None:
    cases = [
        RankingEvaluationCase.model_validate(item) for item in RANKING_EVALUATION_CASES
    ]
    lexical = evaluate_ranking(cases, LexicalSemanticScorer())
    comparison = compare_rankers(
        cases,
        LexicalSemanticScorer(),
        EmbeddingSimilarityScorer(LabeledOracleEmbeddingProvider(cases)),
    )

    assert len(cases) == 30
    assert len({case.name for case in cases}) == 30
    assert all(len(case.candidates) == 4 for case in cases)
    assert lexical.cases == 30
    assert lexical.top_1_accuracy == 0.3667
    assert lexical.recall_at_3 == 0.4333
    assert lexical.mean_reciprocal_rank == 0.5306
    assert comparison.embedding is not None
    assert comparison.embedding.top_1_accuracy == 1.0
    assert comparison.embedding.recall_at_3 == 1.0
    assert comparison.embedding.mean_reciprocal_rank == 1.0
    assert comparison.mrr_delta == pytest.approx(
        1.0 - lexical.mean_reciprocal_rank
    )


def test_ranking_case_rejects_unknown_relevant_candidate() -> None:
    with pytest.raises(ValidationError, match="relevant ID"):
        RankingEvaluationCase.model_validate(
            {
                "name": "invalid",
                "query": "query",
                "candidates": [
                    {"id": "one", "text": "first"},
                    {"id": "two", "text": "second"},
                ],
                "relevant_ids": ["missing"],
            }
        )
