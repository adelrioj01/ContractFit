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
    Requirement,
    SourceDocument,
)
from contractfit.persistence_models import (
    CompanyProfileRecord,
    DocumentPageRecord,
    OpportunityRecord,
    RequirementRecord,
    SourceDocumentRecord,
)


class SqlAlchemyStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def reset(self) -> None:
        with transaction(self.session_factory) as session:
            session.execute(delete(RequirementRecord))
            session.execute(delete(OpportunityRecord))
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
