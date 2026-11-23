"""add song_requests.on_air_name

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("song_requests", sa.Column("on_air_name", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("song_requests", "on_air_name")
