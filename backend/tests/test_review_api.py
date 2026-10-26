from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from contractfit.api import (
    CreateReviewRequest,
    DismissReviewRequest,
    ResolveReviewRequest,
    configure_store,
    create_review,
    dismiss_review,
    get_review,
    list_reviews,
    resolve_review,
)
from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
)
from contractfit.domain import Evidence, Opportunity, SourceDocument
from contractfit.review import ReviewReason, ReviewStatus
from contractfit.store import InMemoryStore


def make_request(
    document_id: UUID,
    opportunity_id: UUID | None = None,
) -> CreateReviewRequest:
    return CreateReviewRequest(
        opportunity_id=opportunity_id,
        field_name="set_aside",
        extracted_value="Small business",
        confidence=0.42,
        mandatory=True,
        reason=ReviewReason.LOW_CONFIDENCE,
        evidence=[
            Evidence(
                document_id=document_id,
                supporting_text="Small business set-aside",
            )
        ],
    )


def make_identity() -> AuthIdentity:
    organization = Organization(name="Test contractor")
    user = UserAccount(
        email=f"{uuid4()}@example.com",
        display_name="Reviewer",
        password_hash="not-used-by-these-tests",
    )
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )


def test_review_api_create_list_resolve_and_conflict() -> None:
    store = InMemoryStore()
    configure_store(store)
    identity = make_identity()
    document = store.save_document(
        SourceDocument(
            organization_id=identity.organization.id,
            filename="notice.txt",
            content="Small business set-aside",
        )
    )
    item = create_review(make_request(document.id), identity)

    assert list_reviews(identity, ReviewStatus.PENDING, None) == [item]
    assert get_review(item.id, identity) == item
    resolved = resolve_review(
        item.id,
        ResolveReviewRequest(corrected_value="SBA small business"),
        identity,
    )
    assert resolved.status is ReviewStatus.RESOLVED
    with pytest.raises(HTTPException) as error:
        dismiss_review(
            item.id,
            DismissReviewRequest(),
            identity,
        )
    assert error.value.status_code == 409


def test_review_api_hides_items_from_other_organizations() -> None:
    store = InMemoryStore()
    configure_store(store)
    owner = make_identity()
    document = store.save_document(
        SourceDocument(
            organization_id=owner.organization.id,
            filename="notice.txt",
            content="Small business set-aside",
        )
    )
    item = create_review(make_request(document.id), owner)

    with pytest.raises(HTTPException) as error:
        get_review(item.id, make_identity())
    assert error.value.status_code == 404


def test_review_creation_rejects_cross_organization_references() -> None:
    store = InMemoryStore()
    configure_store(store)
    owner = make_identity()
    other = make_identity()
    owner_document = store.save_document(
        SourceDocument(
            organization_id=owner.organization.id,
            filename="owner.txt",
            content="Owner evidence",
        )
    )
    other_document = store.save_document(
        SourceDocument(
            organization_id=other.organization.id,
            filename="other.txt",
            content="Other evidence",
        )
    )
    private_opportunity = store.save_opportunity(
        Opportunity(
            source="upload",
            source_id="other-private",
            title="Other private opportunity",
            document_id=other_document.id,
        )
    )

    with pytest.raises(HTTPException) as opportunity_error:
        create_review(
            make_request(owner_document.id, private_opportunity.id),
            owner,
        )
    assert opportunity_error.value.status_code == 404

    with pytest.raises(HTTPException) as evidence_error:
        create_review(make_request(other_document.id), owner)
    assert evidence_error.value.status_code == 404


def test_review_creation_accepts_public_opportunity_with_owned_evidence() -> None:
    store = InMemoryStore()
    configure_store(store)
    identity = make_identity()
    document = store.save_document(
        SourceDocument(
            organization_id=identity.organization.id,
            filename="analysis.txt",
            content="Reviewer analysis",
        )
    )
    public_opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov",
            source_id="public-sam-notice",
            title="Public SAM opportunity",
        )
    )

    item = create_review(
        make_request(document.id, public_opportunity.id),
        identity,
    )

    assert item.opportunity_id == public_opportunity.id
    assert item.organization_id == identity.organization.id
