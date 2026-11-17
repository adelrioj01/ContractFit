"""Track which SAM snapshot produced each imported attachment."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0010"
down_revision: str | None = "20261027_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("origin_snapshot_sha256", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_source_documents_origin_snapshot_sha256",
        "source_documents",
        ["origin_snapshot_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_documents_origin_snapshot_sha256",
        table_name="source_documents",
    )
    op.drop_column("source_documents", "origin_snapshot_sha256")
