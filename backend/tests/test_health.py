from contractfit.api import (
    DEMO_EMAIL,
    configure_store,
    get_evaluation,
    list_matches,
    list_opportunities,
    reset_demo,
    seed_demo,
)
from contractfit.main import app, health
from contractfit.store import InMemoryStore


def test_health() -> None:
    assert health()["status"] == "ok"
    assert "/health" in app.openapi()["paths"]


def test_demo_vertical_slice() -> None:
    store = InMemoryStore()
    configure_store(store)
    seed_demo()
    identity = store.get_identity_by_email(DEMO_EMAIL)
    assert identity is not None
    assert reset_demo(identity)["opportunities"] == 1
    opportunities = list_opportunities()
    matches = list_matches(identity)
    evaluation = get_evaluation(identity)

    assert len(opportunities) == 1
    assert matches[0].eligibility == "eligible"
    assert matches[0].gates[0].evidence is not None
    assert matches[0].gates[0].evidence.supporting_text
    assert evaluation.eligibility_accuracy == 1
