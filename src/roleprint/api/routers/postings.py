"""Recent postings endpoint."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api.deps import get_session
from roleprint.api.schemas import PostingItem
from roleprint.db.models import JobPosting, ProcessedPosting

router = APIRouter(prefix="/api/postings", tags=["postings"])


@router.get("/recent", response_model=List[PostingItem])
def get_recent_postings(
    role_category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Return the most recently scraped postings with NLP enrichment fields.

    Includes ``skills``, ``sentiment_score``, ``topics``, and ``entities``
    when a ProcessedPosting record exists for the job.  Results are ordered
    newest-first.  Not cached — callers should apply their own limit.
    """
    stmt = (
        select(
            JobPosting.id,
            JobPosting.title,
            JobPosting.company,
            JobPosting.location,
            JobPosting.url,
            JobPosting.source,
            JobPosting.role_category,
            JobPosting.scraped_at,
            JobPosting.posted_at,
            ProcessedPosting.skills_extracted,
            ProcessedPosting.sentiment_score,
            ProcessedPosting.topics,
            ProcessedPosting.entities,
        )
        .outerjoin(ProcessedPosting, JobPosting.id == ProcessedPosting.posting_id)
        .order_by(JobPosting.scraped_at.desc())
    )
    if role_category:
        stmt = stmt.where(JobPosting.role_category == role_category)
    stmt = stmt.limit(limit)

    rows = list(session.execute(stmt))

    result = []
    for row in rows:
        result.append({
            "id": str(row.id),
            "title": row.title or "",
            "company": row.company or "",
            "location": row.location or "",
            "url": row.url or "",
            "source": row.source or "",
            "role_category": row.role_category or "",
            "scraped_at": str(row.scraped_at),
            "posted_at": str(row.posted_at) if row.posted_at else None,
            "skills": row.skills_extracted or [],
            "sentiment_score": float(row.sentiment_score) if row.sentiment_score is not None else None,
            "topics": row.topics or {},
            "entities": row.entities or {},
        })

    return result
