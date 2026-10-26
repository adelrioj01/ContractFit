import math
from typing import Protocol
from uuid import UUID

from contractfit.auth import AuthIdentity
from contractfit.domain import (
    CompanyProfile,
    DocumentPage,
    Opportunity,
    ProcessingJob,
    SourceDocument,
)
from contractfit.embeddings import EmbeddingHit, EmbeddingTarget, SemanticEmbedding
from contractfit.review import ReviewItem, ReviewStatus, review_sort_key
from contractfit.sam_models import SamIngestionRun, SamOpportunitySnapshot


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
    def list_documents(self, organization_id: UUID) -> list[SourceDocument]: ...
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
    def get_opportunity_by_source(
        self, source: str, source_id: str
    ) -> Opportunity | None: ...
    def list_opportunities(
        self, organization_id: UUID | None = None
    ) -> list[Opportunity]: ...
    def save_sam_ingestion_run(self, run: SamIngestionRun) -> SamIngestionRun: ...
    def list_sam_ingestion_runs(self) -> list[SamIngestionRun]: ...
    def save_sam_snapshot(
        self, snapshot: SamOpportunitySnapshot
    ) -> SamOpportunitySnapshot: ...
    def get_latest_sam_snapshot(
        self, opportunity_id: UUID
    ) -> SamOpportunitySnapshot | None: ...
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
    def get_review_item(
        self, review_id: UUID, organization_id: UUID
    ) -> ReviewItem | None: ...
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
        self.document_pages: dict[UUID, list[DocumentPage]] = {}
        self.processing_jobs: dict[UUID, ProcessingJob] = {}
        self.opportunities: dict[UUID, Opportunity] = {}
        self.sam_ingestion_runs: dict[UUID, SamIngestionRun] = {}
        self.sam_snapshots: dict[UUID, SamOpportunitySnapshot] = {}
        self.embeddings: dict[tuple[EmbeddingTarget, UUID, str], SemanticEmbedding] = {}
        self.review_items: dict[UUID, ReviewItem] = {}
        self.identities: dict[UUID, AuthIdentity] = {}

    def reset(self) -> None:
        self.profiles.clear()
        self.documents.clear()
        self.document_pages.clear()
        self.processing_jobs.clear()
        self.opportunities.clear()
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

    def find_document_by_sha256(
        self, sha256: str, organization_id: UUID
    ) -> SourceDocument | None:
        return next(
            (
                item
                for item in self.documents.values()
                if item.sha256 == sha256 and item.organization_id == organization_id
            ),
            None,
        )

    def list_documents(self, organization_id: UUID) -> list[SourceDocument]:
        return [
            item
            for item in self.documents.values()
            if item.organization_id == organization_id
        ]

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

    def get_opportunity_by_source(
        self, source: str, source_id: str
    ) -> Opportunity | None:
        return next(
            (
                item
                for item in self.opportunities.values()
                if item.source == source and item.source_id == source_id
            ),
            None,
        )

    def list_opportunities(
        self, organization_id: UUID | None = None
    ) -> list[Opportunity]:
        opportunities = list(self.opportunities.values())
        if organization_id is None:
            return opportunities
        return [
            item
            for item in opportunities
            if item.document_id is None
            or self.get_document(item.document_id, organization_id) is not None
        ]

    def save_sam_ingestion_run(self, run: SamIngestionRun) -> SamIngestionRun:
        self.sam_ingestion_runs[run.id] = run
        return run

    def list_sam_ingestion_runs(self) -> list[SamIngestionRun]:
        return sorted(
            self.sam_ingestion_runs.values(),
            key=lambda item: item.started_at,
        )

    def save_sam_snapshot(
        self, snapshot: SamOpportunitySnapshot
    ) -> SamOpportunitySnapshot:
        if snapshot.opportunity_id not in self.opportunities:
            raise ValueError("SAM snapshot opportunity does not exist")
        self.sam_snapshots[snapshot.id] = snapshot
        return snapshot

    def get_latest_sam_snapshot(
        self, opportunity_id: UUID
    ) -> SamOpportunitySnapshot | None:
        snapshots = self.list_sam_snapshots(opportunity_id)
        return snapshots[-1] if snapshots else None

    def list_sam_snapshots(self, opportunity_id: UUID) -> list[SamOpportunitySnapshot]:
        return sorted(
            (
                item
                for item in self.sam_snapshots.values()
                if item.opportunity_id == opportunity_id
            ),
            key=lambda item: item.observed_at,
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
        hits = [EmbeddingHit(target_id=item.target_id, score=cosine_score(item.vector)) for item in candidates]
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
