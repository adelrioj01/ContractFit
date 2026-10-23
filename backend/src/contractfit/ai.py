import json
import re
from typing import Protocol

import httpx


class SemanticScorer(Protocol):
    @property
    def name(self) -> str: ...

    def score(self, capability: str, scope: str) -> tuple[float, str]: ...


class LexicalSemanticScorer:
    """Offline fallback with the same contract as a model-backed scorer."""

    name = "lexical-fallback"

    def score(self, capability: str, scope: str) -> tuple[float, str]:
        capability_tokens = self._tokenize(capability)
        scope_tokens = self._tokenize(scope)
        if not scope_tokens:
            return 0.5, "No scope was available for semantic comparison."
        overlap = len(capability_tokens & scope_tokens) / len(scope_tokens)
        score = min(1.0, 0.35 + overlap * 1.5)
        return score, f"Capability-to-scope token coverage is {overlap:.0%}."

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))


class OllamaSemanticScorer:
    """Optional local-model scorer. Any failure falls back safely upstream."""

    name = "ollama-local-llm"

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def score(self, capability: str, scope: str) -> tuple[float, str]:
        prompt = (
            "Compare a contractor capability statement with a government contract scope. "
            "Return only JSON with score (0 to 1) and reason.\n"
            f"CAPABILITY:\n{capability}\nSCOPE:\n{scope}"
        )
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = json.loads(response.json()["response"])
        return max(0.0, min(1.0, float(payload["score"]))), str(payload["reason"])
