from datetime import date
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import Opportunity, SourceDocument
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

    organization_id = uuid4()
    attachment_document = SourceDocument(
        organization_id=organization_id,
        filename="attachment.txt",
        content="SAM attachment",
        origin_opportunity_id=sam.id,
        origin_url="https://api.sam.gov/resources/attachment.txt",
        origin_snapshot_sha256=snapshot.content_sha256,
    )
    store.save_document(attachment_document)

    saved_attachment = store.find_document_by_origin(
        sam.id,
        "https://api.sam.gov/resources/attachment.txt",
        snapshot.content_sha256,
        organization_id,
    )
    assert saved_attachment is not None
    assert saved_attachment.id == attachment_document.id
    assert saved_attachment.origin_opportunity_id == sam.id
    assert saved_attachment.origin_url == attachment_document.origin_url
