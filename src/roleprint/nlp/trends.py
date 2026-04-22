"""Trend analysis functions over the skill_trends and processed_postings tables.

All public functions accept an injected SQLAlchemy ``Session`` so they can be
called from the API, the scheduler, tests, or the report script without
coupling to a specific session factory.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend

log = structlog.get_logger(__name__)

# Thresholds
_RISING_THRESHOLD_PCT = 20.0  # week-over-week growth to be "rising"
_EMERGING_MAX_OLD_PCT = 0.02  # max pct_of_postings in the old week
_EMERGING_MIN_CURRENT = 3  # minimum current mention_count


# ─────────────────────────────────────────────────────────────────────────────
# 1. Week-over-week change
# ─────────────────────────────────────────────────────────────────────────────


def week_over_week_change(
    skill: str,
    role_category: str,
    session: Session,
) -> dict[str, Any]:
    """Compute the percentage change in mentions vs the prior week.

    Compares the two most recent ``week_start`` entries for *(skill,
    role_category)* in ``skill_trends``.

    Args:
        skill:         Canonical skill name (e.g. ``"Python"``).
        role_category: Role category string (e.g. ``"data analyst"``).
        session:       Active database session.

    Returns:
        Dict with keys:
        - ``change_pct``      – float, positive = growth.
        - ``is_rising``       – True when ``change_pct > 20 %``.
        - ``current_count``   – mention count this week.
        - ``previous_count``  – mention count last week.
        - ``current_week``    – ``date`` of the current week_start.
        - ``previous_week``   – ``date`` of the prior week_start, or ``None``.
    """
    rows = list(
        session.scalars(
            select(SkillTrend)
            .where(
                SkillTrend.skill == skill,
                SkillTrend.role_category == role_category,
            )
            .order_by(SkillTrend.week_start.desc())
            .limit(2)
        )
    )

    if not rows:
        return {
            "change_pct": 0.0,
            "is_rising": False,
            "current_count": 0,
            "previous_count": 0,
            "current_week": None,
            "previous_week": None,
        }

    current_row = rows[0]
    previous_row = rows[1] if len(rows) == 2 else None

    current_count = current_row.mention_count
    previous_count = previous_row.mention_count if previous_row else 0

    if previous_count == 0:
        change_pct = 100.0 if current_count > 0 else 0.0
    else:
        change_pct = (current_count - previous_count) / previous_count * 100.0

    return {
        "change_pct": round(change_pct, 1),
        "is_rising": change_pct > _RISING_THRESHOLD_PCT,
        "current_count": current_count,
        "previous_count": previous_count,
        "current_week": current_row.week_start,
        "previous_week": previous_row.week_start if previous_row else None,
    }


def rising_skills(
    role_category: str,
    session: Session,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Return the top-N rising skills for a role category.

    Wraps ``week_over_week_change`` across all skills seen this week for
    the given role.

    Returns:
        List of change dicts (same shape as ``week_over_week_change``),
        enriched with a ``"skill"`` key, sorted by ``change_pct`` desc.
    """
    # Find distinct skills that have data in the two most recent weeks
    latest_weeks = list(
        session.scalars(
            select(SkillTrend.week_start)
            .where(SkillTrend.role_category == role_category)
            .distinct()
            .order_by(SkillTrend.week_start.desc())
            .limit(2)
        )
    )

    if not latest_weeks:
        return []

    current_week = latest_weeks[0]
    skills_this_week = list(
        session.scalars(
            select(SkillTrend.skill).where(
                SkillTrend.role_category == role_category,
                SkillTrend.week_start == current_week,
            )
        )
    )

    results = []
    for skill in skills_this_week:
        change = week_over_week_change(skill, role_category, session)
        change["skill"] = skill
        results.append(change)

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Skill co-occurrence
# ─────────────────────────────────────────────────────────────────────────────


def skill_cooccurrence(
    role_category: str,
    session: Session,
    top_n: int = 20,
    min_count: int = 2,
) -> dict[str, Any]:
    """Compute a skill co-occurrence matrix for a role category.

    Uses ``processed_postings.skills_extracted`` (one row per posting) to
    build a document-by-skill incidence matrix, then multiplies it by its
    transpose via ``scipy.sparse`` to get the symmetric co-occurrence matrix.

    Args:
        role_category: Target role category.
        session:       Active database session.
        top_n:         Maximum number of skill pairs to return.
        min_count:     Minimum co-occurrence count to include a pair.

    Returns:
        Dict with keys:
        - ``"skills"``    – sorted list of all skill names in the corpus.
        - ``"top_pairs"`` – list of ``{skill_a, skill_b, count}`` dicts,
                            sorted by count descending.
        - ``"matrix"``    – full NxN co-occurrence matrix as a nested list
                            (useful for heatmap visualisations).
    """
    from scipy.sparse import csr_matrix, lil_matrix  # type: ignore[import]

    # Fetch skill lists from all processed postings for this role
    skill_lists: list[list[str]] = list(
        session.scalars(
            select(ProcessedPosting.skills_extracted)
            .join(JobPosting, ProcessedPosting.posting_id == JobPosting.id)
            .where(JobPosting.role_category == role_category)
        )
    )

    if not skill_lists:
        return {"skills": [], "top_pairs": [], "matrix": []}

    # Build vocabulary
    all_skills: list[str] = sorted({s for lst in skill_lists for s in lst})
    if not all_skills:
        return {"skills": [], "top_pairs": [], "matrix": []}

    n_docs = len(skill_lists)
    n_skills = len(all_skills)
    skill_to_idx: dict[str, int] = {s: i for i, s in enumerate(all_skills)}

    # Build binary incidence matrix  (n_docs × n_skills)
    incidence = lil_matrix((n_docs, n_skills), dtype=np.float32)
    for doc_idx, skills in enumerate(skill_lists):
        for skill in skills:
            if skill in skill_to_idx:
                incidence[doc_idx, skill_to_idx[skill]] = 1.0

    incidence_csr: Any = csr_matrix(incidence)

    # Co-occurrence matrix  (n_skills × n_skills)
    cooc: np.ndarray = (incidence_csr.T @ incidence_csr).toarray()

    # Extract upper-triangle pairs (exclude self-co-occurrence on diagonal)
    pairs: list[dict[str, Any]] = []
    for i in range(n_skills):
        for j in range(i + 1, n_skills):
            count = int(cooc[i, j])
            if count >= min_count:
                pairs.append(
                    {
                        "skill_a": all_skills[i],
                        "skill_b": all_skills[j],
                        "count": count,
                    }
                )

    pairs.sort(key=lambda x: x["count"], reverse=True)

    log.debug(
        "trends.cooccurrence_computed",
        role=role_category,
        n_docs=n_docs,
        n_skills=n_skills,
        n_pairs=len(pairs),
    )

    return {
        "skills": all_skills,
        "top_pairs": pairs[:top_n],
        "matrix": cooc.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Role similarity
# ─────────────────────────────────────────────────────────────────────────────


def role_similarity(
    role_a: str,
    role_b: str,
    session: Session,
) -> float:
    """Cosine similarity of the skill-frequency vectors of two role categories.

    Vectors are built from ``pct_of_postings`` in ``skill_trends`` (aggregated
    across all weeks), so a skill present in 80 % of a role's postings gets
    a much higher weight than one seen in 5 %.

    Args:
        role_a: First role category string.
        role_b: Second role category string.
        session: Active database session.

    Returns:
        Float in [0, 1] — 1.0 = identical skill profiles, 0.0 = no overlap.
    """

    def _skill_vector(role: str) -> dict[str, float]:
        rows = list(session.scalars(select(SkillTrend).where(SkillTrend.role_category == role)))
        if not rows:
            return {}
        # Average pct_of_postings per skill (in case of multiple weeks)
        totals: dict[str, list] = defaultdict(list)
        for r in rows:
            totals[r.skill].append(r.pct_of_postings)
        return {skill: float(np.mean(pcts)) for skill, pcts in totals.items()}

    vec_a = _skill_vector(role_a)
    vec_b = _skill_vector(role_b)

    if not vec_a or not vec_b:
        return 0.0

    all_skills = sorted(set(vec_a) | set(vec_b))
    a = np.array([vec_a.get(s, 0.0) for s in all_skills], dtype=np.float64)
    b = np.array([vec_b.get(s, 0.0) for s in all_skills], dtype=np.float64)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = float(np.dot(a, b) / (norm_a * norm_b))
    return round(min(max(similarity, 0.0), 1.0), 4)


def role_similarity_matrix(
    roles: list[str],
    session: Session,
) -> dict[str, Any]:
    """Compute pairwise cosine similarities across a list of role categories.

    Args:
        roles:   List of role category strings.
        session: Active database session.

    Returns:
        Dict with:
        - ``"roles"``  – the input roles list.
        - ``"matrix"`` – NxN list-of-lists, ``matrix[i][j]`` is the similarity
                         between ``roles[i]`` and ``roles[j]``.
    """
    n = len(roles)
    matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            sim = role_similarity(roles[i], roles[j], session)
            matrix[i][j] = sim
            matrix[j][i] = sim  # symmetric

    return {"roles": roles, "matrix": matrix}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Emerging skills
# ─────────────────────────────────────────────────────────────────────────────


def emerging_skills(
    session: Session,
    lookback_weeks: int = 4,
    min_current_count: int = _EMERGING_MIN_CURRENT,
    max_old_pct: float = _EMERGING_MAX_OLD_PCT,
) -> list[dict[str, Any]]:
    """Find skills with near-zero presence N weeks ago that are growing now.

    Algorithm:
    1. Identify the most recent ``week_start`` in ``skill_trends`` as "current".
    2. Compute the "old" reference week as ``current - lookback_weeks * 7 days``.
    3. For every (skill, role_category) in the current week:
       - Skip if ``mention_count < min_current_count`` (noise filter).
       - Skip if ``old_pct_of_postings > max_old_pct`` (already established).
       - Compute ``growth_pct = (current_count - old_count) / max(old_count, 1) * 100``.
    4. Return results sorted by ``growth_pct`` descending.

    Args:
        session:           Active database session.
        lookback_weeks:    How far back to look (default 4 weeks).
        min_current_count: Minimum current ``mention_count`` (noise floor).
        max_old_pct:       Maximum ``pct_of_postings`` in the old week for a
                           skill to be considered "emerging" (default 2 %).

    Returns:
        List of dicts, each with:
        ``skill``, ``role_category``, ``growth_pct``, ``current_count``,
        ``old_count``, ``current_week``.
    """
    # Determine the current week (latest in the table)
    latest_week: date | None = session.scalar(
        select(SkillTrend.week_start).order_by(SkillTrend.week_start.desc()).limit(1)
    )
    if latest_week is None:
        return []

    lookback_start = latest_week - timedelta(weeks=lookback_weeks)

    # Fetch current-week rows
    current_rows = list(
        session.scalars(select(SkillTrend).where(SkillTrend.week_start == latest_week))
    )

    # For each (skill, role), find the MAX pct and the row at exactly lookback_start
    # across the whole lookback window (exclusive of current week).
    # Using max_pct avoids false positives when a skill has no row at the exact
    # lookback date but was well-established in intermediate weeks.
    from sqlalchemy import func as sa_func

    historical_rows = session.execute(
        select(
            SkillTrend.skill,
            SkillTrend.role_category,
            sa_func.max(SkillTrend.pct_of_postings).label("max_pct"),
        )
        .where(
            SkillTrend.week_start >= lookback_start,
            SkillTrend.week_start < latest_week,
        )
        .group_by(SkillTrend.skill, SkillTrend.role_category)
    ).all()

    historical_index: dict[tuple[str, str], float] = {
        (r.skill, r.role_category): r.max_pct for r in historical_rows
    }

    # Also fetch the exact lookback_start row to use its count for growth calculation
    old_count_rows = list(
        session.scalars(select(SkillTrend).where(SkillTrend.week_start == lookback_start))
    )
    old_count_index: dict[tuple[str, str], int] = {
        (r.skill, r.role_category): r.mention_count for r in old_count_rows
    }

    emerging: list[dict[str, Any]] = []

    for row in current_rows:
        if row.mention_count < min_current_count:
            continue

        key = (row.skill, row.role_category)
        # Use the worst-case (max) historical pct to avoid false positives
        old_pct = historical_index.get(key, 0.0)
        old_count = old_count_index.get(key, 0)

        if old_pct > max_old_pct:
            continue  # already well-established within the lookback window

        if old_count == 0:
            growth_pct = 100.0
        else:
            growth_pct = (row.mention_count - old_count) / old_count * 100.0

        emerging.append(
            {
                "skill": row.skill,
                "role_category": row.role_category,
                "growth_pct": round(growth_pct, 1),
                "current_count": row.mention_count,
                "old_count": old_count,
                "current_week": str(row.week_start),
            }
        )

    emerging.sort(key=lambda x: x["growth_pct"], reverse=True)

    log.debug(
        "trends.emerging_skills_found",
        current_week=str(latest_week),
        lookback_start=str(lookback_start),
        count=len(emerging),
    )
    return emerging
