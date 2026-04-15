"""Skill-related endpoints."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.schemas import EmergingSkillItem, RoleSkillProfile, SkillCompareResponse, SkillTrendItem
from roleprint.db.models import SkillTrend
from roleprint.nlp.trends import emerging_skills, role_similarity

router = APIRouter(prefix="/api/skills", tags=["skills"])

_CACHE_TTL = 300  # 5 minutes


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_latest_week(session: Session):
    return session.scalar(
        select(SkillTrend.week_start).order_by(SkillTrend.week_start.desc()).limit(1)
    )


def _build_trending(
    session: Session,
    role_category: Optional[str],
    weeks: int,
) -> List[dict]:
    latest = _get_latest_week(session)
    if not latest:
        return []

    cutoff = latest - timedelta(weeks=max(weeks - 1, 0))
    prev_week = latest - timedelta(weeks=1)

    # Current-week rows
    stmt = (
        select(SkillTrend)
        .where(SkillTrend.week_start == latest)
        .order_by(SkillTrend.mention_count.desc())
    )
    if role_category:
        stmt = stmt.where(SkillTrend.role_category == role_category)
    current_rows = list(session.scalars(stmt))

    # Previous-week index for WoW calculation
    prev_stmt = select(SkillTrend).where(SkillTrend.week_start == prev_week)
    if role_category:
        prev_stmt = prev_stmt.where(SkillTrend.role_category == role_category)
    prev_index = {
        (r.skill, r.role_category): r.mention_count
        for r in session.scalars(prev_stmt)
    }

    results = []
    for row in current_rows:
        prev_count = prev_index.get((row.skill, row.role_category), 0)
        if prev_count == 0:
            wow = 100.0 if row.mention_count > 0 else 0.0
        else:
            wow = (row.mention_count - prev_count) / prev_count * 100.0

        results.append({
            "skill": row.skill,
            "role_category": row.role_category,
            "mention_count": row.mention_count,
            "pct_of_postings": row.pct_of_postings,
            "wow_change": round(wow, 1),
            "is_rising": wow > 20.0,
        })
    return results


def _get_skill_vector(session: Session, role: str) -> dict:
    """skill → max pct_of_postings across all weeks."""
    from collections import defaultdict
    import numpy as np

    rows = list(session.scalars(
        select(SkillTrend).where(SkillTrend.role_category == role)
    ))
    acc: dict = defaultdict(list)
    for r in rows:
        acc[r.skill].append(r.pct_of_postings)
    return {skill: float(max(pcts)) for skill, pcts in acc.items()}


# ── GET /api/skills/trending ─────────────────────────────────────────────────

@router.get("/trending", response_model=List[SkillTrendItem])
def get_trending(
    role_category: Optional[str] = Query(None, description="Filter to one role category"),
    weeks: int = Query(4, ge=1, le=52, description="How many recent weeks to consider"),
    session: Session = Depends(get_session),
):
    """Return current-week skill counts with week-over-week change.

    Results are sorted by ``mention_count`` descending.
    Cached in Redis for 5 minutes per (role_category, weeks) combination.
    """
    key = f"rp:trending:{role_category}:{weeks}"
    if (hit := cache.get(key)) is not None:
        return hit
    result = _build_trending(session, role_category, weeks)
    cache.set(key, result, ttl=_CACHE_TTL)
    return result


# ── GET /api/skills/compare ──────────────────────────────────────────────────

@router.get("/compare", response_model=SkillCompareResponse)
def compare_roles(
    roles: str = Query(
        ...,
        description="Comma-separated role categories, e.g. 'data+analyst,data+scientist'",
    ),
    session: Session = Depends(get_session),
):
    """Compare skill profiles between 2+ role categories.

    Returns Jaccard overlap %, cosine similarity, shared skills, and the
    top/unique skills per role.
    """
    role_list = [r.strip() for r in roles.split(",") if r.strip()]
    if len(role_list) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Provide at least 2 roles separated by comma")

    key = f"rp:compare:{':'.join(sorted(role_list))}"
    if (hit := cache.get(key)) is not None:
        return hit

    # Build skill vectors for each role
    vectors = {role: _get_skill_vector(session, role) for role in role_list}
    skill_sets = {role: set(v.keys()) for role, v in vectors.items()}

    # Jaccard overlap across all roles
    union_skills: set = set().union(*skill_sets.values())
    intersection: set = skill_sets[role_list[0]]
    for r in role_list[1:]:
        intersection = intersection & skill_sets[r]

    overlap_pct = round(len(intersection) / len(union_skills) * 100, 1) if union_skills else 0.0

    # Cosine similarity (pair of first two roles if >2)
    sim = role_similarity(role_list[0], role_list[1], session) if len(role_list) >= 2 else 1.0

    # Per-role profiles
    profiles: dict = {}
    for role in role_list:
        other_skills: set = set().union(*(skill_sets[r] for r in role_list if r != role))
        unique = sorted(
            [s for s in skill_sets[role] if s not in other_skills],
            key=lambda s: -vectors[role][s],
        )[:10]
        top = sorted(vectors[role], key=lambda s: -vectors[role][s])[:10]
        profiles[role] = {"top_skills": top, "unique_skills": unique}

    result = {
        "roles": role_list,
        "overlap_pct": overlap_pct,
        "similarity_score": sim,
        "shared_skills": sorted(intersection, key=lambda s: -max(vectors[r].get(s, 0) for r in role_list)),
        "role_profiles": profiles,
    }
    cache.set(key, result, ttl=_CACHE_TTL)
    return result


# ── GET /api/skills/emerging ─────────────────────────────────────────────────

@router.get("/emerging", response_model=List[EmergingSkillItem])
def get_emerging(
    lookback_weeks: int = Query(4, ge=1, le=26),
    session: Session = Depends(get_session),
):
    """Return skills with the fastest growth vs N weeks ago.

    Filters out well-established skills (pct > 2 % in the lookback window)
    so only genuinely new entrants appear.
    Cached in Redis for 5 minutes.
    """
    key = f"rp:emerging:{lookback_weeks}"
    if (hit := cache.get(key)) is not None:
        return hit
    result = emerging_skills(session, lookback_weeks=lookback_weeks)
    cache.set(key, result, ttl=_CACHE_TTL)
    return result
