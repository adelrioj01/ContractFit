from pytest import MonkeyPatch

from contractfit.api import get_ranking_evaluation
from contractfit.config import get_settings


def test_ranking_evaluation_api_returns_reproducible_lexical_baseline(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "disabled")
    get_settings.cache_clear()
    try:
        report = get_ranking_evaluation()
    finally:
        get_settings.cache_clear()

    assert report.cases == 8
    assert report.lexical.cases == 8
    assert report.embedding is None
    assert report.embedding_available is False
    assert report.mrr_delta is None
    assert report.note is not None
