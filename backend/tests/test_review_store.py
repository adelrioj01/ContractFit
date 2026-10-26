from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.database import Base, build_session_factory
from contractfit.domain import Evidence, Opportunity, SourceDocument
from contractfit.review import ReviewItem, ReviewReason, ReviewStatus
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


def make_review(organization_id: UUID, document_id: UUID) -> ReviewItem:
    return ReviewItem(
        organization_id=organization_id,
        field_name="response_deadline",
        extracted_value="2026-11-30",
        confidence=0.51,
        mandatory=True,
        reason=ReviewReason.LOW_CONFIDENCE,
        evidence=[
            Evidence(
                document_id=document_id,
                page=2,
                supporting_text="Responses are due November 30.",
            )
        ],
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


def test_review_store_round_trip_and_organization_isolation(store: ContractFitStore) -> None:
    organization_id = uuid4()
    document = store.save_document(
        SourceDocument(
            organization_id=organization_id,
            filename="notice.txt",
            content="source",
        )
    )
    item = store.save_review_item(make_review(organization_id, document.id))

    assert store.get_review_item(item.id, organization_id) == item
    assert store.get_review_item(item.id, uuid4()) is None
    assert store.list_review_items(uuid4()) == []
    assert store.list_review_items(organization_id)[0].evidence[0].page == 2


def test_review_store_persists_resolution_and_filters_status(
    store: ContractFitStore,
) -> None:
    organization_id = uuid4()
    document = store.save_document(
        SourceDocument(
            organization_id=organization_id,
            filename="notice.txt",
            content="source",
        )
    )
    pending = store.save_review_item(make_review(organization_id, document.id))
    resolved = store.save_review_item(
        pending.resolve(reviewer_id=uuid4(), corrected_value="2026-12-01")
    )

    assert store.list_review_items(organization_id, ReviewStatus.PENDING) == []
    assert store.list_review_items(organization_id, ReviewStatus.RESOLVED) == [resolved]


def test_review_store_rejects_foreign_references_and_accepts_public_opportunities(
    store: ContractFitStore,
) -> None:
    first_organization_id = uuid4()
    second_organization_id = uuid4()
    first_document = store.save_document(
        SourceDocument(
            organization_id=first_organization_id,
            filename="first.txt",
            content="first evidence",
        )
    )
    second_document = store.save_document(
        SourceDocument(
            organization_id=second_organization_id,
            filename="second.txt",
            content="second evidence",
        )
    )
    private_opportunity = store.save_opportunity(
        Opportunity(
            source="upload",
            source_id=f"private-{uuid4()}",
            title="Second organization opportunity",
            document_id=second_document.id,
        )
    )
    public_opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id=f"public-{uuid4()}",
            title="Shared SAM opportunity",
        )
    )

    with pytest.raises(ValueError, match="opportunity is not visible"):
        store.save_review_item(
            make_review(first_organization_id, first_document.id).model_copy(
                update={"opportunity_id": private_opportunity.id}
            )
        )

    with pytest.raises(ValueError, match="evidence document is not owned"):
        store.save_review_item(make_review(first_organization_id, second_document.id))

    saved = store.save_review_item(
        make_review(first_organization_id, first_document.id).model_copy(
            update={"opportunity_id": public_opportunity.id}
        )
    )
    assert saved.opportunity_id == public_opportunity.id
