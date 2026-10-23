from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contractfit.domain import Evidence
from contractfit.review import (
    ReviewItem,
    ReviewPriority,
    ReviewReason,
    ReviewStatus,
    calculate_priority_score,
    review_sort_key,
)


def make_item(**overrides: object) -> ReviewItem:
    document_id = uuid4()
    values: dict[str, object] = {
        "organization_id": uuid4(),
        "opportunity_id": uuid4(),
        "field_name": "response_deadline",
        "extracted_value": "2026-12-01",
        "confidence": 0.55,
        "mandatory": True,
        "reason": ReviewReason.LOW_CONFIDENCE,
        "evidence": [
            Evidence(
                document_id=document_id,
                page=3,
                section="Submission deadline",
                supporting_text="Responses are due December 1, 2026.",
            )
        ],
    }
    values.update(overrides)
    return ReviewItem.model_validate(values)


def test_pending_item_preserves_organization_and_evidence() -> None:
    item = make_item()

    assert item.status is ReviewStatus.PENDING
    assert item.organization_id is not None
    assert item.evidence[0].page == 3
    assert item.evidence[0].supporting_text == "Responses are due December 1, 2026."
    assert item.reviewer_id is None
    assert item.resolved_at is None


@pytest.mark.parametrize("field_name", ["", "   "])
def test_field_name_cannot_be_blank(field_name: str) -> None:
    with pytest.raises(ValidationError, match="field_name"):
        make_item(field_name=field_name)


def test_review_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        make_item(evidence=[])


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_is_bounded(confidence: float) -> None:
    with pytest.raises(ValidationError):
        make_item(confidence=confidence)


def test_resolve_records_correction_reviewer_and_audit_time_without_mutation() -> None:
    created_at = datetime(2026, 10, 23, 12, tzinfo=UTC)
    decided_at = created_at + timedelta(minutes=4)
    reviewer_id = uuid4()
    pending = make_item(created_at=created_at, updated_at=created_at)

    resolved = pending.resolve(
        reviewer_id=reviewer_id,
        corrected_value="2026-12-02",
        note="Confirmed in amendment 2",
        at=decided_at,
    )

    assert pending.status is ReviewStatus.PENDING
    assert resolved.status is ReviewStatus.RESOLVED
    assert resolved.corrected_value == "2026-12-02"
    assert resolved.reviewer_id == reviewer_id
    assert resolved.resolution_note == "Confirmed in amendment 2"
    assert resolved.resolved_at == decided_at
    assert resolved.updated_at == decided_at
    assert resolved.created_at == created_at


def test_dismiss_records_auditable_decision_without_correction() -> None:
    decided_at = datetime(2026, 10, 23, 13, tzinfo=UTC)
    dismissed = make_item(created_at=decided_at).dismiss(
        reviewer_id=uuid4(), note="Duplicate extraction", at=decided_at
    )

    assert dismissed.status is ReviewStatus.DISMISSED
    assert dismissed.corrected_value is None
    assert dismissed.resolution_note == "Duplicate extraction"
    assert dismissed.resolved_at == decided_at


@pytest.mark.parametrize("terminal_status", [ReviewStatus.RESOLVED, ReviewStatus.DISMISSED])
def test_terminal_item_requires_reviewer_and_resolution_time(
    terminal_status: ReviewStatus,
) -> None:
    with pytest.raises(ValidationError, match="reviewer_id and resolved_at"):
        make_item(status=terminal_status)


def test_resolved_item_requires_correction() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="corrected_value"):
        make_item(
            status=ReviewStatus.RESOLVED,
            reviewer_id=uuid4(),
            created_at=now,
            updated_at=now,
            resolved_at=now,
        )


def test_pending_item_rejects_resolution_data() -> None:
    with pytest.raises(ValidationError, match="pending reviews"):
        make_item(reviewer_id=uuid4())


def test_terminal_reviews_cannot_transition_again() -> None:
    resolved = make_item().resolve(reviewer_id=uuid4(), corrected_value="corrected")

    with pytest.raises(ValueError, match="cannot transition"):
        resolved.dismiss(reviewer_id=uuid4())


def test_transitions_reject_blank_review_text() -> None:
    with pytest.raises(ValidationError, match="review text"):
        make_item().resolve(reviewer_id=uuid4(), corrected_value="   ")


@pytest.mark.parametrize(
    ("mandatory", "confidence", "reason", "expected_score", "expected_priority"),
    [
        (True, 0.0, ReviewReason.MISSING_VALUE, 100, ReviewPriority.CRITICAL),
        (True, 0.9, ReviewReason.LOW_CONFIDENCE, 53, ReviewPriority.HIGH),
        (False, 0.5, ReviewReason.OCR_UNCERTAIN, 30, ReviewPriority.MEDIUM),
        (False, 1.0, ReviewReason.OTHER, 0, ReviewPriority.LOW),
    ],
)
def test_priority_is_deterministic(
    mandatory: bool,
    confidence: float,
    reason: ReviewReason,
    expected_score: int,
    expected_priority: ReviewPriority,
) -> None:
    item = make_item(mandatory=mandatory, confidence=confidence, reason=reason)

    assert calculate_priority_score(
        mandatory=mandatory, confidence=confidence, reason=reason
    ) == expected_score
    assert item.priority_score == expected_score
    assert item.priority is expected_priority


def test_review_sort_key_orders_by_priority_then_uncertainty_then_age() -> None:
    now = datetime(2026, 10, 23, 14, tzinfo=UTC)
    critical = make_item(
        confidence=0.0,
        reason=ReviewReason.MISSING_VALUE,
        created_at=now,
        updated_at=now,
    )
    older_uncertain = make_item(
        mandatory=False,
        confidence=0.2,
        reason=ReviewReason.OTHER,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    newer_certain = make_item(
        mandatory=False,
        confidence=0.8,
        reason=ReviewReason.OCR_UNCERTAIN,
        created_at=now,
        updated_at=now,
    )

    ordered = sorted([newer_certain, older_uncertain, critical], key=review_sort_key)

    assert ordered == [critical, older_uncertain, newer_certain]


def test_timestamps_must_be_aware_and_ordered() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_item(created_at=datetime(2026, 10, 23))
    with pytest.raises(ValidationError, match="cannot precede"):
        make_item(created_at=now, updated_at=now - timedelta(seconds=1))

