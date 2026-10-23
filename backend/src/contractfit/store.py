from typing import Protocol
from uuid import UUID

from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    Opportunity,
    ProcessingJob,
    SourceDocument,
)


class ContractFitStore(Protocol):
    def reset(self) -> None: ...
    def get_profile(self) -> CompanyProfile | None: ...
    def save_profile(self, profile: CompanyProfile) -> CompanyProfile: ...
    def save_document(self, document: SourceDocument) -> SourceDocument: ...
    def get_document(self, document_id: UUID) -> SourceDocument | None: ...
    def find_document_by_sha256(self, sha256: str) -> SourceDocument | None: ...
    def list_documents(self) -> list[SourceDocument]: ...
    def save_document_pages(self, pages: list[DocumentPage]) -> list[DocumentPage]: ...
    def list_document_pages(self, document_id: UUID) -> list[DocumentPage]: ...
    def save_processing_job(self, job: ProcessingJob) -> ProcessingJob: ...
    def get_processing_job(self, job_id: UUID) -> ProcessingJob | None: ...
    def list_processing_jobs(self, document_id: UUID | None = None) -> list[ProcessingJob]: ...
    def save_opportunity(self, opportunity: Opportunity) -> Opportunity: ...
    def list_opportunities(self) -> list[Opportunity]: ...


class InMemoryStore:
    """Replaceable repository for the first vertical slice and local demos."""

    def __init__(self) -> None:
        self.profile: CompanyProfile | None = None
        self.documents: dict[UUID, SourceDocument] = {}
        self.document_pages: dict[UUID, list[DocumentPage]] = {}
        self.processing_jobs: dict[UUID, ProcessingJob] = {}
        self.opportunities: dict[UUID, Opportunity] = {}

    def reset(self) -> None:
        self.profile = None
        self.documents.clear()
        self.document_pages.clear()
        self.processing_jobs.clear()
        self.opportunities.clear()

    def save_profile(self, profile: CompanyProfile) -> CompanyProfile:
        self.profile = profile
        return profile

    def get_profile(self) -> CompanyProfile | None:
        return self.profile

    def save_document(self, document: SourceDocument) -> SourceDocument:
        self.documents[document.id] = document
        return document

    def get_document(self, document_id: UUID) -> SourceDocument | None:
        return self.documents.get(document_id)

    def find_document_by_sha256(self, sha256: str) -> SourceDocument | None:
        return next((item for item in self.documents.values() if item.sha256 == sha256), None)

    def list_documents(self) -> list[SourceDocument]:
        return list(self.documents.values())

    def save_document_pages(self, pages: list[DocumentPage]) -> list[DocumentPage]:
        if pages:
            self.document_pages[pages[0].document_id] = pages
        return pages

    def list_document_pages(self, document_id: UUID) -> list[DocumentPage]:
        return self.document_pages.get(document_id, [])

    def save_processing_job(self, job: ProcessingJob) -> ProcessingJob:
        self.processing_jobs[job.id] = job
        return job

    def get_processing_job(self, job_id: UUID) -> ProcessingJob | None:
        return self.processing_jobs.get(job_id)

    def list_processing_jobs(self, document_id: UUID | None = None) -> list[ProcessingJob]:
        jobs = list(self.processing_jobs.values())
        if document_id is not None:
            jobs = [job for job in jobs if job.document_id == document_id]
        return jobs

    def save_opportunity(self, opportunity: Opportunity) -> Opportunity:
        self.opportunities[opportunity.id] = opportunity
        return opportunity

    def list_opportunities(self) -> list[Opportunity]:
        return list(self.opportunities.values())
