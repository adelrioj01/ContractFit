import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.api import (
    configure_store,
    seed_demo,
    seed_demo_companies,
    seed_synthetic_catalog,
)
from contractfit.database import Base, build_session_factory
from contractfit.sample_data import SYNTHETIC_COMPANY_SEEDS, SYNTHETIC_OPPORTUNITIES
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


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


def test_synthetic_dataset_persists_multiple_isolated_companies(
    store: ContractFitStore,
) -> None:
    configure_store(store)
    seed_demo()
    seed_demo_companies()
    seed_synthetic_catalog()

    organization_ids = set()
    for seed in SYNTHETIC_COMPANY_SEEDS:
        identity = store.get_identity_by_email(seed.email)
        assert identity is not None
        organization_ids.add(identity.organization.id)
        assert identity.organization.id == seed.profile.organization_id
        assert store.get_profile(identity.organization.id) == seed.profile

    assert len(organization_ids) == len(SYNTHETIC_COMPANY_SEEDS)
    assert {
        item.source_id
        for item in store.list_opportunities()
        if item.source == "synthetic-demo"
    } == {item.source_id for item in SYNTHETIC_OPPORTUNITIES}
