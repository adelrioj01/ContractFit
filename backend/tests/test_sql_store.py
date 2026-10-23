from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import SourceDocument
from contractfit.extraction import RequirementExtractor
from contractfit.sample_data import SAMPLE_PROFILE, SAMPLE_SOLICITATION
from contractfit.sql_store import SqlAlchemyStore


def test_sql_store_round_trip_preserves_evidence() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store = SqlAlchemyStore(build_session_factory(engine))
    document = SourceDocument(filename="sample.txt", content=SAMPLE_SOLICITATION)
    opportunity = RequirementExtractor().extract(document, "sql-round-trip")

    store.save_profile(SAMPLE_PROFILE)
    store.save_document(document)
    store.save_opportunity(opportunity)

    saved_profile = store.get_profile()
    saved_opportunity = store.list_opportunities()[0]
    assert saved_profile is not None
    assert saved_profile.name == SAMPLE_PROFILE.name
    assert saved_opportunity.title == opportunity.title
    assert saved_opportunity.requirements[0].evidence.supporting_text

    store.reset()
    assert store.get_profile() is None
    assert store.list_opportunities() == []
