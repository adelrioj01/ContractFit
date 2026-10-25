import re

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


class LabeledKeywordEmbeddingProvider:
    name = "labeled-keyword-fixture"
    dimensions = 8
    groups = (
        {"climate", "cooling", "heating", "ventilation", "air-conditioning"},
        {"hospital", "infection", "environmental", "medical", "sanitation", "pathogen"},
        {"turf", "tree", "irrigation", "landscape", "arborist", "sprinkler"},
        {"pest", "rodent", "insect", "vermin", "wildlife"},
        {"electricians", "switchgear", "power", "generator", "breaker", "power-distribution"},
        {"plumbing", "drain", "backflow", "pipe", "sewer", "cross-connection"},
        {"buildings", "multi-trade", "work-order", "building", "asset", "service-desk"},
        {"boilers", "burners", "steam-plant", "heating-plant", "combustion", "pressure-vessel"},
    )

    def embed(self, text: str) -> list[float]:
        tokens = set(re.findall(r"[a-z]+(?:-[a-z]+)*", text.lower()))
        return [float(bool(tokens & group)) for group in self.groups]


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
        EmbeddingSimilarityScorer(LabeledKeywordEmbeddingProvider()),
    )

    assert len(cases) == 8
    assert lexical.top_1_accuracy == 0.375
    assert lexical.recall_at_3 == 0.625
    assert lexical.mean_reciprocal_rank == 0.5521
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
