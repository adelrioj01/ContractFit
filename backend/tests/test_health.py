import pytest
from fastapi import HTTPException

from contractfit.api import (
    DEMO_EMAIL,
    configure_store,
    get_evaluation,
    list_matches,
    list_opportunities,
    reset_demo,
    seed_demo,
)
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
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
    assert reset_demo(identity)["opportunities"] == 2
    opportunities = list_opportunities(identity)
    matches = list_matches(identity)
    evaluation = get_evaluation(identity)

    assert len(opportunities) == 2
    assert {item.source_id for item in opportunities} == {
        "DEMO-HVAC-001",
        "SAM-70FB8026Q00000053",
    }
    assert matches[0].eligibility == "eligible"
    assert {match.eligibility.value for match in matches} == {"eligible", "ineligible"}
    assert matches[0].gates[0].evidence is not None
    assert matches[0].gates[0].evidence.supporting_text
    assert evaluation.eligibility_accuracy == 1


def test_demo_reset_rejects_non_demo_administrator() -> None:
    organization = Organization(name="Unrelated tenant")
    user = UserAccount(
        email="admin@example.com", display_name="Admin", password_hash="unused"
    )
    identity = AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )

    with pytest.raises(HTTPException) as error:
        reset_demo(identity)

    assert error.value.status_code == 403
