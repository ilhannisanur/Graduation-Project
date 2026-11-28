"""add tracks.popularity, has_vocals and genres

Filled from the Jamendo API (stats and musicinfo) by app.music.curate and the downloader.
NULL / empty means "not known yet"; the selector treats such tracks as average.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-28 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tracks", sa.Column("popularity", sa.Float(), nullable=True))
    op.add_column("tracks", sa.Column("has_vocals", sa.Boolean(), nullable=True))
    op.add_column(
        "tracks",
        sa.Column(
            "genres",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_tracks_popularity_range",
        "tracks",
        "popularity IS NULL OR (popularity >= 0 AND popularity <= 1)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_tracks_popularity_range", "tracks", type_="check")
    op.drop_column("tracks", "genres")
    op.drop_column("tracks", "has_vocals")
    op.drop_column("tracks", "popularity")
