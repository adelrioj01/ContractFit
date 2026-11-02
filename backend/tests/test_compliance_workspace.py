import csv
import io
from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contractfit.api import (
    CreatePipelineItemRequest,
    UpdateComplianceItemRequest,
    configure_store,
    create_pipeline_item,
    get_opportunity_workspace,
    initialize_compliance_matrix,
    router,
    update_compliance_item,
)
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.compliance import (
    BusinessEvidence,
    ComplianceItem,
    ComplianceStatus,
    RequirementPriority,
)
from contractfit.database import Base, build_session_factory
from contractfit.domain import Evidence, Opportunity, Requirement, SourceDocument
from contractfit.pipeline import PipelineStatus
from contractfit.sql_store import SqlAlchemyStore
from contractfit.store import ContractFitStore, InMemoryStore


class RacingStore(InMemoryStore):
    """Simulate another request winning the unique-key race."""

    def save_compliance_item(self, item: ComplianceItem) -> ComplianceItem:
        super().save_compliance_item(item)
        raise ValueError("requirement is already in the compliance matrix")


def make_identity(email: str) -> AuthIdentity:
    organization = Organization(name=f"{email} Facilities")
    user = UserAccount(email=email, display_name="Bid manager", password_hash="not-used")
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


def seed_workspace(store: ContractFitStore, identity: AuthIdentity) -> Opportunity:
    document = store.save_document(
        SourceDocument(
            organization_id=identity.organization.id,
            filename="solicitation.txt",
            content="Insurance is required.",
            origin_opportunity_id=None,
        )
    )
    requirement = Requirement(
        category="insurance",
        description="Maintain general liability insurance",
        mandatory=True,
        confidence=0.98,
        evidence=Evidence(
            document_id=document.id,
            page=3,
            section="L.2",
            supporting_text="General liability insurance is required.",
        ),
    )
    opportunity = Opportunity(
        source="upload",
        source_id=str(uuid4()),
        title="Facilities maintenance",
        document_id=document.id,
        requirements=[requirement],
    )
    return store.save_opportunity(opportunity)


def test_compliance_matrix_round_trip_and_traceability(store: ContractFitStore) -> None:
    configure_store(store)
    identity = store.register_identity(make_identity("owner@example.com"))
    opportunity = seed_workspace(store, identity)
    create_pipeline_item(
        CreatePipelineItemRequest(
            opportunity_id=opportunity.id, status=PipelineStatus.PURSUE
        ),
        identity,
    )

    items = initialize_compliance_matrix(opportunity.id, identity)
    assert len(items) == 1
    assert items[0].priority is RequirementPriority.MANDATORY
    assert items[0].status is ComplianceStatus.PENDING
    assert items[0].source_evidence == opportunity.requirements[0].evidence

    updated = update_compliance_item(
        items[0].id,
        UpdateComplianceItemRequest(
            status=ComplianceStatus.COVERED,
            business_evidence=[
                BusinessEvidence(
                    kind="profile",
                    reference_id="insurance_coverages",
                    description="General liability coverage recorded in company profile",
                )
            ],
            owner_user_id=identity.user.id,
            due_date=date(2026, 11, 15),
            notes="Obtain current certificate before submission.",
        ),
        identity,
    )
    workspace = get_opportunity_workspace(opportunity.id, identity)
    assert workspace.compliance_items == [updated]
    assert workspace.documents[0].id == opportunity.document_id
    assert updated.source_evidence.page == 3
    assert updated.business_evidence[0].reference_id == "insurance_coverages"
    assert initialize_compliance_matrix(opportunity.id, identity) == [updated]


def test_compliance_requires_pursue_and_isolated_by_organization(
    store: ContractFitStore,
) -> None:
    configure_store(store)
    owner = store.register_identity(make_identity("owner@example.com"))
    other = store.register_identity(make_identity("other@example.com"))
    opportunity = seed_workspace(store, owner)

    with pytest.raises(HTTPException) as not_pursuing:
        initialize_compliance_matrix(opportunity.id, owner)
    assert not_pursuing.value.status_code == 409

    create_pipeline_item(
        CreatePipelineItemRequest(
            opportunity_id=opportunity.id, status=PipelineStatus.PURSUE
        ),
        owner,
    )
    item = initialize_compliance_matrix(opportunity.id, owner)[0]
    with pytest.raises(HTTPException) as hidden_workspace:
        get_opportunity_workspace(opportunity.id, other)
    assert hidden_workspace.value.status_code == 404
    with pytest.raises(HTTPException) as hidden_item:
        update_compliance_item(
            item.id,
            UpdateComplianceItemRequest(status=ComplianceStatus.NOT_APPLICABLE),
            other,
        )
    assert hidden_item.value.status_code == 404


def test_compliance_http_api_preserves_source_evidence() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Compliance Facilities",
            "email": "compliance@example.com",
            "display_name": "Compliance owner",
            "password": "a-secure-test-password",
        },
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    identity = store.get_identity_by_email("compliance@example.com")
    assert identity is not None
    opportunity = seed_workspace(store, identity)
    client.post(
        "/api/pipeline/items",
        headers=headers,
        json={"opportunity_id": str(opportunity.id), "status": "pursue"},
    )

    initialized = client.post(
        f"/api/opportunities/{opportunity.id}/compliance/initialize", headers=headers
    )
    assert initialized.status_code == 200
    item = initialized.json()[0]
    assert item["source_evidence"]["supporting_text"] == (
        "General liability insurance is required."
    )
    unsupported = client.patch(
        f"/api/compliance/items/{item['id']}",
        headers=headers,
        json={"status": "covered"},
    )
    assert unsupported.status_code == 422
    patched = client.patch(
        f"/api/compliance/items/{item['id']}",
        headers=headers,
        json={"status": "missing_evidence", "priority": "recommended"},
    )
    assert patched.status_code == 200
    detail = client.get(f"/api/opportunities/{opportunity.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["compliance_items"][0]["status"] == "missing_evidence"


def test_compliance_initialization_treats_concurrent_winner_as_idempotent() -> None:
    store = RacingStore()
    configure_store(store)
    identity = store.register_identity(make_identity("race@example.com"))
    opportunity = seed_workspace(store, identity)
    create_pipeline_item(
        CreatePipelineItemRequest(
            opportunity_id=opportunity.id, status=PipelineStatus.PURSUE
        ),
        identity,
    )

    items = initialize_compliance_matrix(opportunity.id, identity)

    assert len(items) == 1
    assert items[0].requirement_id == opportunity.requirements[0].id


def test_compliance_csv_export_is_auditable_safe_and_tenant_isolated() -> None:
    store = InMemoryStore()
    configure_store(store)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    owner_registration = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Export Facilities",
            "email": "export@example.com",
            "display_name": "Export owner",
            "password": "a-secure-test-password",
        },
    )
    owner_headers = {
        "Authorization": f"Bearer {owner_registration.json()['access_token']}"
    }
    owner = store.get_identity_by_email("export@example.com")
    assert owner is not None
    opportunity = seed_workspace(store, owner)
    client.post(
        "/api/pipeline/items",
        headers=owner_headers,
        json={"opportunity_id": str(opportunity.id), "status": "pursue"},
    )
    item = client.post(
        f"/api/opportunities/{opportunity.id}/compliance/initialize",
        headers=owner_headers,
    ).json()[0]
    patched = client.patch(
        f"/api/compliance/items/{item['id']}",
        headers=owner_headers,
        json={
            "status": "covered",
            "owner_user_id": str(owner.user.id),
            "due_date": "2026-11-15",
            "notes": "=HYPERLINK(\"https://example.invalid\")",
            "business_evidence": [
                {
                    "kind": "profile",
                    "reference_id": "insurance_coverages",
                    "description": "Verified general liability coverage",
                }
            ],
        },
    )
    assert patched.status_code == 200

    exported = client.get(
        f"/api/opportunities/{opportunity.id}/compliance/export.csv",
        headers=owner_headers,
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "text/csv; charset=utf-8"
    assert exported.headers["content-disposition"] == (
        f'attachment; filename="compliance-{opportunity.id}.csv"'
    )
    rows = list(
        csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig")))
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["opportunity_id"] == str(opportunity.id)
    assert row["requirement_id"] == item["requirement_id"]
    assert row["owner_name"] == "Export owner"
    assert row["due_date"] == "2026-11-15"
    assert row["source_document_id"] == item["source_evidence"]["document_id"]
    assert row["source_document_filename"] == "solicitation.txt"
    assert row["source_page"] == "3"
    assert row["source_section"] == "L.2"
    assert row["source_text"] == "General liability insurance is required."
    assert '"reference_id":"insurance_coverages"' in row["business_evidence_json"]
    assert row["notes"].startswith("'=HYPERLINK")

    other_registration = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Other Facilities",
            "email": "other-export@example.com",
            "display_name": "Other owner",
            "password": "another-secure-password",
        },
    )
    hidden = client.get(
        f"/api/opportunities/{opportunity.id}/compliance/export.csv",
        headers={
            "Authorization": f"Bearer {other_registration.json()['access_token']}"
        },
    )
    assert hidden.status_code == 404
