import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy.engine import make_url

from contractfit.amendments import (
    AmendmentAcknowledgement,
    AmendmentChangeType,
    AmendmentSelection,
)
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.compliance import ComplianceItem, ComplianceStatus, RequirementPriority
from contractfit.database import build_engine, build_session_factory
from contractfit.domain import Evidence, Opportunity, Requirement, SourceDocument
from contractfit.sam_models import SamOpportunitySnapshot
from contractfit.sql_store import SqlAlchemyStore

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ
    or os.environ.get("CONTRACTFIT_ALLOW_TEST_DB_RESET") != "1",
    reason="requires an explicitly enabled, migrated PostgreSQL test database",
)


def test_concurrent_identical_amendment_acknowledgements_return_one_winner() -> None:
    database_name = make_url(os.environ["DATABASE_URL"]).database
    assert database_name is not None and database_name.endswith("_test"), (
        "destructive integration tests require a database name ending in _test"
    )
    session_factory = build_session_factory(build_engine(os.environ["DATABASE_URL"]))
    store = SqlAlchemyStore(session_factory)
    store.reset()
    organization = Organization(name="Concurrent amendment contractor")
    user = UserAccount(
        email="concurrent-amendment@example.com",
        display_name="Amendment admin",
        password_hash="unused",
    )
    identity = store.register_identity(
        AuthIdentity(
            user=user,
            organization=organization,
            membership=OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.ADMIN,
            ),
        )
    )
    catalog = store.save_opportunity(
        Opportunity(source="sam.gov", source_id="postgres-race", title="Amended work")
    )
    observed_at = datetime(2026, 11, 3, tzinfo=UTC)
    previous_snapshot = store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=catalog.id,
            content_sha256="a" * 64,
            normalized_payload={"revision": 1},
            observed_at=observed_at,
        )
    )
    current_snapshot = store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=catalog.id,
            content_sha256="b" * 64,
            normalized_payload={"revision": 2},
            observed_at=observed_at + timedelta(days=1),
        )
    )
    requirements = []
    for index, (snapshot, description) in enumerate(
        (
            (previous_snapshot, "Submit by November 10"),
            (current_snapshot, "Submit by November 17"),
        )
    ):
        document = store.save_document(
            SourceDocument(
                organization_id=organization.id,
                filename=f"amendment-{index}.txt",
                content=description,
                origin_opportunity_id=catalog.id,
                origin_url=f"https://sam.gov/example-{index}",
                origin_snapshot_sha256=snapshot.content_sha256,
            )
        )
        requirement = Requirement(
            category="deadline",
            description=description,
            mandatory=True,
            confidence=1,
            evidence=Evidence(document_id=document.id, supporting_text=description),
        )
        requirements.append(requirement)
        store.save_opportunity(
            Opportunity(
                source="upload",
                source_id=f"postgres-race-{index}",
                title=f"Analyzed revision {index}",
                document_id=document.id,
                requirements=[requirement],
            )
        )
    previous_requirement, current_requirement = requirements
    store.save_compliance_item(
        ComplianceItem(
            organization_id=organization.id,
            opportunity_id=catalog.id,
            requirement_id=previous_requirement.id,
            description=previous_requirement.description,
            category=previous_requirement.category,
            priority=RequirementPriority.MANDATORY,
            status=ComplianceStatus.COVERED,
            source_evidence=previous_requirement.evidence,
            notes="must survive the partial update",
        )
    )
    selection = AmendmentSelection(
        change_type=AmendmentChangeType.CHANGED,
        previous_requirement_id=previous_requirement.id,
        current_requirement_id=current_requirement.id,
    )
    current_item = ComplianceItem(
        organization_id=organization.id,
        opportunity_id=catalog.id,
        requirement_id=current_requirement.id,
        description=current_requirement.description,
        category=current_requirement.category,
        priority=RequirementPriority.MANDATORY,
        source_evidence=current_requirement.evidence,
    )
    barrier = Barrier(2)

    def acknowledge() -> AmendmentAcknowledgement:
        local_store = SqlAlchemyStore(session_factory)
        acknowledgement = AmendmentAcknowledgement(
            organization_id=organization.id,
            opportunity_id=catalog.id,
            previous_snapshot_id=previous_snapshot.id,
            current_snapshot_id=current_snapshot.id,
            selections=[selection],
            acknowledged_by_user_id=identity.user.id,
        )
        barrier.wait(timeout=10)
        return local_store.apply_amendment_acknowledgement(
            acknowledgement,
            [previous_requirement.id],
            [current_item],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(acknowledge) for _ in range(2)]
        acknowledgements = [future.result(timeout=20) for future in futures]

    assert acknowledgements[0].id == acknowledgements[1].id
    assert len(store.list_amendment_acknowledgements(catalog.id, organization.id)) == 1
    items = {
        item.requirement_id: item
        for item in store.list_compliance_items(catalog.id, organization.id)
    }
    assert items[previous_requirement.id].status is ComplianceStatus.NOT_APPLICABLE
    assert items[previous_requirement.id].notes == "must survive the partial update"
    assert items[current_requirement.id].status is ComplianceStatus.PENDING

    third_snapshot = store.save_sam_snapshot(
        SamOpportunitySnapshot(
            opportunity_id=catalog.id,
            content_sha256="c" * 64,
            normalized_payload={"revision": 3},
            observed_at=observed_at + timedelta(days=2),
        )
    )
    conflict_barrier = Barrier(2)
    removed = AmendmentSelection(
        change_type=AmendmentChangeType.REMOVED,
        previous_requirement_id=current_requirement.id,
    )
    added = AmendmentSelection(
        change_type=AmendmentChangeType.ADDED,
        current_requirement_id=previous_requirement.id,
    )

    def acknowledge_conflict(
        conflict_selection: AmendmentSelection,
        superseded: list[UUID],
    ) -> AmendmentAcknowledgement:
        local_store = SqlAlchemyStore(session_factory)
        acknowledgement = AmendmentAcknowledgement(
            organization_id=organization.id,
            opportunity_id=catalog.id,
            previous_snapshot_id=current_snapshot.id,
            current_snapshot_id=third_snapshot.id,
            selections=[conflict_selection],
            acknowledged_by_user_id=identity.user.id,
        )
        conflict_barrier.wait(timeout=10)
        return local_store.apply_amendment_acknowledgement(
            acknowledgement,
            superseded,
            [],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        conflict_futures = [
            executor.submit(acknowledge_conflict, removed, [current_requirement.id]),
            executor.submit(acknowledge_conflict, added, []),
        ]
        conflict_results: list[AmendmentAcknowledgement] = []
        conflict_errors: list[ValueError] = []
        for future in conflict_futures:
            try:
                conflict_results.append(future.result(timeout=20))
            except ValueError as exc:
                conflict_errors.append(exc)

    assert len(conflict_results) == 1
    assert len(conflict_errors) == 1
    assert str(conflict_errors[0]) in {
        "amendment version pair was acknowledged differently",
        "amendment acknowledgement conflicts with stored data",
    }
    assert len(store.list_amendment_acknowledgements(catalog.id, organization.id)) == 2
    current_after_conflict = store.get_compliance_item_by_requirement(
        current_requirement.id, organization.id
    )
    assert current_after_conflict is not None
    winning_change = conflict_results[0].selections[0].change_type
    expected_status = (
        ComplianceStatus.NOT_APPLICABLE
        if winning_change is AmendmentChangeType.REMOVED
        else ComplianceStatus.PENDING
    )
    assert current_after_conflict.status is expected_status
