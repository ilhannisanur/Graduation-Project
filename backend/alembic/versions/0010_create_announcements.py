"""create announcements

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "announcements",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(), nullable=False),
        sa.Column("opening_style", sa.String(), nullable=True),
        sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column("next_track_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["next_track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_announcements_created_at"), "announcements", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_announcements_created_at"), table_name="announcements")
    op.drop_table("announcements")
