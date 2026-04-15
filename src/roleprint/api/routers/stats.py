"""Stats summary endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func as sa_func, select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import StatsSummary
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend

router = APIRouter(prefix="/api/stats", tags=["stats"])

_CACHE_TTL = 300


@router.get("/summary", response_model=StatsSummary)
def get_stats_summary(session: Session = Depends(get_session)):
    """Return high-level dataset statistics.

    Counts total/processed/unprocessed postings, distinct role categories,
    weeks of trend data, and the list of scrape sources.
    Cached 5 minutes.
    """
    key = "rp:stats:summary"
    if (hit := cache.get(key)) is not None:
        return hit

    total = session.scalar(select(sa_func.count(JobPosting.id))) or 0
    processed = session.scalar(select(sa_func.count(ProcessedPosting.id))) or 0

    last_updated = session.scalar(
        select(sa_func.max(JobPosting.scraped_at))
    )

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
