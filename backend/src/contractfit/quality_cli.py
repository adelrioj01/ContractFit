import argparse
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field

from contractfit.ai import LexicalSemanticScorer
from contractfit.evaluation import (
    EvaluationCase,
    EvaluationReport,
    RankingEvaluationCase,
    RankingMetrics,
    evaluate,
    evaluate_ranking,
)
from contractfit.evaluation_dataset import (
    EVALUATION_CASES,
    INSTRUCTION_TEXT_EVALUATION_CASES,
    RANKING_EVALUATION_CASES,
)
from contractfit.sample_data import SAMPLE_PROFILE


class LatencyBudget(BaseModel):
    extraction_and_gates_ms: float = Field(default=500, gt=0)
    instruction_text_ms: float = Field(default=500, gt=0)
    lexical_ranking_ms: float = Field(default=500, gt=0)


class LatencyMeasurements(BaseModel):
    extraction_and_gates_ms: float = Field(ge=0)
    instruction_text_ms: float = Field(ge=0)
    lexical_ranking_ms: float = Field(ge=0)


class QualityReport(BaseModel):
    passed: bool
    extraction: EvaluationReport
    instruction_text: EvaluationReport
    ranking: RankingMetrics
    latency_ms: LatencyMeasurements
    latency_budget_ms: LatencyBudget
    failures: list[str]
    limitations: list[str]


def _measure(operation: object) -> tuple[object, float]:
    if not callable(operation):
        raise TypeError("quality operation must be callable")
    started = perf_counter()
    result = operation()
    return result, round((perf_counter() - started) * 1000, 3)


def build_quality_report(budget: LatencyBudget | None = None) -> QualityReport:
    applied_budget = budget or LatencyBudget()
    extraction_cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    instruction_text_cases = [
        EvaluationCase.model_validate(item) for item in INSTRUCTION_TEXT_EVALUATION_CASES
    ]
    ranking_cases = [
        RankingEvaluationCase.model_validate(item) for item in RANKING_EVALUATION_CASES
    ]

    extraction_result, extraction_ms = _measure(lambda: evaluate(extraction_cases, SAMPLE_PROFILE))
    instruction_text_result, instruction_text_ms = _measure(
        lambda: evaluate(instruction_text_cases, SAMPLE_PROFILE)
    )
    ranking_result, ranking_ms = _measure(
        lambda: evaluate_ranking(ranking_cases, LexicalSemanticScorer())
    )
    extraction = EvaluationReport.model_validate(extraction_result)
    instruction_text = EvaluationReport.model_validate(instruction_text_result)
    ranking = RankingMetrics.model_validate(ranking_result)
    latency = LatencyMeasurements(
        extraction_and_gates_ms=extraction_ms,
        instruction_text_ms=instruction_text_ms,
        lexical_ranking_ms=ranking_ms,
    )

    failures = []
    minimum_cases = {
        "extraction": (len(extraction_cases), 4),
        "instruction_text": (len(instruction_text_cases), 6),
        "ranking": (len(ranking_cases), 30),
    }
    for label, (actual, minimum) in minimum_cases.items():
        if actual < minimum:
            failures.append(f"{label}.cases fell below {minimum}")
    for label, report in (
        ("extraction", extraction),
        ("instruction_text", instruction_text),
    ):
        for metric in (
            "extraction_recall",
            "citation_validity",
            "eligibility_accuracy",
            "structured_value_accuracy",
            "gate_accuracy",
            "gate_citation_alignment",
        ):
            if getattr(report, metric) != 1.0:
                failures.append(f"{label}.{metric} must equal 1.0")
    ranking_floors = {
        "top_1_accuracy": 0.3667,
        "recall_at_3": 0.4333,
        "mean_reciprocal_rank": 0.5306,
    }
    for metric, floor in ranking_floors.items():
        if getattr(ranking, metric) < floor:
            failures.append(f"ranking.{metric} fell below {floor}")
    for metric, measured, maximum in (
        (
            "extraction_and_gates_ms",
            latency.extraction_and_gates_ms,
            applied_budget.extraction_and_gates_ms,
        ),
        (
            "instruction_text_ms",
            latency.instruction_text_ms,
            applied_budget.instruction_text_ms,
        ),
        ("lexical_ranking_ms", latency.lexical_ranking_ms, applied_budget.lexical_ranking_ms),
    ):
        if measured > maximum:
            failures.append(f"latency.{metric} exceeded {maximum} ms")

    return QualityReport(
        passed=not failures,
        extraction=extraction,
        instruction_text=instruction_text,
        ranking=ranking,
        latency_ms=latency,
        latency_budget_ms=applied_budget,
        failures=failures,
        limitations=[
            "All bundled cases are synthetic and are regression tests, not production accuracy claims.",
            "Instruction-like text cases exercise only deterministic extraction, not LLM prompt security.",
            "Wall-clock budgets cover deterministic local evaluation, not OCR, network, or Ollama latency.",
            "The ranking corpus contains 30 labeled cases; the roadmap target remains 100.",
        ],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run ContractFit portfolio quality and latency regression gates."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_quality_report()
    rendered = report.model_dump_json(indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
