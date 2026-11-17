"""Add organization-owned opportunity pipeline items."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0011"
down_revision: str | None = "20261028_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("next_action", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            name="uq_pipeline_items_organization_opportunity",
        ),
    )
    op.create_index("ix_pipeline_items_organization_id", "pipeline_items", ["organization_id"])
    op.create_index("ix_pipeline_items_opportunity_id", "pipeline_items", ["opportunity_id"])
    op.create_index("ix_pipeline_items_owner_user_id", "pipeline_items", ["owner_user_id"])
    op.create_index("ix_pipeline_items_status", "pipeline_items", ["status"])
    op.create_index("ix_pipeline_items_updated_at", "pipeline_items", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_items_updated_at", table_name="pipeline_items")
    op.drop_index("ix_pipeline_items_status", table_name="pipeline_items")
    op.drop_index("ix_pipeline_items_owner_user_id", table_name="pipeline_items")
    op.drop_index("ix_pipeline_items_opportunity_id", table_name="pipeline_items")
    op.drop_index("ix_pipeline_items_organization_id", table_name="pipeline_items")
    op.drop_table("pipeline_items")
