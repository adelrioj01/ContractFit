from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.amendments import AmendmentChangeType, compare_amendments
from contractfit.api import configure_store, router
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.database import Base, build_session_factory
from contractfit.domain import Evidence, Opportunity, Requirement, SourceDocument
from contractfit.sam_models import SamOpportunitySnapshot
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


def requirement(
    document_id: UUID, category: str, description: str, *, mandatory: bool = True
) -> Requirement:
    return Requirement(
        category=category,
        description=description,
        mandatory=mandatory,
        confidence=0.95,
        evidence=Evidence(
            document_id=document_id,
            page=2,
            section="L.3",
            supporting_text=description,
        ),
    )


def snapshot(
    opportunity_id: UUID,
    sha: str,
    observed_at: datetime,
    title: str,
) -> SamOpportunitySnapshot:
    return SamOpportunitySnapshot(
        opportunity_id=opportunity_id,
        content_sha256=sha,
        normalized_payload={"title": title, "resource_links": ["https://example.test/a.pdf"]},
        observed_at=observed_at,
    )


def test_compare_amendments_is_conservative_and_preserves_both_citations() -> None:
    opportunity_id = uuid4()
    old_document_id = uuid4()
    new_document_id = uuid4()
    observed_at = datetime(2026, 11, 1, tzinfo=UTC)
    previous_snapshot = snapshot(opportunity_id, "a" * 64, observed_at, "Original")
    current_snapshot = snapshot(
        opportunity_id, "b" * 64, observed_at + timedelta(days=1), "Amended"
    )
    unchanged_old = requirement(old_document_id, "insurance", "Carry liability insurance")
    unchanged_new = requirement(new_document_id, "Insurance", " Carry  liability insurance ")
    changed_old = requirement(old_document_id, "deadline", "Submit by November 10")
    changed_new = requirement(new_document_id, "deadline", "Submit by November 17")
    ambiguous_old = [
        requirement(old_document_id, "staffing", "Provide one supervisor"),
        requirement(old_document_id, "staffing", "Provide two technicians"),
    ]
    ambiguous_new = [
        requirement(new_document_id, "staffing", "Provide one manager"),
        requirement(new_document_id, "staffing", "Provide three technicians"),
    ]

    result = compare_amendments(
        opportunity_id,
        previous_snapshot,
        current_snapshot,
        [unchanged_old, changed_old, *ambiguous_old],
        [unchanged_new, changed_new, *ambiguous_new],
    )

    counts = {
        change_type: sum(
            item.change_type is change_type for item in result.requirement_changes
        )
        for change_type in AmendmentChangeType
    }
    assert counts == {
        AmendmentChangeType.ADDED: 2,
        AmendmentChangeType.REMOVED: 2,
        AmendmentChangeType.CHANGED: 1,
        AmendmentChangeType.UNCHANGED: 1,
    }
    changed = next(
        item
        for item in result.requirement_changes
        if item.change_type is AmendmentChangeType.CHANGED
    )
    assert changed.previous is not None and changed.current is not None
    assert changed.previous.evidence.document_id == old_document_id
    assert changed.current.evidence.document_id == new_document_id
    assert result.metadata_changes[0].field == "title"


def test_metadata_comparison_preserves_json_types_and_list_boundaries() -> None:
    opportunity_id = uuid4()
    observed_at = datetime(2026, 11, 1, tzinfo=UTC)
    previous = SamOpportunitySnapshot(
        opportunity_id=opportunity_id,
        content_sha256="1" * 64,
        normalized_payload={
            "links": ["a", "b"],
            "revision": 1,
            "nested": {"value": 1},
        },
        observed_at=observed_at,
    )
    current = SamOpportunitySnapshot(
        opportunity_id=opportunity_id,
        content_sha256="2" * 64,
        normalized_payload={
            "links": ["a | b"],
            "revision": "1",
            "nested": {"value": True},
            "new_null": None,
        },
        observed_at=observed_at + timedelta(seconds=1),
    )

    result = compare_amendments(opportunity_id, previous, current, [], [])

    changes = {item.field: item for item in result.metadata_changes}
    assert changes["links"].previous == '["a","b"]'
    assert changes["links"].current == '["a | b"]'
    assert changes["revision"].previous == "1"
    assert changes["revision"].current == '"1"'
    assert changes["nested"].previous == '{"value":1}'
    assert changes["nested"].current == '{"value":true}'
    assert changes["new_null"].previous is None
    assert changes["new_null"].current == "null"


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


def identity(email: str) -> AuthIdentity:
    organization = Organization(name=f"{email} organization")
    user = UserAccount(email=email, display_name="Reviewer", password_hash="unused")
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )


def test_documents_by_snapshot_are_persisted_and_tenant_isolated(
    store: ContractFitStore,
) -> None:
    owner = store.register_identity(identity("owner@example.com"))
    other = store.register_identity(identity("other@example.com"))
    opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="notice-1", title="SAM opportunity")
    )
    document = store.save_document(
        SourceDocument(
            organization_id=owner.organization.id,
            filename="amendment.pdf",
            content="Requirement text",
        )
    )
    store.save_document_origin(
        document.id,
        opportunity.id,
        "https://example.test/amendment.pdf",
        "c" * 64,
        owner.organization.id,
    )

    found = store.list_documents_by_origin(
        opportunity.id, "c" * 64, owner.organization.id
    )
    assert [item.id for item in found] == [document.id]
    assert found[0].filename == document.filename
    assert (
        store.list_documents_by_origin(
            opportunity.id, "c" * 64, other.organization.id
        )
        == []
    )


def test_amendment_comparison_api_uses_only_organization_documents() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    owner_registration = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Owner Facilities",
            "email": "amendments@example.com",
            "display_name": "Owner",
            "password": "a-secure-test-password",
        },
    )
    other_registration = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Other Facilities",
            "email": "other-amendments@example.com",
            "display_name": "Other",
            "password": "another-secure-password",
        },
    )
    owner = store.get_identity_by_email("amendments@example.com")
    assert owner is not None
    sam_opportunity = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="notice-api", title="SAM opportunity")
    )
    observed_at = datetime(2026, 11, 1, tzinfo=UTC)
    old_snapshot = store.save_sam_snapshot(
        snapshot(sam_opportunity.id, "d" * 64, observed_at, "Original title")
    )
    new_snapshot = store.save_sam_snapshot(
        snapshot(
            sam_opportunity.id,
            "e" * 64,
            observed_at + timedelta(days=1),
            "Amended title",
        )
    )
    for index, (item_snapshot, description) in enumerate(
        ((old_snapshot, "Submit by November 10"), (new_snapshot, "Submit by November 17"))
    ):
        document = store.save_document(
            SourceDocument(
                organization_id=owner.organization.id,
                filename=f"version-{index}.pdf",
                content=description,
                origin_opportunity_id=sam_opportunity.id,
                origin_url=f"https://example.test/version-{index}.pdf",
                origin_snapshot_sha256=item_snapshot.content_sha256,
            )
        )
        store.save_document_origin(
            document.id,
            sam_opportunity.id,
            document.origin_url or "",
            item_snapshot.content_sha256,
            owner.organization.id,
        )
        store.save_opportunity(
            Opportunity(
                source="upload",
                source_id=f"version-{index}",
                title=f"Analyzed version {index}",
                document_id=document.id,
                requirements=[requirement(document.id, "deadline", description)],
            )
        )

    owner_headers = {
        "Authorization": f"Bearer {owner_registration.json()['access_token']}"
    }
    response = client.get(
        f"/api/opportunities/{sam_opportunity.id}/amendments/compare",
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["previous_snapshot"]["id"] == str(old_snapshot.id)
    assert payload["current_snapshot"]["id"] == str(new_snapshot.id)
    assert payload["requirement_changes"][0]["change_type"] == "changed"
    assert payload["requirement_changes"][0]["previous"]["evidence"][
        "supporting_text"
    ] == "Submit by November 10"
    assert payload["requirement_changes"][0]["current"]["evidence"][
        "supporting_text"
    ] == "Submit by November 17"

    other_response = client.get(
        f"/api/opportunities/{sam_opportunity.id}/amendments/compare",
        headers={
            "Authorization": f"Bearer {other_registration.json()['access_token']}"
        },
    )
    assert other_response.status_code == 200
    assert other_response.json()["requirement_changes"] == []
    assert "Analyze attachments" in other_response.json()["limitations"][-1]

    reversed_response = client.get(
        f"/api/opportunities/{sam_opportunity.id}/amendments/compare",
        params={
            "from_snapshot_id": str(new_snapshot.id),
            "to_snapshot_id": str(old_snapshot.id),
        },
        headers=owner_headers,
    )
    assert reversed_response.status_code == 422
