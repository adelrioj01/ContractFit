import math
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from contractfit.amendments import AmendmentAcknowledgement
from contractfit.auth import AuthIdentity
from contractfit.compliance import ComplianceItem, ComplianceStatus
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    Opportunity,
    ProcessingJob,
    Requirement,
    SourceDocument,
)
from contractfit.embeddings import EmbeddingHit, EmbeddingTarget, SemanticEmbedding
from contractfit.feedback import OpportunityFeedback
from contractfit.notifications import DeliveryStatus, NotificationDelivery, NotificationPreference
from contractfit.pipeline import PipelineItem
from contractfit.review import (
    ReviewItem,
    ReviewStatus,
    resolve_conflicting_value,
    review_sort_key,
)
from contractfit.sam_models import SamIngestionRun, SamOpportunitySnapshot
from contractfit.watching import OpportunityAlert, OpportunityWatch


class ContractFitStore(Protocol):
    def reset(self) -> None: ...
    def get_profile(self, organization_id: UUID | None = None) -> CompanyProfile | None: ...
    def save_profile(self, profile: CompanyProfile) -> CompanyProfile: ...
    def save_document(self, document: SourceDocument) -> SourceDocument: ...
    def get_document(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> SourceDocument | None: ...
    def find_document_by_sha256(
        self, sha256: str, organization_id: UUID
    ) -> SourceDocument | None: ...
    def find_document_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> SourceDocument | None: ...
    def save_document_origin(
        self,
        document_id: UUID,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> None: ...
    def list_documents(self, organization_id: UUID) -> list[SourceDocument]: ...
    def list_documents_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> list[SourceDocument]: ...
    def save_document_pages(self, pages: list[DocumentPage]) -> list[DocumentPage]: ...
    def list_document_pages(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> list[DocumentPage]: ...
    def save_processing_job(self, job: ProcessingJob) -> ProcessingJob: ...
    def get_processing_job(
        self, job_id: UUID, organization_id: UUID | None = None
    ) -> ProcessingJob | None: ...
    def list_processing_jobs(
        self,
        organization_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> list[ProcessingJob]: ...
    def save_opportunity(self, opportunity: Opportunity) -> Opportunity: ...
    def get_opportunity(
        self, opportunity_id: UUID, organization_id: UUID | None = None
    ) -> Opportunity | None: ...
    def get_opportunity_by_source(self, source: str, source_id: str) -> Opportunity | None: ...
    def list_opportunities(self, organization_id: UUID | None = None) -> list[Opportunity]: ...
    def get_opportunity_feedback(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> OpportunityFeedback | None: ...
    def save_opportunity_feedback(
        self, feedback: OpportunityFeedback
    ) -> OpportunityFeedback: ...
    def save_pipeline_item(self, item: PipelineItem) -> PipelineItem: ...
    def get_pipeline_item(self, item_id: UUID, organization_id: UUID) -> PipelineItem | None: ...
    def get_pipeline_item_by_opportunity(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> PipelineItem | None: ...
    def list_pipeline_items(self, organization_id: UUID) -> list[PipelineItem]: ...
    def save_compliance_item(self, item: ComplianceItem) -> ComplianceItem: ...
    def get_compliance_item(
        self, item_id: UUID, organization_id: UUID
    ) -> ComplianceItem | None: ...
    def get_compliance_item_by_requirement(
        self, requirement_id: UUID, organization_id: UUID
    ) -> ComplianceItem | None: ...
    def list_compliance_items(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[ComplianceItem]: ...
    def apply_amendment_acknowledgement(
        self,
        acknowledgement: AmendmentAcknowledgement,
        superseded_requirement_ids: list[UUID],
        new_compliance_items: list[ComplianceItem],
    ) -> AmendmentAcknowledgement: ...
    def list_amendment_acknowledgements(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[AmendmentAcknowledgement]: ...
    def save_opportunity_watch(self, watch: OpportunityWatch) -> OpportunityWatch: ...
    def get_opportunity_watch(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> OpportunityWatch | None: ...
    def list_opportunity_watches(self, organization_id: UUID) -> list[OpportunityWatch]: ...
    def delete_opportunity_watch(self, opportunity_id: UUID, organization_id: UUID) -> bool: ...
    def save_opportunity_alert(self, alert: OpportunityAlert) -> OpportunityAlert: ...
    def get_opportunity_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> OpportunityAlert | None: ...
    def get_opportunity_alert_by_dedupe_key(
        self, dedupe_key: str, organization_id: UUID
    ) -> OpportunityAlert | None: ...
    def list_opportunity_alerts(self, organization_id: UUID) -> list[OpportunityAlert]: ...
    def save_notification_preference(
        self, item: NotificationPreference
    ) -> NotificationPreference: ...
    def get_notification_preference(
        self, organization_id: UUID
    ) -> NotificationPreference | None: ...
    def list_notification_preferences(
        self, enabled_only: bool = False
    ) -> list[NotificationPreference]: ...
    def save_notification_delivery(self, item: NotificationDelivery) -> NotificationDelivery: ...
    def get_notification_delivery_by_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> NotificationDelivery | None: ...
    def list_notification_deliveries(
        self, organization_id: UUID | None = None
    ) -> list[NotificationDelivery]: ...
    def claim_notification_deliveries(
        self, max_attempts: int, limit: int = 100
    ) -> list[NotificationDelivery]: ...
    def save_sam_ingestion_run(self, run: SamIngestionRun) -> SamIngestionRun: ...
    def list_sam_ingestion_runs(self) -> list[SamIngestionRun]: ...
    def save_sam_snapshot(self, snapshot: SamOpportunitySnapshot) -> SamOpportunitySnapshot: ...
    def get_latest_sam_snapshot(self, opportunity_id: UUID) -> SamOpportunitySnapshot | None: ...
    def list_sam_snapshots(self, opportunity_id: UUID) -> list[SamOpportunitySnapshot]: ...
    def get_embedding(
        self,
        target: EmbeddingTarget,
        target_id: UUID,
        model: str,
        content_sha256: str,
    ) -> SemanticEmbedding | None: ...
    def save_embedding(self, embedding: SemanticEmbedding) -> SemanticEmbedding: ...
    def search_embeddings(
        self,
        target: EmbeddingTarget,
        model: str,
        query_vector: list[float],
        limit: int,
        organization_id: UUID | None = None,
    ) -> list[EmbeddingHit]: ...
    def save_review_item(self, item: ReviewItem) -> ReviewItem: ...
    def resolve_conflicting_review(
        self,
        review_id: UUID,
        organization_id: UUID,
        reviewer_id: UUID,
        corrected_value: str,
        note: str | None = None,
    ) -> ReviewItem: ...
    def get_review_item(self, review_id: UUID, organization_id: UUID) -> ReviewItem | None: ...
    def list_review_items(
        self,
        organization_id: UUID,
        status: ReviewStatus | None = None,
        opportunity_id: UUID | None = None,
    ) -> list[ReviewItem]: ...
    def register_identity(self, identity: AuthIdentity) -> AuthIdentity: ...
    def get_identity_by_email(self, email: str) -> AuthIdentity | None: ...
    def get_identity_by_user_id(self, user_id: UUID) -> AuthIdentity | None: ...


class InMemoryStore:
    """Replaceable repository for the first vertical slice and local demos."""

    def __init__(self) -> None:
        self.profiles: dict[UUID, CompanyProfile] = {}
        self.documents: dict[UUID, SourceDocument] = {}
        self.document_origins: dict[tuple[UUID, UUID, str, str], UUID] = {}
        self.document_pages: dict[UUID, list[DocumentPage]] = {}
        self.processing_jobs: dict[UUID, ProcessingJob] = {}
        self.opportunities: dict[UUID, Opportunity] = {}
        self.opportunity_feedback: dict[tuple[UUID, UUID], OpportunityFeedback] = {}
        self.pipeline_items: dict[UUID, PipelineItem] = {}
        self.compliance_items: dict[UUID, ComplianceItem] = {}
        self.amendment_acknowledgements: dict[UUID, AmendmentAcknowledgement] = {}
        self.opportunity_watches: dict[UUID, OpportunityWatch] = {}
        self.opportunity_alerts: dict[UUID, OpportunityAlert] = {}
        self.notification_preferences: dict[UUID, NotificationPreference] = {}
        self.notification_deliveries: dict[UUID, NotificationDelivery] = {}
        self.sam_ingestion_runs: dict[UUID, SamIngestionRun] = {}
        self.sam_snapshots: dict[UUID, SamOpportunitySnapshot] = {}
        self.embeddings: dict[tuple[EmbeddingTarget, UUID, str], SemanticEmbedding] = {}
        self.review_items: dict[UUID, ReviewItem] = {}
        self._review_lock = RLock()
        self._amendment_lock = RLock()
        self.identities: dict[UUID, AuthIdentity] = {}

    def reset(self) -> None:
        self.profiles.clear()
        self.documents.clear()
        self.document_origins.clear()
        self.document_pages.clear()
        self.processing_jobs.clear()
        self.opportunities.clear()
        self.opportunity_feedback.clear()
        self.pipeline_items.clear()
        self.compliance_items.clear()
        self.amendment_acknowledgements.clear()
        self.opportunity_watches.clear()
        self.opportunity_alerts.clear()
        self.notification_preferences.clear()
        self.notification_deliveries.clear()
        self.sam_ingestion_runs.clear()
        self.sam_snapshots.clear()
        self.embeddings.clear()
        self.review_items.clear()
        self.identities.clear()

    def save_profile(self, profile: CompanyProfile) -> CompanyProfile:
        self.profiles[profile.organization_id] = profile
        return profile

    def get_profile(self, organization_id: UUID | None = None) -> CompanyProfile | None:
        if organization_id is not None:
            return self.profiles.get(organization_id)
        # Temporary compatibility path for background processing. Documents and
        # jobs will supply an organization once their tenant boundary is added.
        return next(iter(self.profiles.values()), None)

    def save_document(self, document: SourceDocument) -> SourceDocument:
        self.documents[document.id] = document
        return document

    def get_document(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> SourceDocument | None:
        document = self.documents.get(document_id)
        if (
            document is not None
            and organization_id is not None
            and document.organization_id != organization_id
        ):
            return None
        return document

    def find_document_by_sha256(self, sha256: str, organization_id: UUID) -> SourceDocument | None:
        return next(
            (
                item
                for item in self.documents.values()
                if item.sha256 == sha256 and item.organization_id == organization_id
            ),
            None,
        )

    def find_document_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> SourceDocument | None:
        document_id = self.document_origins.get(
            (organization_id, origin_opportunity_id, origin_url, origin_snapshot_sha256)
        )
        if document_id is not None:
            return self.get_document(document_id, organization_id)
        return next(
            (
                item
                for item in self.documents.values()
                if item.origin_opportunity_id == origin_opportunity_id
                and item.origin_url == origin_url
                and item.origin_snapshot_sha256 == origin_snapshot_sha256
                and item.organization_id == organization_id
            ),
            None,
        )

    def save_document_origin(
        self,
        document_id: UUID,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> None:
        document = self.get_document(document_id, organization_id)
        if document is None:
            raise ValueError("document is not visible to the organization")
        self.document_origins[
            (organization_id, origin_opportunity_id, origin_url, origin_snapshot_sha256)
        ] = document_id

    def list_documents(self, organization_id: UUID) -> list[SourceDocument]:
        return [item for item in self.documents.values() if item.organization_id == organization_id]

    def list_documents_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> list[SourceDocument]:
        document_ids = {
            document_id
            for (
                tenant_id,
                opportunity_id,
                _,
                snapshot_sha256,
            ), document_id in self.document_origins.items()
            if tenant_id == organization_id
            and opportunity_id == origin_opportunity_id
            and snapshot_sha256 == origin_snapshot_sha256
        }
        document_ids.update(
            item.id
            for item in self.documents.values()
            if item.organization_id == organization_id
            and item.origin_opportunity_id == origin_opportunity_id
            and item.origin_snapshot_sha256 == origin_snapshot_sha256
        )
        return sorted(
            (self.documents[item_id] for item_id in document_ids),
            key=lambda item: (item.filename.casefold(), str(item.id)),
        )

    def save_document_pages(self, pages: list[DocumentPage]) -> list[DocumentPage]:
        if pages:
            self.document_pages[pages[0].document_id] = pages
        return pages

    def list_document_pages(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> list[DocumentPage]:
        if self.get_document(document_id, organization_id) is None:
            return []
        return self.document_pages.get(document_id, [])

    def save_processing_job(self, job: ProcessingJob) -> ProcessingJob:
        self.processing_jobs[job.id] = job
        return job

    def get_processing_job(
        self, job_id: UUID, organization_id: UUID | None = None
    ) -> ProcessingJob | None:
        job = self.processing_jobs.get(job_id)
        if job is None or self.get_document(job.document_id, organization_id) is None:
            return None
        return job

    def list_processing_jobs(
        self,
        organization_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> list[ProcessingJob]:
        jobs = list(self.processing_jobs.values())
        if organization_id is not None:
            jobs = [
                job
                for job in jobs
                if self.get_document(job.document_id, organization_id) is not None
            ]
        if document_id is not None:
            jobs = [job for job in jobs if job.document_id == document_id]
        return jobs

    def save_opportunity(self, opportunity: Opportunity) -> Opportunity:
        self.opportunities[opportunity.id] = opportunity
        return opportunity

    def get_opportunity(
        self, opportunity_id: UUID, organization_id: UUID | None = None
    ) -> Opportunity | None:
        opportunity = self.opportunities.get(opportunity_id)
        if opportunity is None or organization_id is None:
            return opportunity
        if opportunity.document_id is None:
            return opportunity
        if self.get_document(opportunity.document_id, organization_id) is None:
            return None
        return opportunity

    def get_opportunity_by_source(self, source: str, source_id: str) -> Opportunity | None:
        return next(
            (
                item
                for item in self.opportunities.values()
                if item.source == source and item.source_id == source_id
            ),
            None,
        )

    def list_opportunities(self, organization_id: UUID | None = None) -> list[Opportunity]:
        opportunities = list(self.opportunities.values())
        if organization_id is None:
            return opportunities
        return [
            item
            for item in opportunities
            if item.document_id is None
            or self.get_document(item.document_id, organization_id) is not None
        ]

    def get_opportunity_feedback(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> OpportunityFeedback | None:
        return self.opportunity_feedback.get((organization_id, opportunity_id))

    def save_opportunity_feedback(self, feedback: OpportunityFeedback) -> OpportunityFeedback:
        key = (feedback.organization_id, feedback.opportunity_id)
        existing = self.opportunity_feedback.get(key)
        if existing is not None:
            feedback = feedback.model_copy(
                update={"id": existing.id, "created_at": existing.created_at}
            )
        self.opportunity_feedback[key] = feedback
        return feedback

    def save_pipeline_item(self, item: PipelineItem) -> PipelineItem:
        if self.get_opportunity(item.opportunity_id, item.organization_id) is None:
            raise ValueError("pipeline opportunity is not visible to the organization")
        duplicate = self.get_pipeline_item_by_opportunity(item.opportunity_id, item.organization_id)
        if duplicate is not None and duplicate.id != item.id:
            raise ValueError("opportunity is already in the pipeline")
        self.pipeline_items[item.id] = item
        return item

    def get_pipeline_item(self, item_id: UUID, organization_id: UUID) -> PipelineItem | None:
        item = self.pipeline_items.get(item_id)
        return item if item is not None and item.organization_id == organization_id else None

    def get_pipeline_item_by_opportunity(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> PipelineItem | None:
        return next(
            (
                item
                for item in self.pipeline_items.values()
                if item.organization_id == organization_id and item.opportunity_id == opportunity_id
            ),
            None,
        )

    def list_pipeline_items(self, organization_id: UUID) -> list[PipelineItem]:
        return sorted(
            (
                item
                for item in self.pipeline_items.values()
                if item.organization_id == organization_id
            ),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )

    def save_compliance_item(self, item: ComplianceItem) -> ComplianceItem:
        with self._amendment_lock:
            return self._save_compliance_item_unlocked(item)

    def _save_compliance_item_unlocked(self, item: ComplianceItem) -> ComplianceItem:
        opportunity = self.get_opportunity(item.opportunity_id, item.organization_id)
        if opportunity is None:
            raise ValueError("compliance opportunity is not visible to the organization")
        requirement = self._compliance_requirement(item)
        if requirement is None:
            raise ValueError("compliance requirement does not belong to the opportunity")
        duplicate = self.get_compliance_item_by_requirement(
            item.requirement_id, item.organization_id
        )
        if duplicate is not None and duplicate.id != item.id:
            raise ValueError("requirement is already in the compliance matrix")
        if item.source_evidence != requirement.evidence:
            raise ValueError("source evidence cannot differ from the extracted requirement")
        self.compliance_items[item.id] = item
        return item

    def _compliance_requirement(self, item: ComplianceItem) -> Requirement | None:
        for opportunity in self.list_opportunities(item.organization_id):
            requirement = next(
                (entry for entry in opportunity.requirements if entry.id == item.requirement_id),
                None,
            )
            if requirement is None:
                continue
            if opportunity.id == item.opportunity_id:
                return requirement
            document = (
                self.get_document(opportunity.document_id, item.organization_id)
                if opportunity.document_id is not None
                else None
            )
            if document is not None and document.origin_opportunity_id == item.opportunity_id:
                return requirement
        return None

    def get_compliance_item(self, item_id: UUID, organization_id: UUID) -> ComplianceItem | None:
        item = self.compliance_items.get(item_id)
        return item if item is not None and item.organization_id == organization_id else None

    def get_compliance_item_by_requirement(
        self, requirement_id: UUID, organization_id: UUID
    ) -> ComplianceItem | None:
        return next(
            (
                item
                for item in self.compliance_items.values()
                if item.requirement_id == requirement_id and item.organization_id == organization_id
            ),
            None,
        )

    def list_compliance_items(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[ComplianceItem]:
        return sorted(
            (
                item
                for item in self.compliance_items.values()
                if item.opportunity_id == opportunity_id and item.organization_id == organization_id
            ),
            key=lambda item: (item.created_at, str(item.id)),
        )

    def apply_amendment_acknowledgement(
        self,
        acknowledgement: AmendmentAcknowledgement,
        superseded_requirement_ids: list[UUID],
        new_compliance_items: list[ComplianceItem],
    ) -> AmendmentAcknowledgement:
        with self._amendment_lock:
            existing = next(
                (
                    item
                    for item in self.amendment_acknowledgements.values()
                    if item.organization_id == acknowledgement.organization_id
                    and item.opportunity_id == acknowledgement.opportunity_id
                    and item.previous_snapshot_id == acknowledgement.previous_snapshot_id
                    and item.current_snapshot_id == acknowledgement.current_snapshot_id
                ),
                None,
            )
            if existing is not None:
                if existing.selections != acknowledgement.selections:
                    raise ValueError("amendment version pair was acknowledged differently")
                return existing
            if (
                self.get_opportunity(
                    acknowledgement.opportunity_id, acknowledgement.organization_id
                )
                is None
            ):
                raise ValueError("amendment opportunity is not visible to the organization")
            snapshots = {
                item.id: item for item in self.list_sam_snapshots(acknowledgement.opportunity_id)
            }
            if (
                acknowledgement.previous_snapshot_id not in snapshots
                or acknowledgement.current_snapshot_id not in snapshots
            ):
                raise ValueError("amendment snapshots do not belong to the opportunity")
            reviewer = self.get_identity_by_user_id(acknowledgement.acknowledged_by_user_id)
            if reviewer is None or reviewer.organization.id != acknowledgement.organization_id:
                raise ValueError("acknowledging user does not belong to the organization")
            for item in new_compliance_items:
                if item.organization_id != acknowledgement.organization_id or (
                    item.opportunity_id != acknowledgement.opportunity_id
                ):
                    raise ValueError("compliance update belongs to another workspace")
                requirement = self._compliance_requirement(item)
                if requirement is None or item.source_evidence != requirement.evidence:
                    raise ValueError("compliance update has invalid requirement evidence")
            previous_items = dict(self.compliance_items)
            try:
                now = datetime.now(UTC)
                for requirement_id in superseded_requirement_ids:
                    existing_item = self.get_compliance_item_by_requirement(
                        requirement_id, acknowledgement.organization_id
                    )
                    if (
                        existing_item is not None
                        and existing_item.opportunity_id == acknowledgement.opportunity_id
                    ):
                        self.compliance_items[existing_item.id] = existing_item.model_copy(
                            update={
                                "status": ComplianceStatus.NOT_APPLICABLE,
                                "updated_at": now,
                            }
                        )
                for item in new_compliance_items:
                    if (
                        self.get_compliance_item_by_requirement(
                            item.requirement_id, acknowledgement.organization_id
                        )
                        is None
                    ):
                        self.save_compliance_item(item)
                self.amendment_acknowledgements[acknowledgement.id] = acknowledgement
            except Exception:
                self.compliance_items = previous_items
                raise
            return acknowledgement

    def list_amendment_acknowledgements(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[AmendmentAcknowledgement]:
        return sorted(
            (
                item
                for item in self.amendment_acknowledgements.values()
                if item.opportunity_id == opportunity_id and item.organization_id == organization_id
            ),
            key=lambda item: (item.acknowledged_at, str(item.id)),
            reverse=True,
        )

    def save_opportunity_watch(self, watch: OpportunityWatch) -> OpportunityWatch:
        if self.get_opportunity(watch.opportunity_id, watch.organization_id) is None:
            raise ValueError("watch opportunity is not visible to the organization")
        existing = self.get_opportunity_watch(watch.opportunity_id, watch.organization_id)
        if existing is not None and existing.id != watch.id:
            raise ValueError("opportunity is already watched")
        self.opportunity_watches[watch.id] = watch
        return watch

    def get_opportunity_watch(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> OpportunityWatch | None:
        return next(
            (
                item
                for item in self.opportunity_watches.values()
                if item.opportunity_id == opportunity_id and item.organization_id == organization_id
            ),
            None,
        )

    def list_opportunity_watches(self, organization_id: UUID) -> list[OpportunityWatch]:
        return sorted(
            (
                item
                for item in self.opportunity_watches.values()
                if item.organization_id == organization_id
            ),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )

    def delete_opportunity_watch(self, opportunity_id: UUID, organization_id: UUID) -> bool:
        watch = self.get_opportunity_watch(opportunity_id, organization_id)
        if watch is None:
            return False
        del self.opportunity_watches[watch.id]
        self.opportunity_alerts = {
            alert_id: alert
            for alert_id, alert in self.opportunity_alerts.items()
            if alert.watch_id != watch.id
        }
        return True

    def save_opportunity_alert(self, alert: OpportunityAlert) -> OpportunityAlert:
        watch = self.opportunity_watches.get(alert.watch_id)
        if watch is None or watch.organization_id != alert.organization_id:
            raise ValueError("alert watch is not visible to the organization")
        duplicate = self.get_opportunity_alert_by_dedupe_key(
            alert.dedupe_key, alert.organization_id
        )
        if duplicate is not None and duplicate.id != alert.id:
            return duplicate
        self.opportunity_alerts[alert.id] = alert
        return alert

    def get_opportunity_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> OpportunityAlert | None:
        alert = self.opportunity_alerts.get(alert_id)
        return alert if alert is not None and alert.organization_id == organization_id else None

    def get_opportunity_alert_by_dedupe_key(
        self, dedupe_key: str, organization_id: UUID
    ) -> OpportunityAlert | None:
        return next(
            (
                item
                for item in self.opportunity_alerts.values()
                if item.dedupe_key == dedupe_key and item.organization_id == organization_id
            ),
            None,
        )

    def list_opportunity_alerts(self, organization_id: UUID) -> list[OpportunityAlert]:
        return sorted(
            (
                item
                for item in self.opportunity_alerts.values()
                if item.organization_id == organization_id
            ),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )

    def save_notification_preference(self, item: NotificationPreference) -> NotificationPreference:
        if item.organization_id not in {
            identity.organization.id for identity in self.identities.values()
        }:
            raise ValueError("notification organization does not exist")
        self.notification_preferences[item.organization_id] = item
        return item

    def get_notification_preference(self, organization_id: UUID) -> NotificationPreference | None:
        return self.notification_preferences.get(organization_id)

    def list_notification_preferences(
        self, enabled_only: bool = False
    ) -> list[NotificationPreference]:
        items = list(self.notification_preferences.values())
        return [item for item in items if item.enabled] if enabled_only else items

    def save_notification_delivery(self, item: NotificationDelivery) -> NotificationDelivery:
        existing = self.get_notification_delivery_by_alert(item.alert_id, item.organization_id)
        if existing is not None and existing.id != item.id:
            return existing
        self.notification_deliveries[item.id] = item
        return item

    def get_notification_delivery_by_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> NotificationDelivery | None:
        return next(
            (
                item
                for item in self.notification_deliveries.values()
                if item.alert_id == alert_id and item.organization_id == organization_id
            ),
            None,
        )

    def list_notification_deliveries(
        self, organization_id: UUID | None = None
    ) -> list[NotificationDelivery]:
        items = self.notification_deliveries.values()
        return sorted(
            (
                item
                for item in items
                if organization_id is None or item.organization_id == organization_id
            ),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )

    def claim_notification_deliveries(
        self, max_attempts: int, limit: int = 100
    ) -> list[NotificationDelivery]:
        now = datetime.now(UTC)
        candidates = [
            item
            for item in reversed(self.list_notification_deliveries())
            if item.status in {DeliveryStatus.PENDING, DeliveryStatus.FAILED}
            and item.attempts < max_attempts
        ][:limit]
        claimed = [
            item.model_copy(update={"status": DeliveryStatus.PROCESSING, "updated_at": now})
            for item in candidates
        ]
        for item in claimed:
            self.notification_deliveries[item.id] = item
        return claimed

    def save_sam_ingestion_run(self, run: SamIngestionRun) -> SamIngestionRun:
        self.sam_ingestion_runs[run.id] = run
        return run

    def list_sam_ingestion_runs(self) -> list[SamIngestionRun]:
        return sorted(
            self.sam_ingestion_runs.values(),
            key=lambda item: item.started_at,
        )

    def save_sam_snapshot(self, snapshot: SamOpportunitySnapshot) -> SamOpportunitySnapshot:
        if snapshot.opportunity_id not in self.opportunities:
            raise ValueError("SAM snapshot opportunity does not exist")
        self.sam_snapshots[snapshot.id] = snapshot
        return snapshot

    def get_latest_sam_snapshot(self, opportunity_id: UUID) -> SamOpportunitySnapshot | None:
        snapshots = self.list_sam_snapshots(opportunity_id)
        return snapshots[-1] if snapshots else None

    def list_sam_snapshots(self, opportunity_id: UUID) -> list[SamOpportunitySnapshot]:
        return sorted(
            (item for item in self.sam_snapshots.values() if item.opportunity_id == opportunity_id),
            key=lambda item: (item.observed_at, str(item.id)),
        )

    def get_embedding(
        self,
        target: EmbeddingTarget,
        target_id: UUID,
        model: str,
        content_sha256: str,
    ) -> SemanticEmbedding | None:
        embedding = self.embeddings.get((target, target_id, model))
        if embedding is None or embedding.content_sha256 != content_sha256:
            return None
        return embedding

    def save_embedding(self, embedding: SemanticEmbedding) -> SemanticEmbedding:
        self.embeddings[(embedding.target, embedding.target_id, embedding.model)] = embedding
        return embedding

    def search_embeddings(
        self,
        target: EmbeddingTarget,
        model: str,
        query_vector: list[float],
        limit: int,
        organization_id: UUID | None = None,
    ) -> list[EmbeddingHit]:
        def cosine_score(vector: list[float]) -> float:
            dot = sum(left * right for left, right in zip(query_vector, vector, strict=True))
            query_norm = math.sqrt(sum(value * value for value in query_vector))
            vector_norm = math.sqrt(sum(value * value for value in vector))
            if query_norm == 0 or vector_norm == 0:
                return 0.0
            return float(max(0.0, min(1.0, dot / (query_norm * vector_norm))))

        candidates = [
            item
            for item in self.embeddings.values()
            if item.target is target
            and item.model == model
            and item.organization_id == organization_id
        ]
        hits = [
            EmbeddingHit(target_id=item.target_id, score=cosine_score(item.vector))
            for item in candidates
        ]
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]

    def save_review_item(self, item: ReviewItem) -> ReviewItem:
        if (
            item.opportunity_id is not None
            and self.get_opportunity(item.opportunity_id, item.organization_id) is None
        ):
            raise ValueError("review opportunity is not visible to the organization")
        if any(
            self.get_document(evidence.document_id, item.organization_id) is None
            for evidence in item.evidence
        ):
            raise ValueError("review evidence document is not owned by the organization")
        self.review_items[item.id] = item
        return item

    def resolve_conflicting_review(
        self,
        review_id: UUID,
        organization_id: UUID,
        reviewer_id: UUID,
        corrected_value: str,
        note: str | None = None,
    ) -> ReviewItem:
        with self._review_lock:
            item = self.get_review_item(review_id, organization_id)
            if item is None or item.opportunity_id is None:
                raise LookupError("review not found")
            opportunity = self.get_opportunity(item.opportunity_id, organization_id)
            if opportunity is None:
                raise LookupError("opportunity not found")
            resolved, updated_opportunity = resolve_conflicting_value(
                item,
                opportunity,
                reviewer_id=reviewer_id,
                corrected_value=corrected_value,
                note=note,
            )
            self.opportunities[updated_opportunity.id] = updated_opportunity
            self.review_items[resolved.id] = resolved
            return resolved

    def get_review_item(self, review_id: UUID, organization_id: UUID) -> ReviewItem | None:
        item = self.review_items.get(review_id)
        return item if item is not None and item.organization_id == organization_id else None

    def list_review_items(
        self,
        organization_id: UUID,
        status: ReviewStatus | None = None,
        opportunity_id: UUID | None = None,
    ) -> list[ReviewItem]:
        items = [
            item
            for item in self.review_items.values()
            if item.organization_id == organization_id
            and (status is None or item.status is status)
            and (opportunity_id is None or item.opportunity_id == opportunity_id)
        ]
        return sorted(items, key=review_sort_key)

    def register_identity(self, identity: AuthIdentity) -> AuthIdentity:
        if self.get_identity_by_email(identity.user.email) is not None:
            raise ValueError("email is already registered")
        self.identities[identity.user.id] = identity
        return identity

    def get_identity_by_email(self, email: str) -> AuthIdentity | None:
        normalized = email.strip().lower()
        return next(
            (
                identity
                for identity in self.identities.values()
                if identity.user.email == normalized
            ),
            None,
        )

    def get_identity_by_user_id(self, user_id: UUID) -> AuthIdentity | None:
        return self.identities.get(user_id)
