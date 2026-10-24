from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import Base, build_session_factory
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


def make_identity(email: str = "owner@example.com") -> AuthIdentity:
    organization = Organization(name="Acme Facilities")
    user = UserAccount(
        email=email,
        display_name="Owner",
        password_hash="stored-password-hash",
    )
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest) -> ContractFitStore:
    if request.param == "memory":
        return InMemoryStore()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SqlAlchemyStore(build_session_factory(engine))


def test_identity_round_trip_by_email_and_user_id(store: ContractFitStore) -> None:
    identity = store.register_identity(make_identity())

    assert store.get_identity_by_email(" OWNER@EXAMPLE.COM ") == identity
    assert store.get_identity_by_user_id(identity.user.id) == identity
    assert store.get_identity_by_user_id(uuid4()) is None


def test_duplicate_email_is_rejected(store: ContractFitStore) -> None:
    store.register_identity(make_identity())

    with pytest.raises(ValueError, match="already registered"):
        store.register_identity(make_identity("OWNER@example.com"))
