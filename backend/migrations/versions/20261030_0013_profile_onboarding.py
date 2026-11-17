"""Add structured onboarding evidence to company profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0013"
down_revision: str | None = "20261029_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company_profiles",
        sa.Column(
            "insurance_coverages",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "company_profiles",
        sa.Column(
            "contract_preferences",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "company_profiles",
        sa.Column(
            "past_performance",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("company_profiles", "insurance_coverages", server_default=None)
    op.alter_column("company_profiles", "contract_preferences", server_default=None)
    op.alter_column("company_profiles", "past_performance", server_default=None)


def downgrade() -> None:
    op.drop_column("company_profiles", "past_performance")
    op.drop_column("company_profiles", "contract_preferences")
    op.drop_column("company_profiles", "insurance_coverages")
