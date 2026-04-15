"""Initial schema: job_postings, processed_postings, skill_trends

Revision ID: 0001
Revises:
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── job_postings ──────────────────────────────────────────────────────────
    op.create_table(
        "job_postings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.VARCHAR(50), nullable=False),
        sa.Column("role_category", sa.VARCHAR(100), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("company", sa.VARCHAR(255), nullable=False),
        sa.Column("location", sa.VARCHAR(255), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    # Constraints
    op.create_unique_constraint("uq_job_postings_url", "job_postings", ["url"])

    # Indexes
    op.create_index("ix_job_postings_scraped_at", "job_postings", ["scraped_at"])
    op.create_index("ix_job_postings_role_category", "job_postings", ["role_category"])
    op.create_index("ix_job_postings_is_processed", "job_postings", ["is_processed"])
    op.create_index(
        "ix_job_postings_unprocessed",
        "job_postings",
        ["scraped_at"],
        postgresql_where=sa.text("is_processed = false"),
    )

    # ── processed_postings ────────────────────────────────────────────────────
    op.create_table(
        "processed_postings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "posting_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_postings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "skills_extracted",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("sentiment_score", sa.Float, nullable=False),
        sa.Column(
            "topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_processed_postings_posting_id", "processed_postings", ["posting_id"]
    )
    op.create_index(
        "ix_processed_postings_processed_at", "processed_postings", ["processed_at"]
    )

    # ── skill_trends ──────────────────────────────────────────────────────────
    op.create_table(
        "skill_trends",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("skill", sa.VARCHAR(100), nullable=False),
        sa.Column("role_category", sa.VARCHAR(100), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("mention_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "pct_of_postings", sa.Float, nullable=False, server_default=sa.text("0.0")
        ),
    )

    op.create_unique_constraint(
        "uq_skill_trend_week",
        "skill_trends",
        ["skill", "role_category", "week_start"],
    )
    op.create_index(
        "ix_skill_trends_skill_week_start", "skill_trends", ["skill", "week_start"]
    )
    op.create_index("ix_skill_trends_role_category", "skill_trends", ["role_category"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("skill_trends")
    op.drop_table("processed_postings")
    op.drop_table("job_postings")
