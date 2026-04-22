"""Recent postings endpoint — paginated."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api.deps import get_session
from roleprint.api.schemas import PaginatedPostings
from roleprint.db.models import JobPosting, ProcessedPosting

router = APIRouter(prefix="/api/postings", tags=["postings"])


@router.get("/recent", response_model=PaginatedPostings)
def get_recent_postings(
    role_category: str | None = Query(None, description="Filter to one role category"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Rows per page (max 100)"),
    session: Session = Depends(get_session),
):
    """Return paginated job postings, newest-first, with NLP enrichment fields.

    Includes ``skills``, ``sentiment_score``, ``topics``, and ``entities``
    when a ProcessedPosting record exists.  Filtering and pagination compose:
    supply both ``role_category`` and ``page`` to page through a filtered set.

    An out-of-range ``page`` returns an empty ``data`` array (not an error).
    """
    # ── Base filter ───────────────────────────────────────────────────────────
    role = role_category.strip() if role_category else None

    count_stmt = select(sa_func.count(JobPosting.id))
    if role:
        count_stmt = count_stmt.where(JobPosting.role_category == role)
    total_count: int = session.scalar(count_stmt) or 0

    total_pages = max(1, -(-total_count // page_size))  # ceil division
    offset = (page - 1) * page_size

    # ── Data query ────────────────────────────────────────────────────────────
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
        .offset(offset)
        .limit(page_size)
    )
    if role:
        stmt = stmt.where(JobPosting.role_category == role)

    rows = list(session.execute(stmt))

    data = []
    for row in rows:
        data.append(
            {
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
                "sentiment_score": float(row.sentiment_score)
                if row.sentiment_score is not None
                else None,
                "topics": row.topics or {},
                "entities": row.entities or {},
            }
        )

    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
