import json
from pathlib import Path

import pytest

from contractfit.ranking_cli import build_ranking_report, main


def test_build_ranking_report_supports_reproducible_lexical_run() -> None:
    report = build_ranking_report("lexical")

    assert report.cases == 30
    assert report.embedding_available is False
    assert report.lexical.cases == 30


def test_ranking_cli_writes_machine_readable_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "ranking-report.json"

    assert main(["--provider", "lexical", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert payload == printed
    assert payload["cases"] == 30


def test_build_ranking_report_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        build_ranking_report("unknown")
