"""private accounts and connected channels

Revision ID: 003
Revises: 002
Create Date: 2026-09-08 21:24:10.044172
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Autogenerate does not detect new values on a native enum, so the
    # follow-request notification kind is added by hand. Postgres 12+ allows
    # this inside a transaction as long as the value is not used in the same
    # one, which it is not.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'FOLLOW_REQUEST'")

    op.create_table(
        "channels",
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("can_post", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("last_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_channels_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channels")),
        sa.UniqueConstraint("owner_id", name=op.f("uq_channels_owner_id")),
    )
    op.create_index(op.f("ix_channels_chat_id"), "channels", ["chat_id"], unique=False)
    op.create_index(
        op.f("ix_channels_created_at"), "channels", ["created_at"], unique=False
    )
    op.create_table(
        "follow_requests",
        sa.Column("requester_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requester_id <> target_id", name=op.f("ck_follow_requests_no_self_request")
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_follow_requests_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["users.id"],
            name=op.f("fk_follow_requests_target_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "requester_id", "target_id", name=op.f("pk_follow_requests")
        ),
    )
    op.create_index(
        "ix_follow_requests_target_created",
        "follow_requests",
        ["target_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "pulses",
        sa.Column(
            "sent_to_channel", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.create_index(op.f("ix_users_is_private"), "users", ["is_private"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # The FOLLOW_REQUEST enum value is deliberately left in place: Postgres
    # cannot drop a value from an enum, and rows may still reference it.
    op.drop_index(op.f("ix_users_is_private"), table_name="users")
    op.drop_column("users", "is_private")
    op.drop_column("pulses", "sent_to_channel")
    op.drop_index("ix_follow_requests_target_created", table_name="follow_requests")
    op.drop_table("follow_requests")
    op.drop_index(op.f("ix_channels_created_at"), table_name="channels")
    op.drop_index(op.f("ix_channels_chat_id"), table_name="channels")
    op.drop_table("channels")
    # ### end Alembic commands ###
