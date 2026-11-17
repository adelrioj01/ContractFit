import json

from contractfit.quality_cli import LatencyBudget, build_quality_report, main


def test_portfolio_quality_report_meets_regression_contract() -> None:
    report = build_quality_report(
        LatencyBudget(
            extraction_and_gates_ms=5_000,
            instruction_text_ms=5_000,
            lexical_ranking_ms=5_000,
        )
    )

    assert report.passed is True
    assert report.extraction.cases == 4
    assert report.instruction_text.cases == 6
    assert report.ranking.cases == 30
    assert report.failures == []
    assert "not LLM prompt security" in report.limitations[-3]
    assert "roadmap target remains 100" in report.limitations[-1]


def test_quality_report_fails_an_impossible_latency_budget() -> None:
    report = build_quality_report(
        LatencyBudget(
            extraction_and_gates_ms=0.000001,
            instruction_text_ms=0.000001,
            lexical_ranking_ms=0.000001,
        )
    )

    assert report.passed is False
    assert {failure.split(" exceeded")[0] for failure in report.failures} == {
        "latency.extraction_and_gates_ms",
        "latency.instruction_text_ms",
        "latency.lexical_ranking_ms",
    }


def test_quality_cli_writes_machine_readable_report(tmp_path: object) -> None:
    from pathlib import Path

    output = Path(str(tmp_path)) / "quality-report.json"

    exit_code = main(["--output", str(output)])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
