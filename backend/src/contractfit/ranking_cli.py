import argparse
from collections.abc import Sequence
from pathlib import Path

from contractfit.ai import LexicalSemanticScorer
from contractfit.embeddings import EmbeddingSimilarityScorer, OllamaEmbeddingProvider
from contractfit.evaluation import (
    RankingComparisonReport,
    RankingEvaluationCase,
    compare_rankers,
)
from contractfit.evaluation_dataset import RANKING_EVALUATION_CASES


def build_ranking_report(
    provider: str,
    ollama_base_url: str = "http://localhost:11434",
    embedding_model: str = "nomic-embed-text",
    embedding_dimensions: int = 768,
) -> RankingComparisonReport:
    cases = [RankingEvaluationCase.model_validate(item) for item in RANKING_EVALUATION_CASES]
    lexical = LexicalSemanticScorer()
    if provider == "lexical":
        return compare_rankers(
            cases,
            lexical,
            note="Lexical-only run; no embedding model was evaluated.",
        )
    if provider != "ollama":
        raise ValueError(f"unsupported ranking provider: {provider}")
    embeddings = OllamaEmbeddingProvider(
        ollama_base_url,
        embedding_model,
        embedding_dimensions,
    )
    return compare_rankers(cases, lexical, EmbeddingSimilarityScorer(embeddings))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate ContractFit lexical and embedding ranking quality."
    )
    parser.add_argument("--provider", choices=("lexical", "ollama"), default="lexical")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--embedding-model", default="nomic-embed-text")
    parser.add_argument("--embedding-dimensions", type=int, default=768)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = build_ranking_report(
        args.provider,
        args.ollama_base_url,
        args.embedding_model,
        args.embedding_dimensions,
    )
    rendered = report.model_dump_json(indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
