"""Add the organization-scoped human review queue."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261024_0004"
down_revision: str | None = "20261023_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "field_name",
            name="uq_review_items_opportunity_field",
        ),
    )
    op.create_index("ix_review_items_organization_id", "review_items", ["organization_id"])
    op.create_index("ix_review_items_opportunity_id", "review_items", ["opportunity_id"])
    op.create_index("ix_review_items_status", "review_items", ["status"])
    op.create_table(
        "review_evidence",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(255), nullable=True),
        sa.Column("supporting_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_id"], ["review_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id", "position"),
    )


def downgrade() -> None:
    op.drop_table("review_evidence")
    op.drop_index("ix_review_items_status", table_name="review_items")
    op.drop_index("ix_review_items_opportunity_id", table_name="review_items")
    op.drop_index("ix_review_items_organization_id", table_name="review_items")
    op.drop_table("review_items")
