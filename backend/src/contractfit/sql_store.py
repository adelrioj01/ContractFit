from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from contractfit.database import transaction
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    DocumentStatus,
    Evidence,
    Opportunity,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStage,
    Requirement,
    SourceDocument,
)
from contractfit.persistence_models import (
    CompanyProfileRecord,
    DocumentPageRecord,
    OpportunityRecord,
    ProcessingJobRecord,
    RequirementRecord,
    ReviewEvidenceRecord,
    ReviewItemRecord,
    SourceDocumentRecord,
)
from contractfit.review import ReviewItem, ReviewReason, ReviewStatus, review_sort_key


class SqlAlchemyStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def reset(self) -> None:
        with transaction(self.session_factory) as session:
            session.execute(delete(ReviewEvidenceRecord))
            session.execute(delete(ReviewItemRecord))
            session.execute(delete(RequirementRecord))
            session.execute(delete(OpportunityRecord))
            session.execute(delete(ProcessingJobRecord))
            session.execute(delete(DocumentPageRecord))
            session.execute(delete(SourceDocumentRecord))
            session.execute(delete(CompanyProfileRecord))

    def get_profile(self) -> CompanyProfile | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(select(CompanyProfileRecord).limit(1)).first()
            return self._profile_from_record(record) if record else None

    def save_profile(self, profile: CompanyProfile) -> CompanyProfile:
        with transaction(self.session_factory) as session:
            session.merge(CompanyProfileRecord(**profile.model_dump()))
        return profile

    def save_document(self, document: SourceDocument) -> SourceDocument:
        with transaction(self.session_factory) as session:
            payload = document.model_dump()
            payload["status"] = document.status.value
            session.merge(SourceDocumentRecord(**payload))
        return document

    def get_document(self, document_id: UUID) -> SourceDocument | None:
        with transaction(self.session_factory) as session:
            record = session.get(SourceDocumentRecord, document_id)
            return self._document_from_record(record) if record else None

    def find_document_by_sha256(self, sha256: str) -> SourceDocument | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(SourceDocumentRecord).where(SourceDocumentRecord.sha256 == sha256)
            ).first()
            return self._document_from_record(record) if record else None

    def list_documents(self) -> list[SourceDocument]:
        with transaction(self.session_factory) as session:
            records = session.scalars(select(SourceDocumentRecord)).all()
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

    def list_document_pages(self, document_id: UUID) -> list[DocumentPage]:
        with transaction(self.session_factory) as session:
            records = session.scalars(
                select(DocumentPageRecord)
                .where(DocumentPageRecord.document_id == document_id)
                .order_by(DocumentPageRecord.page_number)
            ).all()
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

    def get_processing_job(self, job_id: UUID) -> ProcessingJob | None:
        with transaction(self.session_factory) as session:
            record = session.get(ProcessingJobRecord, job_id)
            return self._processing_job_from_record(record) if record else None

    def list_processing_jobs(self, document_id: UUID | None = None) -> list[ProcessingJob]:
        with transaction(self.session_factory) as session:
            statement = select(ProcessingJobRecord)
            if document_id is not None:
                statement = statement.where(ProcessingJobRecord.document_id == document_id)
            records = session.scalars(statement.order_by(ProcessingJobRecord.created_at)).all()
            return [self._processing_job_from_record(record) for record in records]

    def save_opportunity(self, opportunity: Opportunity) -> Opportunity:
        with transaction(self.session_factory) as session:
            existing = session.get(OpportunityRecord, opportunity.id)
            if existing:
                session.delete(existing)
                session.flush()
            record = OpportunityRecord(
                **opportunity.model_dump(exclude={"requirements"}),
                requirements=[
                    self._requirement_to_record(item) for item in opportunity.requirements
                ],
            )
            session.add(record)
        return opportunity

    def list_opportunities(self) -> list[Opportunity]:
        with transaction(self.session_factory) as session:
            records = session.scalars(select(OpportunityRecord)).unique().all()
            return [self._opportunity_from_record(record) for record in records]

    def save_review_item(self, item: ReviewItem) -> ReviewItem:
        with transaction(self.session_factory) as session:
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

    def get_review_item(self, review_id: UUID, organization_id: UUID) -> ReviewItem | None:
        with transaction(self.session_factory) as session:
            record = session.scalars(
                select(ReviewItemRecord).where(
                    ReviewItemRecord.id == review_id,
                    ReviewItemRecord.organization_id == organization_id,
                )
            ).unique().first()
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
            capability_statement=record.capability_statement,
        )

    @staticmethod
    def _document_from_record(record: SourceDocumentRecord) -> SourceDocument:
        return SourceDocument(
            id=record.id,
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
