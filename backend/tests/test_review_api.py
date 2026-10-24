from uuid import uuid4

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
from contractfit.domain import Evidence
from contractfit.review import ReviewReason, ReviewStatus
from contractfit.store import InMemoryStore


def make_request() -> CreateReviewRequest:
    return CreateReviewRequest(
        field_name="set_aside",
        extracted_value="Small business",
        confidence=0.42,
        mandatory=True,
        reason=ReviewReason.LOW_CONFIDENCE,
        evidence=[Evidence(document_id=uuid4(), supporting_text="Small business set-aside")],
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
    configure_store(InMemoryStore())
    identity = make_identity()
    item = create_review(make_request(), identity)

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
    configure_store(InMemoryStore())
    item = create_review(make_request(), make_identity())

    with pytest.raises(HTTPException) as error:
        get_review(item.id, make_identity())
    assert error.value.status_code == 404
