"""Track multiple SAM snapshot origins for deduplicated documents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0012"
down_revision: str | None = "20261029_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_origins",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("origin_url", sa.String(2000), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "opportunity_id", "origin_url", "snapshot_sha256"
        ),
    )
    op.create_index(
        "ix_document_origins_document_id", "document_origins", ["document_id"]
    )
    op.execute(
        """
        INSERT INTO document_origins (
            organization_id, opportunity_id, origin_url, snapshot_sha256, document_id
        )
        SELECT organization_id, origin_opportunity_id, origin_url,
               origin_snapshot_sha256, id
        FROM source_documents
        WHERE origin_opportunity_id IS NOT NULL
          AND origin_url IS NOT NULL
          AND origin_snapshot_sha256 IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_origins_document_id", table_name="document_origins")
    op.drop_table("document_origins")
