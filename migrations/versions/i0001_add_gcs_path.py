"""Add gcs_path to claim_documents

Revision ID: i0001_add_gcs_path
Revises: h0001_add_audit_findings
Create Date: 2026-02-22

Adds a nullable ``gcs_path`` TEXT column to ``claim_documents`` that stores
the GCS blob name (relative path inside the configured bucket) for the
original (unencrypted) copy of the document.  Rows that pre-date GCS
integration will have ``NULL`` and continue to be served from the local
encrypted-file fallback.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "i0001_add_gcs_path"
down_revision: Union[str, None] = "h0001_add_audit_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claim_documents",
        sa.Column("gcs_path", sa.Text(), nullable=True, comment="GCS blob name for the original document"),
    )
    # Index speeds up admin queries that filter/join on gcs_path status
    op.create_index(
        "ix_claim_docs_gcs_path_not_null",
        "claim_documents",
        [sa.text("gcs_path")],
        postgresql_where=sa.text("gcs_path IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_claim_docs_gcs_path_not_null", table_name="claim_documents")
    op.drop_column("claim_documents", "gcs_path")
