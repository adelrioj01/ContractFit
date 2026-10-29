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
from contractfit.sample_data import SYNTHETIC_COMPANY_SEEDS, SYNTHETIC_OPPORTUNITIES
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
    assert reset_demo(identity) == {"profiles": 5, "opportunities": 7}
    opportunities = list_opportunities(identity)
    matches = list_matches(identity)
    evaluation = get_evaluation(identity)

    assert len(opportunities) == 7
    assert {item.source_id for item in opportunities} >= {
        "DEMO-HVAC-001",
        "SAM-70FB8026Q00000053",
    }
    assert matches[0].eligibility == "eligible"
    assert {match.eligibility.value for match in matches} == {"eligible", "ineligible"}
    assert matches[0].gates[0].evidence is not None
    assert matches[0].gates[0].evidence.supporting_text
    assert evaluation.eligibility_accuracy == 1


def test_synthetic_company_database_is_tenant_isolated_and_ranks_differently() -> None:
    store = InMemoryStore()
    configure_store(store)
    seed_demo()

    top_sources: dict[str, str] = {}
    for seed in SYNTHETIC_COMPANY_SEEDS:
        identity = store.get_identity_by_email(seed.email)
        assert identity is not None
        assert store.get_profile(identity.organization.id) == seed.profile
        visible = list_opportunities(identity)
        if seed.email == DEMO_EMAIL:
            assert len(visible) == len(SYNTHETIC_OPPORTUNITIES) + 2
        else:
            assert len(visible) == len(SYNTHETIC_OPPORTUNITIES)
            assert all(item.document_id is None for item in visible)
        top_match = list_matches(identity)[0]
        top_opportunity = store.get_opportunity(
            top_match.opportunity_id, identity.organization.id
        )
        assert top_opportunity is not None
        top_sources[seed.email] = top_opportunity.source_id

    assert top_sources["demo@contractfit.local"] == "DEMO-HVAC-001"
    assert top_sources["demo+cleaning@contractfit.local"] == "SYN-JANITORIAL-001"
    assert top_sources["demo+grounds@contractfit.local"] == "SYN-GROUNDS-001"
    assert top_sources["demo+electrical@contractfit.local"] == "SYN-ELECTRICAL-001"
    assert top_sources["demo+plumbing@contractfit.local"] == "SYN-PLUMBING-001"


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
