"""retire reposts whose original was deleted

Deleting a pulse used to leave its reposts behind. Because a repost holds no
content of its own, each one rendered in followers' timelines as a blank card:
an author line and a counter row with nothing between them.

The delete path now retires reposts alongside the original. This clears the
rows written before that fix.

Revision ID: 002
Revises: 001
Create Date: 2026-09-08 21:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pulses AS repost
           SET is_deleted = true,
               deleted_at = COALESCE(repost.deleted_at, original.deleted_at, now())
          FROM pulses AS original
         WHERE repost.repulse_of_id = original.id
           AND repost.is_deleted = false
           AND original.is_deleted = true
        """
    )


def downgrade() -> None:
    # Not reversible: once these rows are marked deleted there is no record of
    # which were already deleted beforehand, so restoring them would resurrect
    # blank cards. Leaving them retired is the safe direction.
    pass
