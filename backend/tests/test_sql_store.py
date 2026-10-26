from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import DocumentPage, DocumentStatus, SourceDocument
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
    document = SourceDocument(
        organization_id=SAMPLE_PROFILE.organization_id,
        filename="sample.txt",
        content=SAMPLE_SOLICITATION,
        sha256="a" * 64,
        storage_key="aa/aa/file.txt",
        size_bytes=len(SAMPLE_SOLICITATION),
        status=DocumentStatus.READY,
    )
    pages = [DocumentPage(document_id=document.id, page_number=1, text=SAMPLE_SOLICITATION)]
    opportunity = RequirementExtractor().extract(document, "sql-round-trip")

    store.save_profile(SAMPLE_PROFILE)
    store.save_document(document)
    store.save_document_pages(pages)
    store.save_opportunity(opportunity)

    saved_profile = store.get_profile()
    saved_opportunity = store.list_opportunities()[0]
    assert saved_profile is not None
    assert saved_profile.name == SAMPLE_PROFILE.name
    assert saved_opportunity.title == opportunity.title
    assert saved_opportunity.requirements[0].evidence.supporting_text
    assert (
        store.find_document_by_sha256("a" * 64, SAMPLE_PROFILE.organization_id)
        is not None
    )
    assert store.list_document_pages(document.id)[0].page_number == 1

    store.reset()
    assert store.get_profile() is None
    assert store.list_opportunities() == []


def test_sql_store_scopes_profiles_by_organization() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store = SqlAlchemyStore(build_session_factory(engine))
    other_organization_id = uuid4()
    other_profile = SAMPLE_PROFILE.model_copy(
        update={
            "id": uuid4(),
            "organization_id": other_organization_id,
            "name": "Other Facilities",
        }
    )

    store.save_profile(SAMPLE_PROFILE)
    store.save_profile(other_profile)

    assert store.get_profile(SAMPLE_PROFILE.organization_id) == SAMPLE_PROFILE
    assert store.get_profile(other_organization_id) == other_profile
    assert store.get_profile(uuid4()) is None
