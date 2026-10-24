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
from contractfit.domain import Evidence
from contractfit.review import ReviewReason, ReviewStatus
from contractfit.store import InMemoryStore


def make_request(organization_id: UUID) -> CreateReviewRequest:
    return CreateReviewRequest(
        organization_id=organization_id,
        field_name="set_aside",
        extracted_value="Small business",
        confidence=0.42,
        mandatory=True,
        reason=ReviewReason.LOW_CONFIDENCE,
        evidence=[Evidence(document_id=uuid4(), supporting_text="Small business set-aside")],
    )


def test_review_api_create_list_resolve_and_conflict() -> None:
    configure_store(InMemoryStore())
    organization_id = uuid4()
    item = create_review(make_request(organization_id))

    assert list_reviews(organization_id, ReviewStatus.PENDING, None) == [item]
    assert get_review(item.id, organization_id) == item
    resolved = resolve_review(
        item.id,
        ResolveReviewRequest(
            organization_id=organization_id,
            reviewer_id=uuid4(),
            corrected_value="SBA small business",
        ),
    )
    assert resolved.status is ReviewStatus.RESOLVED
    with pytest.raises(HTTPException) as error:
        dismiss_review(
            item.id,
            DismissReviewRequest(organization_id=organization_id, reviewer_id=uuid4()),
        )
    assert error.value.status_code == 409


def test_review_api_hides_items_from_other_organizations() -> None:
    configure_store(InMemoryStore())
    item = create_review(make_request(uuid4()))

    with pytest.raises(HTTPException) as error:
        get_review(item.id, uuid4())
    assert error.value.status_code == 404
