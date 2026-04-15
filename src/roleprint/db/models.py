"""SQLAlchemy ORM models for Roleprint."""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from roleprint.db.base import Base


class JobPosting(Base):
    """Raw job postings as scraped from source boards."""

    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    role_category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationship
    processed: Mapped[Optional["ProcessedPosting"]] = relationship(
        back_populates="posting", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("url", name="uq_job_postings_url"),
        Index("ix_job_postings_scraped_at", "scraped_at"),
        Index("ix_job_postings_role_category", "role_category"),
        Index("ix_job_postings_is_processed", "is_processed"),
        # Partial index — only unprocessed rows (keeps index small)
        Index(
            "ix_job_postings_unprocessed",
            "scraped_at",
            postgresql_where="is_processed = false",
        ),
    )

    def __repr__(self) -> str:
        return f"<JobPosting id={self.id} title={self.title!r} source={self.source!r}>"


class ProcessedPosting(Base):
    """NLP-derived features for a job posting."""

    __tablename__ = "processed_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    skills_extracted: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    topics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    entities: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    posting: Mapped["JobPosting"] = relationship(back_populates="processed")

    __table_args__ = (
        Index("ix_processed_postings_posting_id", "posting_id"),
        Index("ix_processed_postings_processed_at", "processed_at"),
    )

    def __repr__(self) -> str:
        return f"<ProcessedPosting id={self.id} posting_id={self.posting_id}>"


class Subscriber(Base):
    """Email subscribers for the weekly digest."""

    __tablename__ = "subscribers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_preferences: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Opaque token for one-click unsubscribe links — stored as plain string
    unsubscribe_token: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: uuid.uuid4().hex
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_subscribers_email"),
        Index("ix_subscribers_unsubscribe_token", "unsubscribe_token"),
        Index("ix_subscribers_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Subscriber email={self.email!r} active={self.is_active}>"


class SkillTrend(Base):
    """Weekly aggregated skill mention counts per role category."""

    __tablename__ = "skill_trends"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    role_category: Mapped[str] = mapped_column(String(100), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pct_of_postings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        # Enforce one row per (skill, role, week) combination
        UniqueConstraint("skill", "role_category", "week_start", name="uq_skill_trend_week"),
        Index("ix_skill_trends_skill_week_start", "skill", "week_start"),
        Index("ix_skill_trends_role_category", "role_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillTrend skill={self.skill!r} role={self.role_category!r}"
            f" week={self.week_start}>"
        )
