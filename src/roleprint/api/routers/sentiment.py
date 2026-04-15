"""Sentiment timeline endpoint."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import SentimentWeek
from roleprint.db.models import JobPosting, ProcessedPosting
from roleprint.nlp.sentiment import count_urgency
from roleprint.nlp.pipeline import _week_start

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])

_CACHE_TTL = 300


@router.get("/timeline", response_model=List[SentimentWeek])
def get_sentiment_timeline(
    role_category: Optional[str] = Query(None),
    weeks: int = Query(8, ge=1, le=52),
    session: Session = Depends(get_session),
):
    """Return average sentiment and urgency score per week.

    Urgency is computed client-side by running the urgency-phrase counter
    on each posting's ``raw_text`` and summing per week.  Results are sorted
    chronologically (oldest first).
    Cached 5 minutes.
    """
    key = f"rp:sentiment:{role_category}:{weeks}"
    if (hit := cache.get(key)) is not None:
        return hit

    # Find the most recent week
    from sqlalchemy import func as sa_func
    from roleprint.db.models import SkillTrend

    latest_scraped = session.scalar(
        select(sa_func.max(JobPosting.scraped_at))
    )
    if not latest_scraped:
        return []

    cutoff = latest_scraped - timedelta(weeks=weeks)

    stmt = (
        select(
            JobPosting.scraped_at,
            JobPosting.raw_text,
            ProcessedPosting.sentiment_score,
        )
        .join(ProcessedPosting, JobPosting.id == ProcessedPosting.posting_id)
        .where(JobPosting.scraped_at >= cutoff)
    )
    if role_category:
        stmt = stmt.where(JobPosting.role_category == role_category)

    rows = list(session.execute(stmt))

    # Aggregate per week (Python-side for DB portability)
    weekly: dict = defaultdict(lambda: {"scores": [], "urgency": 0, "count": 0})

    for scraped_at, raw_text, sentiment_score in rows:
        week = str(_week_start(scraped_at))
        weekly[week]["scores"].append(float(sentiment_score))
        weekly[week]["urgency"] += count_urgency(raw_text or "")
        weekly[week]["count"] += 1

    result = []
    for week in sorted(weekly.keys()):
        data = weekly[week]
        avg = sum(data["scores"]) / len(data["scores"])
        result.append({
            "week": week,
            "avg_sentiment": round(avg, 4),
            "urgency_score": data["urgency"],
            "posting_count": data["count"],
        })

    cache.set(key, result, ttl=_CACHE_TTL)
    return result
