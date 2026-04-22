"""Roles endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import RoleItem
from roleprint.db.models import JobPosting, ProcessedPosting

router = APIRouter(prefix="/api/roles", tags=["roles"])

_CACHE_TTL = 300


@router.get("", response_model=list[RoleItem])
def get_roles(session: Session = Depends(get_session)):
    """Return all tracked role categories with posting and processing counts.

    Sorted by posting_count descending.  Cached 5 minutes.
    """
    key = "rp:roles"
    if (hit := cache.get(key)) is not None:
        return hit

    # Total postings per role
    total_stmt = select(
        JobPosting.role_category, sa_func.count(JobPosting.id).label("total")
    ).group_by(JobPosting.role_category)
    total_rows = {row.role_category: row.total for row in session.execute(total_stmt)}

    # Processed postings per role (via join)
    processed_stmt = (
        select(JobPosting.role_category, sa_func.count(ProcessedPosting.id).label("processed"))
        .join(ProcessedPosting, JobPosting.id == ProcessedPosting.posting_id)
        .group_by(JobPosting.role_category)
    )
    processed_rows = {row.role_category: row.processed for row in session.execute(processed_stmt)}

    result = []
    for role, total in sorted(total_rows.items(), key=lambda x: -x[1]):
        processed = processed_rows.get(role, 0)
        result.append(
            {
                "role_category": role,
                "posting_count": total,
                "processed_count": processed,
                "unprocessed_count": total - processed,
            }
        )

    cache.set(key, result, ttl=_CACHE_TTL)
    return result
