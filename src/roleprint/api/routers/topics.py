"""Topic model endpoint."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import TopicItem
from roleprint.db.models import JobPosting, ProcessedPosting

router = APIRouter(prefix="/api/topics", tags=["topics"])

_CACHE_TTL = 300


@router.get("", response_model=list[TopicItem])
def get_topics(
    role_category: str | None = Query(None),
    session: Session = Depends(get_session),
):
    """Return topic model results aggregated across all processed postings.

    Grouped by ``topic_label``; postings without topic data (topics={}) are
    excluded. If no topics exist, returns an empty list.
    Cached 5 minutes.
    """
    key = f"rp:topics:{role_category}"
    if (hit := cache.get(key)) is not None:
        return hit

    stmt = select(ProcessedPosting.topics).join(
        JobPosting, ProcessedPosting.posting_id == JobPosting.id
    )
    if role_category:
        stmt = stmt.where(JobPosting.role_category == role_category)

    rows = list(session.scalars(stmt))

    # Aggregate: topic_label → {count, probabilities}
    agg: dict = defaultdict(lambda: {"count": 0, "probs": [], "topic_id": -1})

    for topics_dict in rows:
        if not topics_dict or "topic_label" not in topics_dict:
            continue
        label = topics_dict["topic_label"]
        agg[label]["count"] += 1
        agg[label]["topic_id"] = topics_dict.get("topic_id", -1)
        if prob := topics_dict.get("probability"):
            agg[label]["probs"].append(float(prob))

    result = []
    for label, data in sorted(agg.items(), key=lambda x: -x[1]["count"]):
        avg_prob = sum(data["probs"]) / len(data["probs"]) if data["probs"] else 0.0
        result.append(
            {
                "topic_id": data["topic_id"],
                "topic_label": label,
                "posting_count": data["count"],
                "avg_probability": round(avg_prob, 3),
            }
        )

    cache.set(key, result, ttl=_CACHE_TTL)
    return result
