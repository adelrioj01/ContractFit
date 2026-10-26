from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity
from contractfit.sam_models import SamOpportunitySnapshot
from contractfit.sql_store import SqlAlchemyStore


def test_sql_store_uses_composite_source_identity_and_preserves_snapshots() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store = SqlAlchemyStore(build_session_factory(engine))
    sam = Opportunity(
        source="sam.gov",
        source_id="shared-id",
        title="Original title",
        response_deadline=date(2026, 11, 1),
    )
    other = Opportunity(source="state-portal", source_id="shared-id", title="State bid")
    store.save_opportunity(sam)
    store.save_opportunity(other)
    snapshot = SamOpportunitySnapshot(
        opportunity_id=sam.id,
        content_sha256="a" * 64,
        normalized_payload={"title": sam.title},
    )
    store.save_sam_snapshot(snapshot)

    store.save_opportunity(sam.model_copy(update={"title": "Amended title"}))

    assert store.get_opportunity_by_source("sam.gov", "shared-id") is not None
    assert store.get_opportunity_by_source("state-portal", "shared-id") is not None
    assert store.get_opportunity_by_source("sam.gov", "shared-id").title == "Amended title"  # type: ignore[union-attr]
    assert store.list_sam_snapshots(sam.id) == [snapshot]
