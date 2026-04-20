"""Stats summary endpoint."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func as sa_func, select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import StatsSummary
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend

router = APIRouter(prefix="/api/stats", tags=["stats"])

_CACHE_TTL = 300


@router.get("/summary", response_model=StatsSummary)
def get_stats_summary(
    role_category: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Return high-level dataset statistics.

    When ``role_category`` is provided, all counts are filtered to that role:
    - total_postings / processed_postings: only postings for that role
    - roles_tracked: returns 1
    - weeks_of_data: distinct weeks in skill_trends for that role
    - last_updated: most recent scraped_at for that role

    Without ``role_category`` (or empty string), returns global stats.
    Cached 5 minutes per unique role_category value.
    """
    role = role_category.strip() if role_category else None
    key = f"rp:stats:summary:{role or 'all'}"
    if (hit := cache.get(key)) is not None:
        return hit

    if role:
        # ── Filtered stats ────────────────────────────────────────────────
        total = session.scalar(
            select(sa_func.count(JobPosting.id))
            .where(JobPosting.role_category == role)
        ) or 0

        processed = session.scalar(
            select(sa_func.count(ProcessedPosting.id))
            .join(JobPosting, JobPosting.id == ProcessedPosting.posting_id)
            .where(JobPosting.role_category == role)
        ) or 0

        last_updated = session.scalar(
            select(sa_func.max(JobPosting.scraped_at))
            .where(JobPosting.role_category == role)
        )

        weeks_of_data = session.scalar(
            select(sa_func.count(distinct(SkillTrend.week_start)))
            .where(SkillTrend.role_category == role)
        ) or 0

        source_rows = list(session.scalars(
            select(distinct(JobPosting.source))
            .where(JobPosting.role_category == role, JobPosting.source.isnot(None))
        ))

        result = {
            "total_postings": total,
            "processed_postings": processed,
            "unprocessed_postings": total - processed,
            "last_updated": str(last_updated) if last_updated else None,
            "roles_tracked": 1,
            "weeks_of_data": weeks_of_data,
            "sources": sorted(source_rows),
        }
    else:
        # ── Global stats ──────────────────────────────────────────────────
        total = session.scalar(select(sa_func.count(JobPosting.id))) or 0
        processed = session.scalar(select(sa_func.count(ProcessedPosting.id))) or 0

        last_updated = session.scalar(select(sa_func.max(JobPosting.scraped_at)))

        roles_tracked = session.scalar(
            select(sa_func.count(distinct(JobPosting.role_category)))
        ) or 0

        weeks_of_data = session.scalar(
            select(sa_func.count(distinct(SkillTrend.week_start)))
        ) or 0

        source_rows = list(session.scalars(
            select(distinct(JobPosting.source)).where(JobPosting.source.isnot(None))
        ))

        result = {
            "total_postings": total,
            "processed_postings": processed,
            "unprocessed_postings": total - processed,
            "last_updated": str(last_updated) if last_updated else None,
            "roles_tracked": roles_tracked,
            "weeks_of_data": weeks_of_data,
            "sources": sorted(source_rows),
        }

    cache.set(key, result, ttl=_CACHE_TTL)
    return result
