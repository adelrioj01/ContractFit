"""Persist organization-owned opportunity feedback."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0018"
down_revision: str | None = "20261103_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            name="uq_opportunity_feedback_organization_opportunity",
        ),
    )
    for column in (
        "organization_id",
        "opportunity_id",
        "submitted_by_user_id",
        "updated_at",
    ):
        op.create_index(
            f"ix_opportunity_feedback_{column}", "opportunity_feedback", [column]
        )


def downgrade() -> None:
    op.drop_table("opportunity_feedback")
