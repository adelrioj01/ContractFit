import os
from uuid import uuid4

import pytest

from contractfit.database import build_engine, build_session_factory
from contractfit.embeddings import EmbeddingTarget, SemanticEmbedding
from contractfit.sql_store import SqlAlchemyStore

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="requires the migrated PostgreSQL pgvector CI service",
)


def vector(first: float, second: float) -> list[float]:
    return [first, second, *([0.0] * 766)]


def test_pgvector_store_returns_cosine_ranked_embeddings() -> None:
    store = SqlAlchemyStore(build_session_factory(build_engine(os.environ["DATABASE_URL"])))
    store.reset()
    closest_id = uuid4()
    farther_id = uuid4()
    for target_id, embedding in (
        (closest_id, vector(1.0, 0.0)),
        (farther_id, vector(0.0, 1.0)),
    ):
        store.save_embedding(
            SemanticEmbedding(
                target=EmbeddingTarget.OPPORTUNITY,
                target_id=target_id,
                model="test:768",
                content_sha256=str(target_id).replace("-", "") * 2,
                vector=embedding,
            )
        )

    hits = store.search_embeddings(
        EmbeddingTarget.OPPORTUNITY,
        "test:768",
        vector(1.0, 0.0),
        limit=2,
    )

    assert [hit.target_id for hit in hits] == [closest_id, farther_id]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.0)
