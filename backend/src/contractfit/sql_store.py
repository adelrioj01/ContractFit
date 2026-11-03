from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from contractfit.amendments import AmendmentAcknowledgement, AmendmentSelection
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
from contractfit.database import transaction
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    DocumentStatus,
    Evidence,
    Opportunity,
    PastPerformanceProject,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStage,
    Requirement,
    SourceDocument,
)
from contractfit.embeddings import EmbeddingHit, EmbeddingTarget, SemanticEmbedding
from contractfit.notifications import DeliveryStatus, NotificationDelivery, NotificationPreference
from contractfit.persistence_models import (
    AmendmentAcknowledgementRecord,
    CompanyProfileRecord,
    ComplianceItemRecord,
    DocumentOriginRecord,
    DocumentPageRecord,
    NotificationDeliveryRecord,
    NotificationPreferenceRecord,
    OpportunityAlertRecord,
    OpportunityRecord,
    OpportunityWatchRecord,
    OrganizationMembershipRecord,
    OrganizationRecord,
    PipelineItemRecord,
    ProcessingJobRecord,
    RequirementRecord,
    ReviewEvidenceRecord,
    ReviewItemRecord,
    SamIngestionRunRecord,
    SamOpportunitySnapshotRecord,
    SemanticEmbeddingRecord,
    SourceDocumentRecord,
    UserAccountRecord,
)
from contractfit.pipeline import PipelineItem, PipelineStatus
from contractfit.review import (
    ReviewItem,
    ReviewReason,
    ReviewStatus,
    resolve_conflicting_value,
    review_sort_key,
)
from contractfit.sam_models import (
    SamIngestionRun,
    SamIngestionStatus,
    SamOpportunitySnapshot,
)
from contractfit.watching import AlertStatus, AlertType, OpportunityAlert, OpportunityWatch


def _ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SqlAlchemyStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def reset(self) -> None:
        with transaction(self.session_factory) as session:
            session.execute(delete(AmendmentAcknowledgementRecord))
            session.execute(delete(ComplianceItemRecord))
            session.execute(delete(SemanticEmbeddingRecord))
            session.execute(delete(ReviewEvidenceRecord))
            session.execute(delete(ReviewItemRecord))
            session.execute(delete(NotificationDeliveryRecord))
            session.execute(delete(OpportunityAlertRecord))
            session.execute(delete(NotificationPreferenceRecord))
            session.execute(delete(OpportunityWatchRecord))
            session.execute(delete(PipelineItemRecord))
            session.execute(delete(DocumentOriginRecord))
            session.execute(delete(SamOpportunitySnapshotRecord))
            session.execute(delete(SamIngestionRunRecord))
            session.execute(delete(RequirementRecord))
            session.execute(delete(OpportunityRecord))
            session.execute(delete(ProcessingJobRecord))
            session.execute(delete(DocumentPageRecord))
            session.execute(delete(SourceDocumentRecord))
            session.execute(delete(CompanyProfileRecord))
            session.execute(delete(OrganizationMembershipRecord))
            session.execute(delete(UserAccountRecord))
            session.execute(delete(OrganizationRecord))

    def get_profile(self, organization_id: UUID | None = None) -> CompanyProfile | None:
        with transaction(self.session_factory) as session:
            statement = select(CompanyProfileRecord)
            if organization_id is not None:
                statement = statement.where(CompanyProfileRecord.organization_id == organization_id)
            record = session.scalars(statement.limit(1)).first()
            return self._profile_from_record(record) if record else None

    def save_profile(self, profile: CompanyProfile) -> CompanyProfile:
        with transaction(self.session_factory) as session:
            payload = profile.model_dump()
            payload["past_performance"] = [
                project.model_dump(mode="json") for project in profile.past_performance
            ]
            session.merge(CompanyProfileRecord(**payload))
        return profile

    def save_document(self, document: SourceDocument) -> SourceDocument:
        with transaction(self.session_factory) as session:
            payload = document.model_dump()
            payload["status"] = document.status.value
            session.merge(SourceDocumentRecord(**payload))
        return document

    def get_document(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> SourceDocument | None:
        with transaction(self.session_factory) as session:
            statement = select(SourceDocumentRecord).where(SourceDocumentRecord.id == document_id)
            if organization_id is not None:
                statement = statement.where(SourceDocumentRecord.organization_id == organization_id)
            record = session.scalars(statement).first()
            return self._document_from_record(record) if record else None

    def find_document_by_sha256(self, sha256: str, organization_id: UUID) -> SourceDocument | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(SourceDocumentRecord).where(
                    SourceDocumentRecord.sha256 == sha256,
                    SourceDocumentRecord.organization_id == organization_id,
                )
            ).first()
            return self._document_from_record(record) if record else None

    def find_document_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> SourceDocument | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(SourceDocumentRecord)
                .join(
                    DocumentOriginRecord,
                    DocumentOriginRecord.document_id == SourceDocumentRecord.id,
                )
                .where(
                    DocumentOriginRecord.opportunity_id == origin_opportunity_id,
                    DocumentOriginRecord.origin_url == origin_url,
                    DocumentOriginRecord.snapshot_sha256 == origin_snapshot_sha256,
                    DocumentOriginRecord.organization_id == organization_id,
                    SourceDocumentRecord.organization_id == organization_id,
                )
            ).first()
            if record is None:
                record = session.scalars(
                    select(SourceDocumentRecord).where(
                        SourceDocumentRecord.origin_opportunity_id == origin_opportunity_id,
                        SourceDocumentRecord.origin_url == origin_url,
                        SourceDocumentRecord.origin_snapshot_sha256 == origin_snapshot_sha256,
                        SourceDocumentRecord.organization_id == organization_id,
                    )
                ).first()
            return self._document_from_record(record) if record else None

    def save_document_origin(
        self,
        document_id: UUID,
        origin_opportunity_id: UUID,
        origin_url: str,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> None:
        if self.get_document(document_id, organization_id) is None:
            raise ValueError("document is not visible to the organization")
        with transaction(self.session_factory) as session:
            session.merge(
                DocumentOriginRecord(
                    organization_id=organization_id,
                    opportunity_id=origin_opportunity_id,
                    origin_url=origin_url,
                    snapshot_sha256=origin_snapshot_sha256,
                    document_id=document_id,
                )
            )

    def list_documents(self, organization_id: UUID) -> list[SourceDocument]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(SourceDocumentRecord).where(
                    SourceDocumentRecord.organization_id == organization_id
                )
            ).all()
            return [self._document_from_record(record) for record in records]

    def list_documents_by_origin(
        self,
        origin_opportunity_id: UUID,
        origin_snapshot_sha256: str,
        organization_id: UUID,
    ) -> list[SourceDocument]:
        with transaction(self.session_factory) as session:
            records = (
                session.scalars(
                    select(SourceDocumentRecord)
                    .outerjoin(
                        DocumentOriginRecord,
                        DocumentOriginRecord.document_id == SourceDocumentRecord.id,
                    )
                    .where(
                        SourceDocumentRecord.organization_id == organization_id,
                        or_(
                            (
                                (DocumentOriginRecord.organization_id == organization_id)
                                & (DocumentOriginRecord.opportunity_id == origin_opportunity_id)
                                & (DocumentOriginRecord.snapshot_sha256 == origin_snapshot_sha256)
                            ),
                            (
                                (
                                    SourceDocumentRecord.origin_opportunity_id
                                    == origin_opportunity_id
                                )
                                & (
                                    SourceDocumentRecord.origin_snapshot_sha256
                                    == origin_snapshot_sha256
                                )
                            ),
                        ),
                    )
                    .order_by(SourceDocumentRecord.filename, SourceDocumentRecord.id)
                )
                .unique()
                .all()
            )
            return [self._document_from_record(record) for record in records]

    def save_document_pages(self, pages: list[DocumentPage]) -> list[DocumentPage]:
        if not pages:
            return pages
        with transaction(self.session_factory) as session:
            document_id = pages[0].document_id
            session.execute(
                delete(DocumentPageRecord).where(DocumentPageRecord.document_id == document_id)
            )
            session.add_all([DocumentPageRecord(**page.model_dump()) for page in pages])
        return pages

    def list_document_pages(
        self, document_id: UUID, organization_id: UUID | None = None
    ) -> list[DocumentPage]:
        with transaction(self.session_factory) as session:
            statement = (
                select(DocumentPageRecord)
                .join(SourceDocumentRecord)
                .where(DocumentPageRecord.document_id == document_id)
                .order_by(DocumentPageRecord.page_number)
            )
            if organization_id is not None:
                statement = statement.where(SourceDocumentRecord.organization_id == organization_id)
            records = session.scalars(statement).all()
            return [
                DocumentPage(
                    id=record.id,
                    document_id=record.document_id,
                    page_number=record.page_number,
                    text=record.text,
                    needs_ocr=record.needs_ocr,
                )
                for record in records
            ]

    def save_processing_job(self, job: ProcessingJob) -> ProcessingJob:
        with transaction(self.session_factory) as session:
            payload = job.model_dump()
            payload["status"] = job.status.value
            payload["stage"] = job.stage.value
            session.merge(ProcessingJobRecord(**payload))
        return job

    def get_processing_job(
        self, job_id: UUID, organization_id: UUID | None = None
    ) -> ProcessingJob | None:
        with transaction(self.session_factory) as session:
            statement = (
                select(ProcessingJobRecord)
                .join(SourceDocumentRecord)
                .where(ProcessingJobRecord.id == job_id)
            )
            if organization_id is not None:
                statement = statement.where(SourceDocumentRecord.organization_id == organization_id)
            record = session.scalars(statement).first()
            return self._processing_job_from_record(record) if record else None

    def list_processing_jobs(
        self,
        organization_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> list[ProcessingJob]:
        with transaction(self.session_factory) as session:
            statement = select(ProcessingJobRecord).join(SourceDocumentRecord)
            if organization_id is not None:
                statement = statement.where(SourceDocumentRecord.organization_id == organization_id)
            if document_id is not None:
                statement = statement.where(ProcessingJobRecord.document_id == document_id)
            records = session.scalars(statement.order_by(ProcessingJobRecord.created_at)).all()
            return [self._processing_job_from_record(record) for record in records]

    def save_opportunity(self, opportunity: Opportunity) -> Opportunity:
        with transaction(self.session_factory) as session:
            existing = session.get(OpportunityRecord, opportunity.id)
            payload = opportunity.model_dump(exclude={"requirements"})
            requirements = [self._requirement_to_record(item) for item in opportunity.requirements]
            if existing is None:
                session.add(OpportunityRecord(**payload, requirements=requirements))
            else:
                for name, value in payload.items():
                    setattr(existing, name, value)
                existing.requirements = requirements
        return opportunity

    def get_opportunity(
        self, opportunity_id: UUID, organization_id: UUID | None = None
    ) -> Opportunity | None:
        with transaction(self.session_factory) as session:
            statement = (
                select(OpportunityRecord)
                .outerjoin(
                    SourceDocumentRecord,
                    OpportunityRecord.document_id == SourceDocumentRecord.id,
                )
                .where(OpportunityRecord.id == opportunity_id)
            )
            if organization_id is not None:
                statement = statement.where(
                    or_(
                        OpportunityRecord.document_id.is_(None),
                        SourceDocumentRecord.organization_id == organization_id,
                    )
                )
            record = session.scalars(statement).unique().first()
            return self._opportunity_from_record(record) if record else None

    def get_opportunity_by_source(self, source: str, source_id: str) -> Opportunity | None:
        with transaction(self.session_factory) as session:
            record = (
                session.scalars(
                    select(OpportunityRecord).where(
                        OpportunityRecord.source == source,
                        OpportunityRecord.source_id == source_id,
                    )
                )
                .unique()
                .first()
            )
            return self._opportunity_from_record(record) if record else None

    def list_opportunities(self, organization_id: UUID | None = None) -> list[Opportunity]:
        with transaction(self.session_factory) as session:
            statement = select(OpportunityRecord).outerjoin(
                SourceDocumentRecord,
                OpportunityRecord.document_id == SourceDocumentRecord.id,
            )
            if organization_id is not None:
                statement = statement.where(
                    or_(
                        OpportunityRecord.document_id.is_(None),
                        SourceDocumentRecord.organization_id == organization_id,
                    )
                )
            records = session.scalars(statement).unique().all()
            return [self._opportunity_from_record(record) for record in records]

    def save_pipeline_item(self, item: PipelineItem) -> PipelineItem:
        if self.get_opportunity(item.opportunity_id, item.organization_id) is None:
            raise ValueError("pipeline opportunity is not visible to the organization")
        try:
            with transaction(self.session_factory) as session:
                duplicate = session.scalars(
                    select(PipelineItemRecord).where(
                        PipelineItemRecord.organization_id == item.organization_id,
                        PipelineItemRecord.opportunity_id == item.opportunity_id,
                        PipelineItemRecord.id != item.id,
                    )
                ).first()
                if duplicate is not None:
                    raise ValueError("opportunity is already in the pipeline")
                payload = item.model_dump()
                payload["status"] = item.status.value
                session.merge(PipelineItemRecord(**payload))
        except IntegrityError as exc:
            raise ValueError("opportunity is already in the pipeline") from exc
        return item

    def get_pipeline_item(self, item_id: UUID, organization_id: UUID) -> PipelineItem | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(PipelineItemRecord).where(
                    PipelineItemRecord.id == item_id,
                    PipelineItemRecord.organization_id == organization_id,
                )
            ).first()
            return self._pipeline_item_from_record(record) if record else None

    def get_pipeline_item_by_opportunity(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> PipelineItem | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(PipelineItemRecord).where(
                    PipelineItemRecord.opportunity_id == opportunity_id,
                    PipelineItemRecord.organization_id == organization_id,
                )
            ).first()
            return self._pipeline_item_from_record(record) if record else None

    def list_pipeline_items(self, organization_id: UUID) -> list[PipelineItem]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(PipelineItemRecord)
                .where(PipelineItemRecord.organization_id == organization_id)
                .order_by(
                    PipelineItemRecord.updated_at.desc(),
                    PipelineItemRecord.id.desc(),
                )
            ).all()
            return [self._pipeline_item_from_record(record) for record in records]

    def save_compliance_item(self, item: ComplianceItem) -> ComplianceItem:
        opportunity = self.get_opportunity(item.opportunity_id, item.organization_id)
        if opportunity is None:
            raise ValueError("compliance opportunity is not visible to the organization")
        requirement = self._compliance_requirement(item)
        if requirement is None:
            raise ValueError("compliance requirement does not belong to the opportunity")
        if item.source_evidence != requirement.evidence:
            raise ValueError("source evidence cannot differ from the extracted requirement")
        payload = item.model_dump(exclude={"source_evidence"})
        payload.update(
            {
                "priority": item.priority.value,
                "status": item.status.value,
                "business_evidence": [entry.model_dump() for entry in item.business_evidence],
                "evidence_document_id": item.source_evidence.document_id,
                "evidence_page": item.source_evidence.page,
                "evidence_section": item.source_evidence.section,
                "evidence_supporting_text": item.source_evidence.supporting_text,
            }
        )
        try:
            with transaction(self.session_factory) as session:
                duplicate = session.scalars(
                    select(ComplianceItemRecord).where(
                        ComplianceItemRecord.organization_id == item.organization_id,
                        ComplianceItemRecord.requirement_id == item.requirement_id,
                        ComplianceItemRecord.id != item.id,
                    )
                ).first()
                if duplicate is not None:
                    raise ValueError("requirement is already in the compliance matrix")
                session.merge(ComplianceItemRecord(**payload))
        except IntegrityError as exc:
            raise ValueError("requirement is already in the compliance matrix") from exc
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
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(ComplianceItemRecord).where(
                    ComplianceItemRecord.id == item_id,
                    ComplianceItemRecord.organization_id == organization_id,
                )
            ).first()
            return self._compliance_item_from_record(record) if record else None

    def get_compliance_item_by_requirement(
        self, requirement_id: UUID, organization_id: UUID
    ) -> ComplianceItem | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(ComplianceItemRecord).where(
                    ComplianceItemRecord.requirement_id == requirement_id,
                    ComplianceItemRecord.organization_id == organization_id,
                )
            ).first()
            return self._compliance_item_from_record(record) if record else None

    def list_compliance_items(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[ComplianceItem]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(ComplianceItemRecord)
                .where(
                    ComplianceItemRecord.opportunity_id == opportunity_id,
                    ComplianceItemRecord.organization_id == organization_id,
                )
                .order_by(ComplianceItemRecord.created_at, ComplianceItemRecord.id)
            ).all()
            return [self._compliance_item_from_record(record) for record in records]

    def apply_amendment_acknowledgement(
        self,
        acknowledgement: AmendmentAcknowledgement,
        superseded_requirement_ids: list[UUID],
        new_compliance_items: list[ComplianceItem],
    ) -> AmendmentAcknowledgement:
        existing = self._get_amendment_acknowledgement(
            acknowledgement.opportunity_id,
            acknowledgement.organization_id,
            acknowledgement.previous_snapshot_id,
            acknowledgement.current_snapshot_id,
        )
        if existing is not None:
            if existing.selections != acknowledgement.selections:
                raise ValueError("amendment version pair was acknowledged differently")
            return existing
        if (
            self.get_opportunity(acknowledgement.opportunity_id, acknowledgement.organization_id)
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
            requirement = self._compliance_requirement(item)
            if (
                item.organization_id != acknowledgement.organization_id
                or item.opportunity_id != acknowledgement.opportunity_id
                or requirement is None
                or item.source_evidence != requirement.evidence
            ):
                raise ValueError("compliance update has invalid requirement evidence")

        try:
            with transaction(self.session_factory) as session:
                concurrent = session.scalars(
                    select(AmendmentAcknowledgementRecord)
                    .where(
                        AmendmentAcknowledgementRecord.organization_id
                        == acknowledgement.organization_id,
                        AmendmentAcknowledgementRecord.opportunity_id
                        == acknowledgement.opportunity_id,
                        AmendmentAcknowledgementRecord.previous_snapshot_id
                        == acknowledgement.previous_snapshot_id,
                        AmendmentAcknowledgementRecord.current_snapshot_id
                        == acknowledgement.current_snapshot_id,
                    )
                    .with_for_update()
                ).first()
                if concurrent is not None:
                    found = self._amendment_acknowledgement_from_record(concurrent)
                    if found.selections != acknowledgement.selections:
                        raise ValueError("amendment version pair was acknowledged differently")
                    return found
                if superseded_requirement_ids:
                    superseded = session.scalars(
                        select(ComplianceItemRecord)
                        .where(
                            ComplianceItemRecord.organization_id == acknowledgement.organization_id,
                            ComplianceItemRecord.opportunity_id == acknowledgement.opportunity_id,
                            ComplianceItemRecord.requirement_id.in_(superseded_requirement_ids),
                        )
                        .with_for_update()
                    ).all()
                    now = datetime.now(UTC)
                    for record in superseded:
                        record.status = ComplianceStatus.NOT_APPLICABLE.value
                        record.updated_at = now
                for item in new_compliance_items:
                    present = session.scalars(
                        select(ComplianceItemRecord)
                        .where(
                            ComplianceItemRecord.organization_id == acknowledgement.organization_id,
                            ComplianceItemRecord.requirement_id == item.requirement_id,
                        )
                        .with_for_update()
                    ).first()
                    if present is not None:
                        continue
                    payload = item.model_dump(exclude={"source_evidence"})
                    payload.update(
                        {
                            "priority": item.priority.value,
                            "status": item.status.value,
                            "business_evidence": [
                                entry.model_dump() for entry in item.business_evidence
                            ],
                            "evidence_document_id": item.source_evidence.document_id,
                            "evidence_page": item.source_evidence.page,
                            "evidence_section": item.source_evidence.section,
                            "evidence_supporting_text": (item.source_evidence.supporting_text),
                        }
                    )
                    session.add(ComplianceItemRecord(**payload))
                session.add(
                    AmendmentAcknowledgementRecord(
                        **acknowledgement.model_dump(exclude={"selections"}),
                        selections=[
                            item.model_dump(mode="json") for item in acknowledgement.selections
                        ],
                    )
                )
        except IntegrityError as exc:
            winner = self._get_amendment_acknowledgement(
                acknowledgement.opportunity_id,
                acknowledgement.organization_id,
                acknowledgement.previous_snapshot_id,
                acknowledgement.current_snapshot_id,
            )
            if winner is not None and winner.selections == acknowledgement.selections:
                return winner
            raise ValueError("amendment acknowledgement conflicts with stored data") from exc
        return acknowledgement

    def _get_amendment_acknowledgement(
        self,
        opportunity_id: UUID,
        organization_id: UUID,
        previous_snapshot_id: UUID,
        current_snapshot_id: UUID,
    ) -> AmendmentAcknowledgement | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(AmendmentAcknowledgementRecord).where(
                    AmendmentAcknowledgementRecord.opportunity_id == opportunity_id,
                    AmendmentAcknowledgementRecord.organization_id == organization_id,
                    AmendmentAcknowledgementRecord.previous_snapshot_id == previous_snapshot_id,
                    AmendmentAcknowledgementRecord.current_snapshot_id == current_snapshot_id,
                )
            ).first()
            return (
                self._amendment_acknowledgement_from_record(record) if record is not None else None
            )

    def list_amendment_acknowledgements(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> list[AmendmentAcknowledgement]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(AmendmentAcknowledgementRecord)
                .where(
                    AmendmentAcknowledgementRecord.opportunity_id == opportunity_id,
                    AmendmentAcknowledgementRecord.organization_id == organization_id,
                )
                .order_by(
                    AmendmentAcknowledgementRecord.acknowledged_at.desc(),
                    AmendmentAcknowledgementRecord.id.desc(),
                )
            ).all()
            return [self._amendment_acknowledgement_from_record(record) for record in records]

    def save_opportunity_watch(self, watch: OpportunityWatch) -> OpportunityWatch:
        if self.get_opportunity(watch.opportunity_id, watch.organization_id) is None:
            raise ValueError("watch opportunity is not visible to the organization")
        try:
            with transaction(self.session_factory) as session:
                session.merge(OpportunityWatchRecord(**watch.model_dump()))
        except IntegrityError as exc:
            raise ValueError("opportunity is already watched") from exc
        return watch

    def get_opportunity_watch(
        self, opportunity_id: UUID, organization_id: UUID
    ) -> OpportunityWatch | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(OpportunityWatchRecord).where(
                    OpportunityWatchRecord.opportunity_id == opportunity_id,
                    OpportunityWatchRecord.organization_id == organization_id,
                )
            ).first()
            return self._opportunity_watch_from_record(record) if record else None

    def list_opportunity_watches(self, organization_id: UUID) -> list[OpportunityWatch]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(OpportunityWatchRecord)
                .where(OpportunityWatchRecord.organization_id == organization_id)
                .order_by(
                    OpportunityWatchRecord.created_at.desc(), OpportunityWatchRecord.id.desc()
                )
            ).all()
            return [self._opportunity_watch_from_record(record) for record in records]

    def delete_opportunity_watch(self, opportunity_id: UUID, organization_id: UUID) -> bool:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(OpportunityWatchRecord).where(
                    OpportunityWatchRecord.opportunity_id == opportunity_id,
                    OpportunityWatchRecord.organization_id == organization_id,
                )
            ).first()
            if record is None:
                return False
            session.execute(
                delete(OpportunityAlertRecord).where(OpportunityAlertRecord.watch_id == record.id)
            )
            session.delete(record)
            return True

    def save_opportunity_alert(self, alert: OpportunityAlert) -> OpportunityAlert:
        try:
            with transaction(self.session_factory) as session:
                payload = alert.model_dump()
                payload["alert_type"] = alert.alert_type.value
                payload["status"] = alert.status.value
                session.merge(OpportunityAlertRecord(**payload))
        except IntegrityError:
            existing = self.get_opportunity_alert_by_dedupe_key(
                alert.dedupe_key, alert.organization_id
            )
            if existing is not None:
                return existing
            raise
        return alert

    def get_opportunity_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> OpportunityAlert | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(OpportunityAlertRecord).where(
                    OpportunityAlertRecord.id == alert_id,
                    OpportunityAlertRecord.organization_id == organization_id,
                )
            ).first()
            return self._opportunity_alert_from_record(record) if record else None

    def get_opportunity_alert_by_dedupe_key(
        self, dedupe_key: str, organization_id: UUID
    ) -> OpportunityAlert | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(OpportunityAlertRecord).where(
                    OpportunityAlertRecord.dedupe_key == dedupe_key,
                    OpportunityAlertRecord.organization_id == organization_id,
                )
            ).first()
            return self._opportunity_alert_from_record(record) if record else None

    def list_opportunity_alerts(self, organization_id: UUID) -> list[OpportunityAlert]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(OpportunityAlertRecord)
                .where(OpportunityAlertRecord.organization_id == organization_id)
                .order_by(
                    OpportunityAlertRecord.created_at.desc(), OpportunityAlertRecord.id.desc()
                )
            ).all()
            return [self._opportunity_alert_from_record(record) for record in records]

    def save_notification_preference(self, item: NotificationPreference) -> NotificationPreference:
        with transaction(self.session_factory) as session:
            payload = item.model_dump()
            payload["alert_types"] = [value.value for value in item.alert_types]
            session.merge(NotificationPreferenceRecord(**payload))
        return item

    def get_notification_preference(self, organization_id: UUID) -> NotificationPreference | None:
        with transaction(self.session_factory) as session:
            record = session.get(NotificationPreferenceRecord, organization_id)
            return self._notification_preference_from_record(record) if record else None

    def list_notification_preferences(
        self, enabled_only: bool = False
    ) -> list[NotificationPreference]:
        with transaction(self.session_factory) as session:
            statement = select(NotificationPreferenceRecord)
            if enabled_only:
                statement = statement.where(NotificationPreferenceRecord.enabled.is_(True))
            records = session.scalars(
                statement.order_by(NotificationPreferenceRecord.updated_at)
            ).all()
            return [self._notification_preference_from_record(record) for record in records]

    def save_notification_delivery(self, item: NotificationDelivery) -> NotificationDelivery:
        try:
            with transaction(self.session_factory) as session:
                payload = item.model_dump()
                payload["status"] = item.status.value
                session.merge(NotificationDeliveryRecord(**payload))
        except IntegrityError:
            existing = self.get_notification_delivery_by_alert(item.alert_id, item.organization_id)
            if existing is not None:
                return existing
            raise
        return item

    def get_notification_delivery_by_alert(
        self, alert_id: UUID, organization_id: UUID
    ) -> NotificationDelivery | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(NotificationDeliveryRecord).where(
                    NotificationDeliveryRecord.alert_id == alert_id,
                    NotificationDeliveryRecord.organization_id == organization_id,
                )
            ).first()
            return self._notification_delivery_from_record(record) if record else None

    def list_notification_deliveries(
        self, organization_id: UUID | None = None
    ) -> list[NotificationDelivery]:
        with transaction(self.session_factory) as session:
            statement = select(NotificationDeliveryRecord)
            if organization_id is not None:
                statement = statement.where(
                    NotificationDeliveryRecord.organization_id == organization_id
                )
            records = session.scalars(
                statement.order_by(
                    NotificationDeliveryRecord.created_at.desc(),
                    NotificationDeliveryRecord.id.desc(),
                )
            ).all()
            return [self._notification_delivery_from_record(record) for record in records]

    def claim_notification_deliveries(
        self, max_attempts: int, limit: int = 100
    ) -> list[NotificationDelivery]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(NotificationDeliveryRecord)
                .where(
                    NotificationDeliveryRecord.status.in_(
                        [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
                    ),
                    NotificationDeliveryRecord.attempts < max_attempts,
                )
                .order_by(NotificationDeliveryRecord.created_at, NotificationDeliveryRecord.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            now = datetime.now(UTC)
            for record in records:
                record.status = DeliveryStatus.PROCESSING.value
                record.updated_at = now
            session.flush()
            return [self._notification_delivery_from_record(record) for record in records]

    def save_sam_ingestion_run(self, run: SamIngestionRun) -> SamIngestionRun:
        with transaction(self.session_factory) as session:
            payload = run.model_dump()
            payload["status"] = run.status.value
            session.merge(SamIngestionRunRecord(**payload))
        return run

    def list_sam_ingestion_runs(self) -> list[SamIngestionRun]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(SamIngestionRunRecord).order_by(
                    SamIngestionRunRecord.started_at,
                    SamIngestionRunRecord.id,
                )
            ).all()
            return [self._sam_ingestion_run_from_record(record) for record in records]

    def save_sam_snapshot(self, snapshot: SamOpportunitySnapshot) -> SamOpportunitySnapshot:
        with transaction(self.session_factory) as session:
            if session.get(OpportunityRecord, snapshot.opportunity_id) is None:
                raise ValueError("SAM snapshot opportunity does not exist")
            session.add(SamOpportunitySnapshotRecord(**snapshot.model_dump()))
        return snapshot

    def get_latest_sam_snapshot(self, opportunity_id: UUID) -> SamOpportunitySnapshot | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(SamOpportunitySnapshotRecord)
                .where(SamOpportunitySnapshotRecord.opportunity_id == opportunity_id)
                .order_by(
                    SamOpportunitySnapshotRecord.observed_at.desc(),
                    SamOpportunitySnapshotRecord.id.desc(),
                )
            ).first()
            return self._sam_snapshot_from_record(record) if record else None

    def list_sam_snapshots(self, opportunity_id: UUID) -> list[SamOpportunitySnapshot]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(SamOpportunitySnapshotRecord)
                .where(SamOpportunitySnapshotRecord.opportunity_id == opportunity_id)
                .order_by(
                    SamOpportunitySnapshotRecord.observed_at,
                    SamOpportunitySnapshotRecord.id,
                )
            ).all()
            return [self._sam_snapshot_from_record(record) for record in records]

    def get_embedding(
        self,
        target: EmbeddingTarget,
        target_id: UUID,
        model: str,
        content_sha256: str,
    ) -> SemanticEmbedding | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(SemanticEmbeddingRecord).where(
                    SemanticEmbeddingRecord.target == target.value,
                    SemanticEmbeddingRecord.target_id == target_id,
                    SemanticEmbeddingRecord.model == model,
                    SemanticEmbeddingRecord.content_sha256 == content_sha256,
                )
            ).first()
            return self._embedding_from_record(record) if record else None

    def save_embedding(self, embedding: SemanticEmbedding) -> SemanticEmbedding:
        with transaction(self.session_factory) as session:
            existing = session.scalars(
                select(SemanticEmbeddingRecord).where(
                    SemanticEmbeddingRecord.target == embedding.target.value,
                    SemanticEmbeddingRecord.target_id == embedding.target_id,
                    SemanticEmbeddingRecord.model == embedding.model,
                )
            ).first()
            payload = embedding.model_dump(exclude={"vector"})
            payload["target"] = embedding.target.value
            payload["embedding"] = embedding.vector
            if existing is None:
                session.add(SemanticEmbeddingRecord(**payload))
            else:
                for name, value in payload.items():
                    setattr(existing, name, value)
        return embedding

    def search_embeddings(
        self,
        target: EmbeddingTarget,
        model: str,
        query_vector: list[float],
        limit: int,
        organization_id: UUID | None = None,
    ) -> list[EmbeddingHit]:
        distance = SemanticEmbeddingRecord.embedding.cosine_distance(query_vector)
        with transaction(self.session_factory) as session:
            statement = select(SemanticEmbeddingRecord, distance.label("distance")).where(
                SemanticEmbeddingRecord.target == target.value,
                SemanticEmbeddingRecord.model == model,
            )
            if organization_id is None:
                statement = statement.where(SemanticEmbeddingRecord.organization_id.is_(None))
            else:
                statement = statement.where(
                    SemanticEmbeddingRecord.organization_id == organization_id
                )
            rows = session.execute(statement.order_by(distance).limit(limit)).all()
            hits: list[EmbeddingHit] = []
            for row in rows:
                record = cast(SemanticEmbeddingRecord, row[0])
                cosine_distance = cast(float, row[1])
                hits.append(
                    EmbeddingHit(
                        target_id=record.target_id,
                        score=max(0.0, min(1.0, 1.0 - cosine_distance)),
                    )
                )
            return hits

    def save_review_item(self, item: ReviewItem) -> ReviewItem:
        with transaction(self.session_factory) as session:
            if item.opportunity_id is not None:
                visible_opportunity = session.scalars(
                    select(OpportunityRecord)
                    .outerjoin(
                        SourceDocumentRecord,
                        OpportunityRecord.document_id == SourceDocumentRecord.id,
                    )
                    .where(
                        OpportunityRecord.id == item.opportunity_id,
                        or_(
                            OpportunityRecord.document_id.is_(None),
                            SourceDocumentRecord.organization_id == item.organization_id,
                        ),
                    )
                ).first()
                if visible_opportunity is None:
                    raise ValueError("review opportunity is not visible to the organization")

            evidence_document_ids = {evidence.document_id for evidence in item.evidence}
            owned_document_ids = set(
                session.scalars(
                    select(SourceDocumentRecord.id).where(
                        SourceDocumentRecord.id.in_(evidence_document_ids),
                        SourceDocumentRecord.organization_id == item.organization_id,
                    )
                ).all()
            )
            if owned_document_ids != evidence_document_ids:
                raise ValueError("review evidence document is not owned by the organization")

            existing = session.get(ReviewItemRecord, item.id)
            if existing:
                session.delete(existing)
                session.flush()
            payload = item.model_dump(exclude={"evidence", "priority", "priority_score"})
            payload["reason"] = item.reason.value
            payload["status"] = item.status.value
            session.add(
                ReviewItemRecord(
                    **payload,
                    evidence=[
                        ReviewEvidenceRecord(position=index, **evidence.model_dump())
                        for index, evidence in enumerate(item.evidence)
                    ],
                )
            )
        return item

    def resolve_conflicting_review(
        self,
        review_id: UUID,
        organization_id: UUID,
        reviewer_id: UUID,
        corrected_value: str,
        note: str | None = None,
    ) -> ReviewItem:
        with transaction(self.session_factory) as session:
            review_record = (
                session.scalars(
                    select(ReviewItemRecord)
                    .where(
                        ReviewItemRecord.id == review_id,
                        ReviewItemRecord.organization_id == organization_id,
                    )
                    .with_for_update()
                )
                .unique()
                .first()
            )
            if review_record is None or review_record.opportunity_id is None:
                raise LookupError("review not found")
            opportunity_record = (
                session.scalars(
                    select(OpportunityRecord)
                    .join(
                        SourceDocumentRecord,
                        OpportunityRecord.document_id == SourceDocumentRecord.id,
                    )
                    .where(
                        OpportunityRecord.id == review_record.opportunity_id,
                        SourceDocumentRecord.organization_id == organization_id,
                    )
                    .with_for_update()
                )
                .unique()
                .first()
            )
            if opportunity_record is None:
                raise LookupError("opportunity not found")
            item = self._review_from_record(review_record)
            opportunity = self._opportunity_from_record(opportunity_record)
            resolved, updated_opportunity = resolve_conflicting_value(
                item,
                opportunity,
                reviewer_id=reviewer_id,
                corrected_value=corrected_value,
                note=note,
            )
            field_name = item.field_name.removeprefix("opportunity:")
            setattr(opportunity_record, field_name, getattr(updated_opportunity, field_name))
            review_record.status = resolved.status.value
            review_record.corrected_value = resolved.corrected_value
            review_record.reviewer_id = resolved.reviewer_id
            review_record.resolution_note = resolved.resolution_note
            review_record.updated_at = resolved.updated_at
            review_record.resolved_at = resolved.resolved_at
        return resolved

    def get_review_item(self, review_id: UUID, organization_id: UUID) -> ReviewItem | None:
        with transaction(self.session_factory) as session:
            record = (
                session.scalars(
                    select(ReviewItemRecord).where(
                        ReviewItemRecord.id == review_id,
                        ReviewItemRecord.organization_id == organization_id,
                    )
                )
                .unique()
                .first()
            )
            return self._review_from_record(record) if record else None

    def list_review_items(
        self,
        organization_id: UUID,
        status: ReviewStatus | None = None,
        opportunity_id: UUID | None = None,
    ) -> list[ReviewItem]:
        with transaction(self.session_factory) as session:
            statement = select(ReviewItemRecord).where(
                ReviewItemRecord.organization_id == organization_id
            )
            if status is not None:
                statement = statement.where(ReviewItemRecord.status == status.value)
            if opportunity_id is not None:
                statement = statement.where(ReviewItemRecord.opportunity_id == opportunity_id)
            records = session.scalars(statement).unique().all()
            return sorted(
                [self._review_from_record(record) for record in records],
                key=review_sort_key,
            )

    def register_identity(self, identity: AuthIdentity) -> AuthIdentity:
        with transaction(self.session_factory) as session:
            existing = session.scalars(
                select(UserAccountRecord).where(UserAccountRecord.email == identity.user.email)
            ).first()
            if existing is not None:
                raise ValueError("email is already registered")
            session.add(OrganizationRecord(**identity.organization.model_dump()))
            session.add(UserAccountRecord(**identity.user.model_dump()))
            session.flush()
            membership = identity.membership.model_dump()
            membership["role"] = identity.membership.role.value
            session.add(OrganizationMembershipRecord(**membership))
        return identity

    def get_identity_by_email(self, email: str) -> AuthIdentity | None:
        return self._get_identity(UserAccountRecord.email == email.strip().lower())

    def get_identity_by_user_id(self, user_id: UUID) -> AuthIdentity | None:
        return self._get_identity(UserAccountRecord.id == user_id)

    def _get_identity(self, criterion: ColumnElement[bool]) -> AuthIdentity | None:
        with transaction(self.session_factory) as session:
            row = session.execute(
                select(
                    UserAccountRecord,
                    OrganizationMembershipRecord,
                    OrganizationRecord,
                )
                .join(
                    OrganizationMembershipRecord,
                    OrganizationMembershipRecord.user_id == UserAccountRecord.id,
                )
                .join(
                    OrganizationRecord,
                    OrganizationRecord.id == OrganizationMembershipRecord.organization_id,
                )
                .where(criterion)
            ).first()
            if row is None:
                return None
            user, membership, organization = row
            return AuthIdentity(
                user=UserAccount(
                    id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    created_at=_ensure_aware(user.created_at),
                ),
                organization=Organization(
                    id=organization.id,
                    name=organization.name,
                    created_at=_ensure_aware(organization.created_at),
                ),
                membership=OrganizationMembership(
                    organization_id=membership.organization_id,
                    user_id=membership.user_id,
                    role=OrganizationRole(membership.role),
                    created_at=_ensure_aware(membership.created_at),
                ),
            )

    @staticmethod
    def _profile_from_record(record: CompanyProfileRecord) -> CompanyProfile:
        return CompanyProfile(
            id=record.id,
            organization_id=record.organization_id,
            name=record.name,
            service_categories=record.service_categories,
            states=record.states,
            maximum_distance_miles=record.maximum_distance_miles,
            minimum_contract_value=record.minimum_contract_value,
            maximum_contract_value=record.maximum_contract_value,
            licenses=record.licenses,
            certifications=record.certifications,
            set_asides=record.set_asides,
            naics_codes=record.naics_codes,
            insurance_coverages=record.insurance_coverages,
            contract_preferences=record.contract_preferences,
            past_performance=[
                PastPerformanceProject.model_validate(item) for item in record.past_performance
            ],
            capability_statement=record.capability_statement,
        )

    @staticmethod
    def _document_from_record(record: SourceDocumentRecord) -> SourceDocument:
        return SourceDocument(
            id=record.id,
            organization_id=record.organization_id,
            filename=record.filename,
            content=record.content,
            imported_at=record.imported_at,
            sha256=record.sha256,
            storage_key=record.storage_key,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            status=DocumentStatus(record.status),
            page_count=record.page_count,
            error_message=record.error_message,
            origin_opportunity_id=record.origin_opportunity_id,
            origin_url=record.origin_url,
            origin_snapshot_sha256=record.origin_snapshot_sha256,
        )

    @staticmethod
    def _processing_job_from_record(record: ProcessingJobRecord) -> ProcessingJob:
        created_at = record.created_at
        updated_at = record.updated_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return ProcessingJob(
            id=record.id,
            document_id=record.document_id,
            status=ProcessingJobStatus(record.status),
            stage=ProcessingStage(record.stage),
            attempts=record.attempts,
            max_attempts=record.max_attempts,
            error_message=record.error_message,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _requirement_to_record(requirement: Requirement) -> RequirementRecord:
        return RequirementRecord(
            id=requirement.id,
            category=requirement.category,
            description=requirement.description,
            mandatory=requirement.mandatory,
            confidence=requirement.confidence,
            evidence_document_id=requirement.evidence.document_id,
            evidence_page=requirement.evidence.page,
            evidence_section=requirement.evidence.section,
            evidence_supporting_text=requirement.evidence.supporting_text,
        )

    @staticmethod
    def _opportunity_from_record(record: OpportunityRecord) -> Opportunity:
        requirements = [
            Requirement(
                id=item.id,
                category=item.category,
                description=item.description,
                mandatory=item.mandatory,
                confidence=float(item.confidence),
                evidence=Evidence(
                    document_id=item.evidence_document_id,
                    page=item.evidence_page,
                    section=item.evidence_section,
                    supporting_text=item.evidence_supporting_text,
                ),
            )
            for item in record.requirements
        ]
        return Opportunity(
            id=record.id,
            source=record.source,
            source_id=record.source_id,
            title=record.title,
            agency=record.agency,
            response_deadline=record.response_deadline,
            place_of_performance=record.place_of_performance,
            set_aside=record.set_aside,
            estimated_value=record.estimated_value,
            scope=record.scope,
            source_url=record.source_url,
            document_id=record.document_id,
            requirements=requirements,
        )

    @staticmethod
    def _pipeline_item_from_record(record: PipelineItemRecord) -> PipelineItem:
        return PipelineItem(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            status=PipelineStatus(record.status),
            owner_user_id=record.owner_user_id,
            next_action=record.next_action,
            notes=record.notes,
            created_at=_ensure_aware(record.created_at),
            updated_at=_ensure_aware(record.updated_at),
        )

    @staticmethod
    def _compliance_item_from_record(record: ComplianceItemRecord) -> ComplianceItem:
        return ComplianceItem(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            requirement_id=record.requirement_id,
            description=record.description,
            category=record.category,
            priority=RequirementPriority(record.priority),
            status=ComplianceStatus(record.status),
            source_evidence=Evidence(
                document_id=record.evidence_document_id,
                page=record.evidence_page,
                section=record.evidence_section,
                supporting_text=record.evidence_supporting_text,
            ),
            business_evidence=[
                BusinessEvidence.model_validate(item) for item in record.business_evidence
            ],
            owner_user_id=record.owner_user_id,
            due_date=record.due_date,
            notes=record.notes,
            created_at=_ensure_aware(record.created_at),
            updated_at=_ensure_aware(record.updated_at),
        )

    @staticmethod
    def _amendment_acknowledgement_from_record(
        record: AmendmentAcknowledgementRecord,
    ) -> AmendmentAcknowledgement:
        return AmendmentAcknowledgement(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            previous_snapshot_id=record.previous_snapshot_id,
            current_snapshot_id=record.current_snapshot_id,
            selections=[AmendmentSelection.model_validate(item) for item in record.selections],
            acknowledged_by_user_id=record.acknowledged_by_user_id,
            acknowledged_at=_ensure_aware(record.acknowledged_at),
        )

    @staticmethod
    def _opportunity_watch_from_record(record: OpportunityWatchRecord) -> OpportunityWatch:
        return OpportunityWatch(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            created_at=_ensure_aware(record.created_at),
        )

    @staticmethod
    def _opportunity_alert_from_record(record: OpportunityAlertRecord) -> OpportunityAlert:
        return OpportunityAlert(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            watch_id=record.watch_id,
            alert_type=AlertType(record.alert_type),
            status=AlertStatus(record.status),
            title=record.title,
            message=record.message,
            changed_fields=record.changed_fields,
            dedupe_key=record.dedupe_key,
            created_at=_ensure_aware(record.created_at),
            updated_at=_ensure_aware(record.updated_at),
        )

    @staticmethod
    def _notification_preference_from_record(
        record: NotificationPreferenceRecord,
    ) -> NotificationPreference:
        return NotificationPreference(
            organization_id=record.organization_id,
            enabled=record.enabled,
            recipient_email=record.recipient_email,
            alert_types=[AlertType(value) for value in record.alert_types],
            created_at=_ensure_aware(record.created_at),
            updated_at=_ensure_aware(record.updated_at),
        )

    @staticmethod
    def _notification_delivery_from_record(
        record: NotificationDeliveryRecord,
    ) -> NotificationDelivery:
        return NotificationDelivery(
            id=record.id,
            organization_id=record.organization_id,
            alert_id=record.alert_id,
            recipient_email=record.recipient_email,
            subject=record.subject,
            body=record.body,
            status=DeliveryStatus(record.status),
            attempts=record.attempts,
            error_message=record.error_message,
            created_at=_ensure_aware(record.created_at),
            updated_at=_ensure_aware(record.updated_at),
            sent_at=_ensure_aware(record.sent_at) if record.sent_at else None,
        )

    @staticmethod
    def _review_from_record(record: ReviewItemRecord) -> ReviewItem:
        def aware(value: datetime | None) -> datetime | None:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        def aware_required(value: datetime) -> datetime:
            return aware(value) or value

        return ReviewItem(
            id=record.id,
            organization_id=record.organization_id,
            opportunity_id=record.opportunity_id,
            field_name=record.field_name,
            extracted_value=record.extracted_value,
            confidence=float(record.confidence),
            mandatory=record.mandatory,
            reason=ReviewReason(record.reason),
            status=ReviewStatus(record.status),
            corrected_value=record.corrected_value,
            reviewer_id=record.reviewer_id,
            resolution_note=record.resolution_note,
            created_at=aware_required(record.created_at),
            updated_at=aware_required(record.updated_at),
            resolved_at=aware(record.resolved_at),
            evidence=[
                Evidence(
                    document_id=item.document_id,
                    page=item.page,
                    section=item.section,
                    supporting_text=item.supporting_text,
                )
                for item in record.evidence
            ],
        )

    @staticmethod
    def _embedding_from_record(record: SemanticEmbeddingRecord) -> SemanticEmbedding:
        return SemanticEmbedding(
            id=record.id,
            target=EmbeddingTarget(record.target),
            target_id=record.target_id,
            organization_id=record.organization_id,
            model=record.model,
            content_sha256=record.content_sha256,
            vector=[float(component) for component in record.embedding],
            created_at=_ensure_aware(record.created_at),
        )

    @staticmethod
    def _sam_ingestion_run_from_record(record: SamIngestionRunRecord) -> SamIngestionRun:
        return SamIngestionRun(
            id=record.id,
            posted_from=record.posted_from,
            posted_to=record.posted_to,
            status=SamIngestionStatus(record.status),
            pages_fetched=record.pages_fetched,
            records_fetched=record.records_fetched,
            created_count=record.created_count,
            updated_count=record.updated_count,
            unchanged_count=record.unchanged_count,
            started_at=_ensure_aware(record.started_at),
            finished_at=(_ensure_aware(record.finished_at) if record.finished_at else None),
            error_message=record.error_message,
        )

    @staticmethod
    def _sam_snapshot_from_record(
        record: SamOpportunitySnapshotRecord,
    ) -> SamOpportunitySnapshot:
        return SamOpportunitySnapshot(
            id=record.id,
            opportunity_id=record.opportunity_id,
            content_sha256=record.content_sha256,
            normalized_payload=record.normalized_payload,
            observed_at=_ensure_aware(record.observed_at),
        )
