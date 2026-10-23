"""Add binary document metadata and page-level text."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0002"
down_revision: str | None = "20261023_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("source_documents", sa.Column("storage_key", sa.String(1000), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("content_type", sa.String(255), nullable=False, server_default="text/plain"),
    )
    op.add_column(
        "source_documents", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "source_documents",
        sa.Column("status", sa.String(50), nullable=False, server_default="ready"),
    )
    op.add_column(
        "source_documents", sa.Column("page_count", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("source_documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_source_documents_sha256", "source_documents", ["sha256"])
    op.create_index("ix_source_documents_status", "source_documents", ["status"])
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("needs_ocr", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_number"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_pages_document_id", table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_index("ix_source_documents_status", table_name="source_documents")
    op.drop_constraint("uq_source_documents_sha256", "source_documents", type_="unique")
    op.drop_column("source_documents", "error_message")
    op.drop_column("source_documents", "page_count")
    op.drop_column("source_documents", "status")
    op.drop_column("source_documents", "size_bytes")
    op.drop_column("source_documents", "content_type")
    op.drop_column("source_documents", "storage_key")
    op.drop_column("source_documents", "sha256")
