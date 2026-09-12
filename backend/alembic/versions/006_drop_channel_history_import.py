"""drop the channel history import

The import feature was withdrawn. Migration 005 had already been applied, so
its columns are removed here rather than by deleting that revision, which would
leave any database stamped 005 unable to resolve its own history.

Nothing is lost: the feature never completed an import on any deployment, so
these columns held no data.

Revision ID: 006
Revises: 005
Create Date: 2026-09-12 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_pulses_source_message",
        table_name="pulses",
        postgresql_where=sa.text("source_channel_id IS NOT NULL"),
    )
    op.drop_index(
        "ix_pulses_source_date",
        table_name="pulses",
        postgresql_where=sa.text("source_channel_id IS NOT NULL"),
    )
    op.drop_column("pulses", "reactions")
    op.drop_column("pulses", "source_date")
    op.drop_column("pulses", "source_message_id")
    op.drop_column("pulses", "source_channel_id")

    op.drop_column("channels", "imported_at")
    op.drop_column("channels", "import_error")
    op.drop_column("channels", "import_done")
    op.drop_column("channels", "import_total")
    op.drop_column("channels", "import_status")


def downgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "import_status",
            sa.String(length=16),
            server_default=sa.text("'idle'"),
            nullable=False,
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "import_total", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "channels",
        sa.Column("import_done", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "channels", sa.Column("import_error", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "channels", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column("pulses", sa.Column("source_channel_id", sa.BigInteger(), nullable=True))
    op.add_column("pulses", sa.Column("source_message_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "pulses", sa.Column("source_date", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "pulses",
        sa.Column("reactions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_pulses_source_date",
        "pulses",
        ["author_id", sa.text("source_date DESC")],
        unique=False,
        postgresql_where=sa.text("source_channel_id IS NOT NULL"),
    )
    op.create_index(
        "uq_pulses_source_message",
        "pulses",
        ["source_channel_id", "source_message_id"],
        unique=True,
        postgresql_where=sa.text("source_channel_id IS NOT NULL"),
    )
