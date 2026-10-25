from typing import Any

import httpx
import pytest

from contractfit.domain import Opportunity
from contractfit.embeddings import EmbeddingService, OllamaEmbeddingProvider
from contractfit.sample_data import SAMPLE_PROFILE
from contractfit.store import InMemoryStore


class FakeEmbeddingProvider:
    name = "fake:test"
    dimensions = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        lowered = text.lower()
        return [
            float("hvac" in lowered),
            float("roof" in lowered),
            0.25,
        ]


def opportunities() -> list[Opportunity]:
    return [
        Opportunity(source="test", source_id="hvac", title="HVAC", scope="HVAC maintenance"),
        Opportunity(source="test", source_id="roof", title="Roof", scope="Roof replacement"),
    ]


def test_embedding_service_caches_vectors_and_ranks_by_cosine_similarity() -> None:
    store = InMemoryStore()
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider, store)
    profile = SAMPLE_PROFILE.model_copy(update={"capability_statement": "HVAC services"})
    items = opportunities()

    first = service.score_opportunities(profile, items, limit=10)
    second = service.score_opportunities(profile, items, limit=10)

    assert first[items[0].id] > first[items[1].id]
    assert second == first
    assert provider.calls == ["HVAC services", "HVAC maintenance", "Roof replacement"]


def test_changed_text_invalidates_cached_embedding() -> None:
    store = InMemoryStore()
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider, store)
    items = opportunities()
    service.score_opportunities(SAMPLE_PROFILE, items, limit=10)
    items[0].scope = "Roof and envelope repair"

    service.score_opportunities(SAMPLE_PROFILE, items, limit=10)

    assert provider.calls.count("Roof and envelope repair") == 1
    assert len(provider.calls) == 4


def test_ollama_embedding_provider_validates_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("POST", str(args[0]))
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OllamaEmbeddingProvider("http://ollama", "tiny", dimensions=3)

    assert provider.name == "ollama:tiny"
    assert provider.embed("test") == [0.1, 0.2, 0.3]


def test_ollama_embedding_provider_rejects_wrong_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("POST", str(args[0]))
        return httpx.Response(200, json={"embeddings": [[0.1]]}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ValueError, match="expected 3"):
        OllamaEmbeddingProvider("http://ollama", dimensions=3).embed("test")
