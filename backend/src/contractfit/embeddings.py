import hashlib
import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field, field_validator

from contractfit.domain import CompanyProfile, Opportunity


class EmbeddingTarget(StrEnum):
    PROFILE = "profile"
    OPPORTUNITY = "opportunity"


class SemanticEmbedding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    target: EmbeddingTarget
    target_id: UUID
    organization_id: UUID | None = None
    model: str = Field(min_length=1, max_length=255)
    content_sha256: str = Field(min_length=64, max_length=64)
    vector: list[float] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("vector")
    @classmethod
    def vector_must_be_finite(cls, value: list[float]) -> list[float]:
        if not all(math.isfinite(component) for component in value):
            raise ValueError("embedding vector must contain only finite values")
        return value


class EmbeddingHit(BaseModel):
    target_id: UUID
    score: float = Field(ge=0, le=1)


class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


class EmbeddingIndex(Protocol):
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


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model: str = "nomic-embed-text",
        dimensions: int = 768,
        timeout_seconds: float = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("cannot embed empty text")
        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": text},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise ValueError("Ollama response did not contain embeddings")
        vector = [float(component) for component in embeddings[0]]
        if len(vector) != self.dimensions:
            raise ValueError(
                f"embedding model returned {len(vector)} dimensions; expected {self.dimensions}"
            )
        if not all(math.isfinite(component) for component in vector):
            raise ValueError("embedding model returned a non-finite component")
        return vector


class EmbeddingSimilarityScorer:
    """Pairwise cosine scorer for labeled evaluation and small experiments."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self._cache: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return f"embedding-cosine:{self.provider.name}"

    def score(self, query: str, candidate: str) -> tuple[float, str]:
        query_vector = self._embed(query)
        candidate_vector = self._embed(candidate)
        dot = sum(
            left * right
            for left, right in zip(query_vector, candidate_vector, strict=True)
        )
        query_norm = math.sqrt(sum(value * value for value in query_vector))
        candidate_norm = math.sqrt(sum(value * value for value in candidate_vector))
        similarity = 0.0
        if query_norm and candidate_norm:
            similarity = max(0.0, min(1.0, dot / (query_norm * candidate_norm)))
        return similarity, f"Embedding cosine similarity is {similarity:.0%}."

    def _embed(self, text: str) -> list[float]:
        if text not in self._cache:
            vector = self.provider.embed(text)
            if len(vector) != self.provider.dimensions:
                raise ValueError("embedding provider returned an unexpected vector size")
            self._cache[text] = vector
        return self._cache[text]


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, index: EmbeddingIndex) -> None:
        self.provider = provider
        self.index = index

    def score_opportunities(
        self,
        profile: CompanyProfile,
        opportunities: list[Opportunity],
        limit: int,
    ) -> dict[UUID, float]:
        if not opportunities:
            return {}
        profile_embedding = self._get_or_create(
            EmbeddingTarget.PROFILE,
            profile.id,
            profile.capability_statement,
            profile.organization_id,
        )
        for opportunity in opportunities:
            self._get_or_create(
                EmbeddingTarget.OPPORTUNITY,
                opportunity.id,
                opportunity.scope,
                None,
            )
        hits = self.index.search_embeddings(
            EmbeddingTarget.OPPORTUNITY,
            self.provider.name,
            profile_embedding.vector,
            min(limit, len(opportunities)),
        )
        opportunity_ids = {item.id for item in opportunities}
        return {hit.target_id: hit.score for hit in hits if hit.target_id in opportunity_ids}

    def _get_or_create(
        self,
        target: EmbeddingTarget,
        target_id: UUID,
        content: str,
        organization_id: UUID | None,
    ) -> SemanticEmbedding:
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self.index.get_embedding(
            target, target_id, self.provider.name, content_sha256
        )
        if existing is not None:
            return existing
        vector = self.provider.embed(content)
        if len(vector) != self.provider.dimensions:
            raise ValueError("embedding provider returned an unexpected vector size")
        return self.index.save_embedding(
            SemanticEmbedding(
                target=target,
                target_id=target_id,
                organization_id=organization_id,
                model=self.provider.name,
                content_sha256=content_sha256,
                vector=vector,
            )
        )
