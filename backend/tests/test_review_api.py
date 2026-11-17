from datetime import date
from decimal import Decimal
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
from contractfit.domain import Evidence, Opportunity, Requirement, SourceDocument
from contractfit.review import ReviewReason, ReviewStatus, build_requirement_reviews
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


def make_conflicting_review(
    store: InMemoryStore,
    identity: AuthIdentity,
    *,
    category: str,
    values: tuple[str, str],
    public: bool = False,
):
    document = store.save_document(
        SourceDocument(
            organization_id=identity.organization.id,
            filename=f"{category}.txt",
            content="\n".join(values),
        )
    )
    opportunity = store.save_opportunity(
        Opportunity(
            source="sam.gov" if public else "upload",
            source_id=f"conflict-{category}-{uuid4()}",
            title=f"Conflicting {category}",
            document_id=None if public else document.id,
            requirements=[
                Requirement(
                    category=category,
                    description=value,
                    mandatory=True,
                    confidence=0.5,
                    evidence=Evidence(
                        document_id=document.id,
                        page=index,
                        supporting_text=f"Candidate {value}",
                    ),
                )
                for index, value in enumerate(values, start=1)
            ],
        )
    )
    review = store.save_review_item(
        build_requirement_reviews(opportunity, identity.organization.id)[0]
    )
    return opportunity, review


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


@pytest.mark.parametrize(
    ("category", "field_name", "values", "corrected_value", "expected_value"),
    [
        (
            "deadline",
            "response_deadline",
            ("2099-02-15", "2099-03-01"),
            "2099-03-01",
            date(2099, 3, 1),
        ),
        (
            "location",
            "place_of_performance",
            ("Austin, TX", "Dallas, TX"),
            " Dallas, TX ",
            "Dallas, TX",
        ),
        (
            "set_aside",
            "set_aside",
            ("Small Business", "8(a)"),
            "8(a)",
            "8(a)",
        ),
        (
            "value",
            "estimated_value",
            ("100000", "200000.00"),
            "$200,000.00",
            Decimal("200000.00"),
        ),
    ],
)
def test_resolve_grouped_conflict_updates_private_opportunity_scalar(
    category: str,
    field_name: str,
    values: tuple[str, str],
    corrected_value: str,
    expected_value: object,
) -> None:
    store = InMemoryStore()
    configure_store(store)
    identity = make_identity()
    opportunity, review = make_conflicting_review(
        store, identity, category=category, values=values
    )

    resolved = resolve_review(
        review.id,
        ResolveReviewRequest(corrected_value=corrected_value),
        identity,
    )

    persisted = store.get_opportunity(opportunity.id, identity.organization.id)
    assert resolved.status is ReviewStatus.RESOLVED
    assert persisted is not None
    assert getattr(persisted, field_name) == expected_value


@pytest.mark.parametrize(
    ("category", "values", "invalid_value"),
    [
        ("deadline", ("2099-02-15", "2099-03-01"), "March 1, 2099"),
        ("location", ("Austin, TX", "Dallas, TX"), "Mars"),
        ("set_aside", ("Small Business", "8(a)"), "   "),
        ("value", ("100000", "200000"), "NaN"),
    ],
)
def test_invalid_conflict_correction_does_not_mutate_review_or_opportunity(
    category: str,
    values: tuple[str, str],
    invalid_value: str,
) -> None:
    store = InMemoryStore()
    configure_store(store)
    identity = make_identity()
    opportunity, review = make_conflicting_review(
        store, identity, category=category, values=values
    )
    before = store.get_opportunity(opportunity.id, identity.organization.id)

    with pytest.raises(HTTPException) as error:
        resolve_review(
            review.id,
            ResolveReviewRequest(corrected_value=invalid_value),
            identity,
        )

    assert error.value.status_code in {409, 422}
    assert store.get_opportunity(opportunity.id, identity.organization.id) == before
    persisted_review = store.get_review_item(review.id, identity.organization.id)
    assert persisted_review is not None
    assert persisted_review.status is ReviewStatus.PENDING
    assert persisted_review.corrected_value is None


def test_grouped_conflict_resolution_rejects_public_opportunity() -> None:
    store = InMemoryStore()
    configure_store(store)
    identity = make_identity()
    opportunity, review = make_conflicting_review(
        store,
        identity,
        category="deadline",
        values=("2099-02-15", "2099-03-01"),
        public=True,
    )

    with pytest.raises(HTTPException) as error:
        resolve_review(
            review.id,
            ResolveReviewRequest(corrected_value="2099-03-01"),
            identity,
        )

    assert error.value.status_code in {409, 422}
    assert store.get_opportunity(opportunity.id, identity.organization.id) == opportunity
    assert store.get_review_item(review.id, identity.organization.id) == review


def test_grouped_conflict_resolution_is_hidden_from_other_organizations() -> None:
    store = InMemoryStore()
    configure_store(store)
    owner = make_identity()
    other = make_identity()
    opportunity, review = make_conflicting_review(
        store,
        owner,
        category="deadline",
        values=("2099-02-15", "2099-03-01"),
    )

    with pytest.raises(HTTPException) as error:
        resolve_review(
            review.id,
            ResolveReviewRequest(corrected_value="2099-03-01"),
            other,
        )

    assert error.value.status_code == 404
    persisted = store.get_opportunity(opportunity.id, owner.organization.id)
    assert persisted is not None
    assert persisted.response_deadline is None
    assert store.get_review_item(review.id, owner.organization.id) == review
