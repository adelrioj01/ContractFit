"""Add cached semantic embeddings and pgvector search."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20261025_0006"
down_revision: str | None = "20261024_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "semantic_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target", "target_id", "model", name="uq_semantic_embedding_target"
        ),
    )
    op.create_index("ix_semantic_embeddings_target", "semantic_embeddings", ["target"])
    op.create_index("ix_semantic_embeddings_target_id", "semantic_embeddings", ["target_id"])
    op.create_index(
        "ix_semantic_embeddings_organization_id",
        "semantic_embeddings",
        ["organization_id"],
    )
    op.create_index("ix_semantic_embeddings_model", "semantic_embeddings", ["model"])
    op.create_index(
        "ix_semantic_embeddings_vector_hnsw",
        "semantic_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_semantic_embeddings_vector_hnsw", table_name="semantic_embeddings")
    op.drop_index("ix_semantic_embeddings_model", table_name="semantic_embeddings")
    op.drop_index("ix_semantic_embeddings_organization_id", table_name="semantic_embeddings")
    op.drop_index("ix_semantic_embeddings_target_id", table_name="semantic_embeddings")
    op.drop_index("ix_semantic_embeddings_target", table_name="semantic_embeddings")
    op.drop_table("semantic_embeddings")
