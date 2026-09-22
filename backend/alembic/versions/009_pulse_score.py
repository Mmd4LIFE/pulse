"""pulse score

Revision ID: 009
Revises: 008
Create Date: 2026-09-22 10:12:04.118402
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pulse_scores",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pulse_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("AI", "HUMAN", name="score_source", native_enum=True),
            nullable=False,
        ),
        sa.Column("rater_id", sa.BigInteger(), nullable=True),
        sa.Column("value", sa.Numeric(precision=3, scale=1), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["pulse_id"], ["pulses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rater_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pulse_scores_pulse_created",
        "pulse_scores",
        ["pulse_id", sa.text("created_at DESC")],
    )
    # The model gets one say per pulse...
    op.create_index(
        "uq_pulse_scores_ai",
        "pulse_scores",
        ["pulse_id"],
        unique=True,
        postgresql_where=sa.text("rater_id IS NULL"),
    )
    # ...and so, when people can rate, does each person.
    op.create_index(
        "uq_pulse_scores_rater",
        "pulse_scores",
        ["pulse_id", "rater_id"],
        unique=True,
        postgresql_where=sa.text("rater_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_pulse_scores_rater", table_name="pulse_scores")
    op.drop_index("uq_pulse_scores_ai", table_name="pulse_scores")
    op.drop_index("ix_pulse_scores_pulse_created", table_name="pulse_scores")
    op.drop_table("pulse_scores")
    sa.Enum(name="score_source").drop(op.get_bind(), checkfirst=True)
