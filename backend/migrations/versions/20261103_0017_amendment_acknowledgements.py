"""Persist organization amendment acknowledgements."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_0017"
down_revision: str | None = "20261031_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "amendment_acknowledgements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("previous_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("selections", sa.JSON(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_snapshot_id"],
            ["sam_opportunity_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_snapshot_id"],
            ["sam_opportunity_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "previous_snapshot_id",
            "current_snapshot_id",
            name="uq_amendment_acknowledgements_version_pair",
        ),
    )
    for column in (
        "organization_id",
        "opportunity_id",
        "previous_snapshot_id",
        "current_snapshot_id",
        "acknowledged_by_user_id",
        "acknowledged_at",
    ):
        op.create_index(
            f"ix_amendment_acknowledgements_{column}",
            "amendment_acknowledgements",
            [column],
        )


def downgrade() -> None:
    op.drop_table("amendment_acknowledgements")
