"""Add subscribers table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "role_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="'[]'::jsonb",
            nullable=False,
        ),
        sa.Column(
            "subscribed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("unsubscribe_token", sa.String(64), nullable=False),
        sa.UniqueConstraint("email", name="uq_subscribers_email"),
    )
    op.create_index("ix_subscribers_unsubscribe_token", "subscribers", ["unsubscribe_token"])
    op.create_index("ix_subscribers_is_active", "subscribers", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_subscribers_is_active", table_name="subscribers")
    op.drop_index("ix_subscribers_unsubscribe_token", table_name="subscribers")
    op.drop_table("subscribers")
