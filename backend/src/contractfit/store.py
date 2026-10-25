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


class ContractFitStore(Protocol):
    def reset(self) -> None: ...
    def get_profile(self, organization_id: UUID | None = None) -> CompanyProfile | None: ...
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
        self.embeddings: dict[tuple[EmbeddingTarget, UUID, str], SemanticEmbedding] = {}
        self.review_items: dict[UUID, ReviewItem] = {}
        self.identities: dict[UUID, AuthIdentity] = {}

    def reset(self) -> None:
        self.profiles.clear()
        self.documents.clear()
        self.document_pages.clear()
        self.processing_jobs.clear()
        self.opportunities.clear()
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
