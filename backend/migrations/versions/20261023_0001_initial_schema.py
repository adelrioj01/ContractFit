"""Create the initial ContractFit persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("service_categories", sa.JSON(), nullable=False),
        sa.Column("states", sa.JSON(), nullable=False),
        sa.Column("maximum_distance_miles", sa.Integer(), nullable=True),
        sa.Column("minimum_contract_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("maximum_contract_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("licenses", sa.JSON(), nullable=False),
        sa.Column("certifications", sa.JSON(), nullable=False),
        sa.Column("set_asides", sa.JSON(), nullable=False),
        sa.Column("naics_codes", sa.JSON(), nullable=False),
        sa.Column("capability_statement", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_profiles_organization_id", "company_profiles", ["organization_id"])
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("agency", sa.String(500), nullable=True),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("place_of_performance", sa.String(500), nullable=True),
        sa.Column("set_aside", sa.String(255), nullable=True),
        sa.Column("estimated_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_table(
        "requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("evidence_document_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_page", sa.Integer(), nullable=True),
        sa.Column("evidence_section", sa.String(255), nullable=True),
        sa.Column("evidence_supporting_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_document_id"], ["source_documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirements_category", "requirements", ["category"])
    op.create_index("ix_requirements_opportunity_id", "requirements", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_requirements_opportunity_id", table_name="requirements")
    op.drop_index("ix_requirements_category", table_name="requirements")
    op.drop_table("requirements")
    op.drop_table("opportunities")
    op.drop_table("source_documents")
    op.drop_index("ix_company_profiles_organization_id", table_name="company_profiles")
    op.drop_table("company_profiles")
