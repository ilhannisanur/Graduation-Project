"""add tracks.gain_db, start_s and end_s

Filled by `python -m app.music.curate analyze`. The player plays a song from start_s,
schedules its transitions from end_s (the end of the music, before trailing silence) and
applies gain_db so all songs sound equally loud. NULL means "not analysed yet".

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-28 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tracks", sa.Column("gain_db", sa.Float(), nullable=True))
    op.add_column("tracks", sa.Column("start_s", sa.Float(), nullable=True))
    op.add_column("tracks", sa.Column("end_s", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tracks", "end_s")
    op.drop_column("tracks", "start_s")
    op.drop_column("tracks", "gain_db")
