"""drop user_profiles.artists, news_topics and weather_city

The broadcast is one shared stream: news and weather are station settings, and the
Creative Commons catalog cannot play a listener's favourite artists. Only genres and
languages stay in the profile. The dropped values are deleted, not moved anywhere.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-24 23:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("user_profiles", "artists")
    op.drop_column("user_profiles", "news_topics")
    op.drop_column("user_profiles", "weather_city")


def downgrade() -> None:
    """Downgrade schema. The columns come back empty; the old values are gone."""
    for name in ("artists", "news_topics"):
        op.add_column(
            "user_profiles",
            sa.Column(
                name,
                postgresql.ARRAY(sa.Text()),
                server_default=sa.text("'{}'::text[]"),
                nullable=False,
            ),
        )
    op.add_column("user_profiles", sa.Column("weather_city", sa.Text(), nullable=True))
