"""Scope source documents to organizations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0007"
down_revision: str | None = "20261025_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
    )

    # Existing documents have no trustworthy ownership information. Quarantine
    # them under a membership-free organization instead of exposing them to an
    # arbitrary customer during the migration.
    op.execute(
        sa.text(
            """
            INSERT INTO organizations (id, name, created_at)
            SELECT CAST(:legacy_id AS UUID), 'Legacy quarantined documents', CURRENT_TIMESTAMP
            WHERE EXISTS (SELECT 1 FROM source_documents)
              AND NOT EXISTS (
                  SELECT 1 FROM organizations WHERE id = CAST(:legacy_id AS UUID)
              )
            """
        ).bindparams(legacy_id=LEGACY_ORGANIZATION_ID)
    )
    op.execute(
        sa.text(
            """
            UPDATE source_documents
            SET organization_id = CAST(:legacy_id AS UUID)
            WHERE organization_id IS NULL
            """
        ).bindparams(legacy_id=LEGACY_ORGANIZATION_ID)
    )

    op.alter_column("source_documents", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_source_documents_organization_id",
        "source_documents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_source_documents_organization_id",
        "source_documents",
        ["organization_id"],
    )
    op.drop_constraint(
        "uq_source_documents_sha256",
        "source_documents",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_source_documents_organization_sha256",
        "source_documents",
        ["organization_id", "sha256"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_source_documents_organization_sha256",
        "source_documents",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_source_documents_sha256",
        "source_documents",
        ["sha256"],
    )
    op.drop_index("ix_source_documents_organization_id", table_name="source_documents")
    op.drop_constraint(
        "fk_source_documents_organization_id",
        "source_documents",
        type_="foreignkey",
    )
    op.drop_column("source_documents", "organization_id")
