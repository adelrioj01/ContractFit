from contractfit.api import (
    configure_store,
    get_evaluation,
    list_matches,
    list_opportunities,
    reset_demo,
)
from contractfit.main import app, health
from contractfit.store import InMemoryStore


def test_health() -> None:
    assert health()["status"] == "ok"
    assert "/health" in app.openapi()["paths"]


def test_demo_vertical_slice() -> None:
    configure_store(InMemoryStore())
    assert reset_demo()["opportunities"] == 1
    opportunities = list_opportunities()
    matches = list_matches()
    evaluation = get_evaluation()

    assert len(opportunities) == 1
    assert matches[0].eligibility == "eligible"
    assert matches[0].gates[0].evidence is not None
    assert matches[0].gates[0].evidence.supporting_text
    assert evaluation.eligibility_accuracy == 1
