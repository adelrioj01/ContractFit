"""Deterministic, evidence-preserving comparison of solicitation amendments."""

import json
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from contractfit.domain import Evidence, Requirement
from contractfit.sam_models import SamOpportunitySnapshot


class AmendmentChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class RequirementVersion(BaseModel):
    id: UUID
    category: str
    description: str
    mandatory: bool
    evidence: Evidence


class RequirementChange(BaseModel):
    change_type: AmendmentChangeType
    previous: RequirementVersion | None = None
    current: RequirementVersion | None = None


class MetadataChange(BaseModel):
    field: str
    previous: str | None = None
    current: str | None = None


class AmendmentComparison(BaseModel):
    opportunity_id: UUID
    previous_snapshot: SamOpportunitySnapshot
    current_snapshot: SamOpportunitySnapshot
    metadata_changes: list[MetadataChange]
    requirement_changes: list[RequirementChange]
    limitations: list[str]


class AmendmentSelection(BaseModel):
    """A human-selected material change, identified only by extracted requirements."""

    change_type: AmendmentChangeType
    previous_requirement_id: UUID | None = None
    current_requirement_id: UUID | None = None

    @model_validator(mode="after")
    def validate_material_change(self) -> "AmendmentSelection":
        if self.change_type is AmendmentChangeType.UNCHANGED:
            raise ValueError("unchanged requirements cannot be selected")
        if self.change_type is AmendmentChangeType.ADDED and self.current_requirement_id is None:
            raise ValueError("added selections require a current requirement")
        if self.change_type is AmendmentChangeType.REMOVED and self.previous_requirement_id is None:
            raise ValueError("removed selections require a previous requirement")
        if self.change_type is AmendmentChangeType.CHANGED and (
            self.previous_requirement_id is None or self.current_requirement_id is None
        ):
            raise ValueError("changed selections require both requirement versions")
        return self


class AmendmentAcknowledgement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    opportunity_id: UUID
    previous_snapshot_id: UUID
    current_snapshot_id: UUID
    selections: list[AmendmentSelection] = Field(min_length=1)
    acknowledged_by_user_id: UUID
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def canonicalize_selections(self) -> "AmendmentAcknowledgement":
        def key(item: AmendmentSelection) -> tuple[str, str, str]:
            return (
                item.change_type.value,
                str(item.previous_requirement_id or ""),
                str(item.current_requirement_id or ""),
            )

        if len({key(item) for item in self.selections}) != len(self.selections):
            raise ValueError("amendment selections must be unique")
        self.selections = sorted(self.selections, key=key)
        return self


def compare_amendments(
    opportunity_id: UUID,
    previous_snapshot: SamOpportunitySnapshot,
    current_snapshot: SamOpportunitySnapshot,
    previous_requirements: list[Requirement],
    current_requirements: list[Requirement],
) -> AmendmentComparison:
    """Compare two versions without semantic guesses or mutating compliance work."""

    if previous_snapshot.opportunity_id != opportunity_id:
        raise ValueError("previous snapshot belongs to another opportunity")
    if current_snapshot.opportunity_id != opportunity_id:
        raise ValueError("current snapshot belongs to another opportunity")
    if (previous_snapshot.observed_at, str(previous_snapshot.id)) >= (
        current_snapshot.observed_at,
        str(current_snapshot.id),
    ):
        raise ValueError("previous snapshot must be older than current snapshot")

    metadata_changes = []
    fields = sorted(
        set(previous_snapshot.normalized_payload) | set(current_snapshot.normalized_payload)
    )
    for field in fields:
        previous_present = field in previous_snapshot.normalized_payload
        current_present = field in current_snapshot.normalized_payload
        previous = (
            _metadata_value(previous_snapshot.normalized_payload[field])
            if previous_present
            else None
        )
        current = (
            _metadata_value(current_snapshot.normalized_payload[field]) if current_present else None
        )
        if previous_present != current_present or previous != current:
            metadata_changes.append(
                MetadataChange(
                    field=field,
                    previous=previous,
                    current=current,
                )
            )

    changes = _compare_requirements(previous_requirements, current_requirements)
    limitations = [
        "Requirement matching is deterministic and conservative; ambiguous pairs are not inferred.",
        "The comparison does not update compliance decisions automatically.",
    ]
    if not previous_requirements or not current_requirements:
        limitations.append(
            "Analyze attachments for both snapshots to compare extracted requirements."
        )
    return AmendmentComparison(
        opportunity_id=opportunity_id,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        metadata_changes=metadata_changes,
        requirement_changes=changes,
        limitations=limitations,
    )


def _compare_requirements(
    previous: list[Requirement], current: list[Requirement]
) -> list[RequirementChange]:
    previous_buckets: dict[tuple[str, str, bool], list[Requirement]] = defaultdict(list)
    current_buckets: dict[tuple[str, str, bool], list[Requirement]] = defaultdict(list)
    for requirement in previous:
        previous_buckets[_signature(requirement)].append(requirement)
    for requirement in current:
        current_buckets[_signature(requirement)].append(requirement)

    changes: list[RequirementChange] = []
    unmatched_previous: list[Requirement] = []
    unmatched_current: list[Requirement] = []
    for signature in sorted(set(previous_buckets) | set(current_buckets)):
        old_items = sorted(previous_buckets[signature], key=lambda item: str(item.id))
        new_items = sorted(current_buckets[signature], key=lambda item: str(item.id))
        matched_count = min(len(old_items), len(new_items))
        for index in range(matched_count):
            changes.append(
                RequirementChange(
                    change_type=AmendmentChangeType.UNCHANGED,
                    previous=_version(old_items[index]),
                    current=_version(new_items[index]),
                )
            )
        unmatched_previous.extend(old_items[matched_count:])
        unmatched_current.extend(new_items[matched_count:])

    old_by_category = _by_category(unmatched_previous)
    new_by_category = _by_category(unmatched_current)
    for category in sorted(set(old_by_category) | set(new_by_category)):
        old_items = old_by_category[category]
        new_items = new_by_category[category]
        if len(old_items) == 1 and len(new_items) == 1:
            changes.append(
                RequirementChange(
                    change_type=AmendmentChangeType.CHANGED,
                    previous=_version(old_items[0]),
                    current=_version(new_items[0]),
                )
            )
            continue
        changes.extend(
            RequirementChange(
                change_type=AmendmentChangeType.REMOVED,
                previous=_version(item),
            )
            for item in old_items
        )
        changes.extend(
            RequirementChange(
                change_type=AmendmentChangeType.ADDED,
                current=_version(item),
            )
            for item in new_items
        )

    order = {
        AmendmentChangeType.CHANGED: 0,
        AmendmentChangeType.ADDED: 1,
        AmendmentChangeType.REMOVED: 2,
        AmendmentChangeType.UNCHANGED: 3,
    }

    def sort_key(item: RequirementChange) -> tuple[int, str, str]:
        version = item.current or item.previous
        if version is None:
            raise ValueError("requirement change must contain a version")
        return (
            order[item.change_type],
            _normalize(version.category),
            _normalize(version.description),
        )

    return sorted(changes, key=sort_key)


def _by_category(requirements: list[Requirement]) -> dict[str, list[Requirement]]:
    grouped: dict[str, list[Requirement]] = defaultdict(list)
    for requirement in requirements:
        grouped[_normalize(requirement.category)].append(requirement)
    for items in grouped.values():
        items.sort(key=lambda item: (_normalize(item.description), str(item.id)))
    return grouped


def _signature(requirement: Requirement) -> tuple[str, str, bool]:
    return (
        _normalize(requirement.category),
        _normalize(requirement.description),
        requirement.mandatory,
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _version(requirement: Requirement) -> RequirementVersion:
    return RequirementVersion.model_validate(requirement.model_dump())


def _metadata_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
