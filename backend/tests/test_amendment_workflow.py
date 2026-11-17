from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.amendments import (
    AmendmentAcknowledgement,
    AmendmentChangeType,
    AmendmentSelection,
)
from contractfit.api import configure_store, router
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
    create_access_token,
)
from contractfit.compliance import (
    BusinessEvidence,
    ComplianceItem,
    ComplianceStatus,
    RequirementPriority,
)
from contractfit.config import get_settings
from contractfit.database import Base, build_session_factory
from contractfit.domain import Evidence, Opportunity, Requirement, SourceDocument
from contractfit.pipeline import PipelineItem, PipelineStatus
from contractfit.sam_models import SamOpportunitySnapshot
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


def _identity(email: str, role: OrganizationRole = OrganizationRole.ADMIN) -> AuthIdentity:
    organization = Organization(name=f"{email} organization")
    user = UserAccount(email=email, display_name="Reviewer", password_hash="unused")
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
        ),
    )


def _requirement(document_id: UUID, description: str) -> Requirement:
    return Requirement(
        category="deadline",
        description=description,
        mandatory=True,
        confidence=0.98,
        evidence=Evidence(
            document_id=document_id,
            page=2,
            section="L.3",
            supporting_text=description,
        ),
    )


def test_selected_amendment_change_is_audited_and_updates_compliance_atomically(
    store: ContractFitStore,
) -> None:
    owner = store.register_identity(_identity("owner-workflow@example.com"))
    other = store.register_identity(_identity("other-workflow@example.com"))
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    settings = get_settings()
    owner_headers = {
        "Authorization": f"Bearer {create_access_token(owner, settings.auth_secret_key)}"
    }
    other_headers = {
        "Authorization": f"Bearer {create_access_token(other, settings.auth_secret_key)}"
    }

    catalog = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="workflow-notice", title="Amended work")
    )
    observed_at = datetime(2026, 11, 1, tzinfo=UTC)
    old_snapshot = store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=catalog.id,
            content_sha256="a" * 64,
            normalized_payload={"title": "Original"},
            observed_at=observed_at,
        )
    )
    new_snapshot = store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=catalog.id,
            content_sha256="b" * 64,
            normalized_payload={"title": "Amended"},
            observed_at=observed_at + timedelta(days=1),
        )
    )
    requirements = []
    for index, (snapshot, description) in enumerate(
        (
            (old_snapshot, "Submit by November 10"),
            (new_snapshot, "Submit by November 17"),
        )
    ):
        document = store.save_document(
            SourceDocument(
                organization_id=owner.organization.id,
                filename=f"version-{index}.pdf",
                content=description,
                origin_opportunity_id=catalog.id,
                origin_url=f"https://example.test/version-{index}.pdf",
                origin_snapshot_sha256=snapshot.content_sha256,
            )
        )
        store.save_document_origin(
            document.id,
            catalog.id,
            document.origin_url or "",
            snapshot.content_sha256,
            owner.organization.id,
        )
        requirement = _requirement(document.id, description)
        requirements.append(requirement)
        store.save_opportunity(
            Opportunity(
                source="upload",
                source_id=f"workflow-version-{index}",
                title=f"Analyzed version {index}",
                document_id=document.id,
                requirements=[requirement],
            )
        )

    store.save_pipeline_item(
        PipelineItem(
            organization_id=owner.organization.id,
            opportunity_id=catalog.id,
            owner_user_id=owner.user.id,
            status=PipelineStatus.PURSUE,
        )
    )
    old_requirement, new_requirement = requirements
    old_item = store.save_compliance_item(
        ComplianceItem(
            organization_id=owner.organization.id,
            opportunity_id=catalog.id,
            requirement_id=old_requirement.id,
            description=old_requirement.description,
            category=old_requirement.category,
            priority=RequirementPriority.MANDATORY,
            status=ComplianceStatus.COVERED,
            source_evidence=old_requirement.evidence,
            business_evidence=[
                BusinessEvidence(kind="project", description="Verified delivery plan")
            ],
        )
    )
    payload = {
        "previous_snapshot_id": str(old_snapshot.id),
        "current_snapshot_id": str(new_snapshot.id),
        "selections": [
            {
                "change_type": "changed",
                "previous_requirement_id": str(old_requirement.id),
                "current_requirement_id": str(new_requirement.id),
            }
        ],
    }

    response = client.post(
        f"/api/opportunities/{catalog.id}/amendments/acknowledge",
        json=payload,
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["acknowledgement"]["acknowledged_by_user_id"] == str(owner.user.id)
    items = {item["requirement_id"]: item for item in body["compliance_items"]}
    assert items[str(old_requirement.id)]["id"] == str(old_item.id)
    assert items[str(old_requirement.id)]["status"] == "not_applicable"
    assert items[str(old_requirement.id)]["business_evidence"] == [
        {
            "kind": "project",
            "reference_id": None,
            "description": "Verified delivery plan",
        }
    ]
    assert items[str(new_requirement.id)]["status"] == "pending"
    assert items[str(new_requirement.id)]["business_evidence"] == []
    assert items[str(new_requirement.id)]["source_evidence"]["supporting_text"] == (
        "Submit by November 17"
    )

    repeated = client.post(
        f"/api/opportunities/{catalog.id}/amendments/acknowledge",
        json=payload,
        headers=owner_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["acknowledgement"]["id"] == body["acknowledgement"]["id"]
    assert len(repeated.json()["compliance_items"]) == 2

    owner_history = client.get(
        f"/api/opportunities/{catalog.id}/amendments/acknowledgements",
        headers=owner_headers,
    )
    assert owner_history.status_code == 200
    assert len(owner_history.json()) == 1
    other_history = client.get(
        f"/api/opportunities/{catalog.id}/amendments/acknowledgements",
        headers=other_headers,
    )
    assert other_history.status_code == 200
    assert other_history.json() == []


def test_acknowledgement_rejects_unverified_selection(store: ContractFitStore) -> None:
    owner = store.register_identity(_identity("invalid-selection@example.com"))
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    settings = get_settings()
    headers = {"Authorization": f"Bearer {create_access_token(owner, settings.auth_secret_key)}"}
    catalog = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="invalid-notice", title="Invalid")
    )
    observed_at = datetime(2026, 11, 1, tzinfo=UTC)
    snapshots = [
        store.save_sam_snapshot(
            SamOpportunitySnapshot(
                opportunity_id=catalog.id,
                content_sha256=character * 64,
                normalized_payload={"revision": index},
                observed_at=observed_at + timedelta(days=index),
            )
        )
        for index, character in enumerate(("c", "d"))
    ]
    store.save_pipeline_item(
        PipelineItem(
            organization_id=owner.organization.id,
            opportunity_id=catalog.id,
            owner_user_id=owner.user.id,
            status=PipelineStatus.PURSUE,
        )
    )

    response = client.post(
        f"/api/opportunities/{catalog.id}/amendments/acknowledge",
        json={
            "previous_snapshot_id": str(snapshots[0].id),
            "current_snapshot_id": str(snapshots[1].id),
            "selections": [
                {
                    "change_type": "added",
                    "current_requirement_id": str(uuid4()),
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 409
    assert "not in this comparison" in response.json()["detail"]
    assert store.list_amendment_acknowledgements(catalog.id, owner.organization.id) == []


def test_acknowledgement_selections_are_canonical_and_order_independent() -> None:
    organization_id = uuid4()
    opportunity_id = uuid4()
    previous_snapshot_id = uuid4()
    current_snapshot_id = uuid4()
    user_id = uuid4()
    first = AmendmentSelection(
        change_type=AmendmentChangeType.REMOVED,
        previous_requirement_id=uuid4(),
    )
    second = AmendmentSelection(
        change_type=AmendmentChangeType.ADDED,
        current_requirement_id=uuid4(),
    )
    common = {
        "organization_id": organization_id,
        "opportunity_id": opportunity_id,
        "previous_snapshot_id": previous_snapshot_id,
        "current_snapshot_id": current_snapshot_id,
        "acknowledged_by_user_id": user_id,
    }

    forward = AmendmentAcknowledgement(**common, selections=[first, second])
    reverse = AmendmentAcknowledgement(**common, selections=[second, first])

    assert forward.selections == reverse.selections


def test_reviewer_cannot_apply_amendment_changes(store: ContractFitStore) -> None:
    reviewer = store.register_identity(
        _identity("reviewer-amendment@example.com", OrganizationRole.REVIEWER)
    )
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    settings = get_settings()
    headers = {"Authorization": f"Bearer {create_access_token(reviewer, settings.auth_secret_key)}"}
    catalog = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="reviewer-notice", title="Restricted")
    )
    store.save_pipeline_item(
        PipelineItem(
            organization_id=reviewer.organization.id,
            opportunity_id=catalog.id,
            owner_user_id=reviewer.user.id,
            status=PipelineStatus.PURSUE,
        )
    )

    response = client.post(
        f"/api/opportunities/{catalog.id}/amendments/acknowledge",
        json={
            "previous_snapshot_id": str(uuid4()),
            "current_snapshot_id": str(uuid4()),
            "selections": [{"change_type": "added", "current_requirement_id": str(uuid4())}],
        },
        headers=headers,
    )

    assert response.status_code == 403
