"""Track the catalog origin of organization-owned source documents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0009"
down_revision: str | None = "20261026_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("origin_opportunity_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("origin_url", sa.String(2000), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_documents_origin_opportunity_id",
        "source_documents",
        "opportunities",
        ["origin_opportunity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_source_documents_origin_opportunity_id",
        "source_documents",
        ["origin_opportunity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_documents_origin_opportunity_id",
        table_name="source_documents",
    )
    op.drop_constraint(
        "fk_source_documents_origin_opportunity_id",
        "source_documents",
        type_="foreignkey",
    )
    op.drop_column("source_documents", "origin_url")
    op.drop_column("source_documents", "origin_opportunity_id")
