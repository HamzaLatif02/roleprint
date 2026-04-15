"""Typed query helpers for the five most common Roleprint reads.

All functions accept a SQLAlchemy ``Session`` and return typed results.
They are intentionally free of FastAPI coupling so they can be used
from the scheduler, scripts, and tests alike.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from roleprint.db.models import JobPosting, SkillTrend


# ── 1. Unprocessed postings ───────────────────────────────────────────────────

def get_unprocessed_postings(
    session: Session,
    *,
    limit: int = 100,
    role_category: Optional[str] = None,
) -> List[JobPosting]:
    """Return job postings that have not yet been through the NLP pipeline.

    Args:
        session: Active database session.
        limit: Maximum rows to fetch (avoids runaway memory use).
        role_category: Optional filter — only return postings in this category.
    """
    stmt = (
        select(JobPosting)
        .where(JobPosting.is_processed.is_(False))
        .order_by(JobPosting.scraped_at.asc())
        .limit(limit)
    )
    if role_category is not None:
        stmt = stmt.where(JobPosting.role_category == role_category)
    return list(session.scalars(stmt))


# ── 2. Skill trends by role category ─────────────────────────────────────────

def get_skill_trends_by_role(
    session: Session,
    role_category: str,
    *,
    since: Optional[date] = None,
    top_n: int = 20,
) -> List[SkillTrend]:
    """Return weekly skill trend rows for a role category, ordered by mention count.

    Args:
        session: Active database session.
        role_category: The role to filter by (e.g. "data analyst").
        since: Optional lower bound on ``week_start`` (inclusive).
        top_n: Cap on number of distinct skill rows returned per query.
    """
    stmt = (
        select(SkillTrend)
        .where(SkillTrend.role_category == role_category)
        .order_by(SkillTrend.week_start.desc(), SkillTrend.mention_count.desc())
        .limit(top_n)
    )
    if since is not None:
        stmt = stmt.where(SkillTrend.week_start >= since)
    return list(session.scalars(stmt))


# ── 3. Single posting with its NLP result ────────────────────────────────────

def get_posting_with_analysis(
    session: Session,
    posting_id: UUID,
) -> Optional[JobPosting]:
    """Fetch a job posting eagerly joined with its processed analysis.

    Returns ``None`` if the posting does not exist.
    """
    stmt = (
        select(JobPosting)
        .where(JobPosting.id == posting_id)
        .options(selectinload(JobPosting.processed))
    )
    return session.scalars(stmt).first()


# ── 4. Recent postings for a role category ────────────────────────────────────

def get_recent_postings_by_role(
    session: Session,
    role_category: str,
    *,
    limit: int = 50,
    include_analysis: bool = False,
) -> List[JobPosting]:
    """Return the most recently scraped postings for a given role category.

    Args:
        session: Active database session.
        role_category: Target role category string.
        limit: Maximum rows to return.
        include_analysis: If ``True``, eagerly load the related
            ``ProcessedPosting`` to avoid N+1 queries downstream.
    """
    stmt = (
        select(JobPosting)
        .where(JobPosting.role_category == role_category)
        .order_by(JobPosting.scraped_at.desc())
        .limit(limit)
    )
    if include_analysis:
        stmt = stmt.options(selectinload(JobPosting.processed))
    return list(session.scalars(stmt))


# ── 5. Top skills across all roles for a date range ──────────────────────────

def get_top_skills_overall(
    session: Session,
    *,
    since: date,
    until: Optional[date] = None,
    top_n: int = 25,
) -> List[SkillTrend]:
    """Return the highest-mentioned skills across *all* role categories in a window.

    Aggregation is left to the caller if cross-role rollup is needed;
    this returns raw ``SkillTrend`` rows ordered by descending mention count.

    Args:
        session: Active database session.
        since: Start of the date window (inclusive).
        until: End of the date window (inclusive). Defaults to today.
        top_n: Number of rows to return.
    """
    stmt = (
        select(SkillTrend)
        .where(SkillTrend.week_start >= since)
        .order_by(SkillTrend.mention_count.desc())
        .limit(top_n)
    )
    if until is not None:
        stmt = stmt.where(SkillTrend.week_start <= until)
    return list(session.scalars(stmt))
