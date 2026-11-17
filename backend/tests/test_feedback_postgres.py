import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.engine import make_url

from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import build_engine, build_session_factory
from contractfit.domain import Opportunity
from contractfit.feedback import FeedbackRating, OpportunityFeedback
from contractfit.sql_store import SqlAlchemyStore

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ
    or os.environ.get("CONTRACTFIT_ALLOW_TEST_DB_RESET") != "1",
    reason="requires an explicitly enabled, migrated PostgreSQL test database",
)


def test_concurrent_feedback_first_writes_return_one_winner() -> None:
    database_url = os.environ["DATABASE_URL"]
    database_name = make_url(database_url).database
    assert database_name is not None and database_name.endswith("_test"), (
        "destructive integration tests require a database name ending in _test"
    )
    session_factory = build_session_factory(build_engine(database_url))
    store = SqlAlchemyStore(session_factory)
    store.reset()
    organization = Organization(name="Concurrent feedback contractor")
    user = UserAccount(
        email="concurrent-feedback@example.com",
        display_name="Feedback reviewer",
        password_hash="unused",
    )
    identity = store.register_identity(
        AuthIdentity(
            user=user,
            organization=organization,
            membership=OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.ADMIN,
            ),
        )
    )
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="feedback-race", title="Feedback race")
    )
    barrier = Barrier(2)

    def save(rating: FeedbackRating) -> OpportunityFeedback:
        feedback = OpportunityFeedback(
            organization_id=organization.id,
            opportunity_id=opportunity.id,
            rating=rating,
            submitted_by_user_id=identity.user.id,
        )
        barrier.wait(timeout=10)
        return SqlAlchemyStore(session_factory).save_opportunity_feedback(feedback)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(save, FeedbackRating.RELEVANT),
            executor.submit(save, FeedbackRating.NOT_RELEVANT),
        ]
        results = [future.result(timeout=20) for future in futures]

    persisted = store.get_opportunity_feedback(opportunity.id, organization.id)
    assert persisted is not None
    assert results[0].id == results[1].id == persisted.id
