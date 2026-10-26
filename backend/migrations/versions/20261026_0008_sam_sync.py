"""Persist SAM.gov synchronization runs and opportunity snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0008"
down_revision: str | None = "20261026_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("opportunities_source_id_key", "opportunities", type_="unique")
    op.create_unique_constraint(
        "uq_opportunities_source_identity",
        "opportunities",
        ["source", "source_id"],
    )

    op.create_table(
        "sam_ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("posted_from", sa.Date(), nullable=False),
        sa.Column("posted_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sam_ingestion_runs_status", "sam_ingestion_runs", ["status"])
    op.create_index(
        "ix_sam_ingestion_runs_started_at", "sam_ingestion_runs", ["started_at"]
    )

    op.create_table(
        "sam_opportunity_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sam_opportunity_snapshots_opportunity_id",
        "sam_opportunity_snapshots",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_sam_opportunity_snapshots_content_sha256",
        "sam_opportunity_snapshots",
        ["content_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sam_opportunity_snapshots_content_sha256",
        table_name="sam_opportunity_snapshots",
    )
    op.drop_index(
        "ix_sam_opportunity_snapshots_opportunity_id",
        table_name="sam_opportunity_snapshots",
    )
    op.drop_table("sam_opportunity_snapshots")
    op.drop_index("ix_sam_ingestion_runs_started_at", table_name="sam_ingestion_runs")
    op.drop_index("ix_sam_ingestion_runs_status", table_name="sam_ingestion_runs")
    op.drop_table("sam_ingestion_runs")

    op.drop_constraint(
        "uq_opportunities_source_identity", "opportunities", type_="unique"
    )
    op.create_unique_constraint(
        "opportunities_source_id_key", "opportunities", ["source_id"]
    )
