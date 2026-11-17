"""Add organization-owned opportunity watches and alerts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0014"
down_revision: str | None = "20261030_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_watches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "opportunity_id", name="uq_opportunity_watches_organization_opportunity"),
    )
    op.create_index("ix_opportunity_watches_organization_id", "opportunity_watches", ["organization_id"])
    op.create_index("ix_opportunity_watches_opportunity_id", "opportunity_watches", ["opportunity_id"])
    op.create_index("ix_opportunity_watches_created_at", "opportunity_watches", ["created_at"])
    op.create_table(
        "opportunity_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("watch_id", sa.Uuid(), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watch_id"], ["opportunity_watches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "dedupe_key", name="uq_opportunity_alerts_organization_dedupe"),
    )
    for column in ("organization_id", "opportunity_id", "watch_id", "alert_type", "status", "created_at", "updated_at"):
        op.create_index(f"ix_opportunity_alerts_{column}", "opportunity_alerts", [column])


def downgrade() -> None:
    op.drop_table("opportunity_alerts")
    op.drop_table("opportunity_watches")
