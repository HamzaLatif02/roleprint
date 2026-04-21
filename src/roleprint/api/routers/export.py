"""CSV export endpoints for skill trends and gap analysis."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.api.deps import get_session
from roleprint.db.models import SkillTrend

router = APIRouter(prefix="/api/export", tags=["export"])

_COLUMNS_TRENDING = ["skill", "role_category", "week_start", "mention_count", "pct_of_postings", "wow_change"]
_COLUMNS_GAP = ["skill", "status", "demand_pct", "role_category"]


def _today() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _csv_response(rows: list[list], columns: list[str], filename: str) -> StreamingResponse:
    """Build a StreamingResponse that emits CSV rows one at a time."""

    def _generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue()
        for row in rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(row)
            yield buf.getvalue()

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /api/export/skills/trending ──────────────────────────────────────────

@router.get(
    "/skills/trending",
    summary="Export trending skills as CSV",
    response_description="CSV file with columns: skill, role_category, week_start, mention_count, pct_of_postings, wow_change",
)
def export_trending(
    role_category: Optional[str] = Query(None, description="Filter to one role category; omit for all roles"),
    weeks: int = Query(4, ge=1, le=52, description="Number of recent weeks to include"),
    session: Session = Depends(get_session),
):
    """Download the trending-skills dataset as a CSV file.

    Mirrors the data shown on the Overview and Trends pages.  Each row
    represents a skill for the most recent complete data week, with a
    week-over-week percentage change column.

    If no data exists the file contains only the header row.
    """
    role = role_category.strip() if role_category else None
    filename = f"roleprint_trending_{_today()}.csv"

    # Latest week
    latest = session.scalar(
        select(SkillTrend.week_start).order_by(SkillTrend.week_start.desc()).limit(1)
    )
    if not latest:
        return _csv_response([], _COLUMNS_TRENDING, filename)

    prev_week = latest - timedelta(weeks=1)

    # Current-week rows
    stmt = (
        select(SkillTrend)
        .where(SkillTrend.week_start == latest)
        .order_by(SkillTrend.mention_count.desc())
    )
    if role:
        stmt = stmt.where(SkillTrend.role_category == role)
    current_rows = list(session.scalars(stmt))

    # Previous-week index for WoW
    prev_stmt = select(SkillTrend).where(SkillTrend.week_start == prev_week)
    if role:
        prev_stmt = prev_stmt.where(SkillTrend.role_category == role)
    prev_index = {
        (r.skill, r.role_category): r.mention_count
        for r in session.scalars(prev_stmt)
    }

    csv_rows = []
    for row in current_rows:
        prev_count = prev_index.get((row.skill, row.role_category), 0)
        if prev_count == 0:
            wow = 100.0 if row.mention_count > 0 else 0.0
        else:
            wow = (row.mention_count - prev_count) / prev_count * 100.0

        csv_rows.append([
            row.skill,
            row.role_category,
            str(row.week_start),
            row.mention_count,
            round(row.pct_of_postings, 4),
            round(wow, 1),
        ])

    return _csv_response(csv_rows, _COLUMNS_TRENDING, filename)


# ── GET /api/export/skills/gap ────────────────────────────────────────────────

@router.get(
    "/skills/gap",
    summary="Export skill gap analysis as CSV",
    response_description="CSV file with columns: skill, status, demand_pct, role_category",
)
def export_gap(
    role_category: str = Query(..., description="Role to analyse, e.g. 'data analyst'"),
    user_skills: str = Query(..., description="Comma-separated list of user skills, e.g. 'python,sql,excel'"),
    session: Session = Depends(get_session),
):
    """Download a skill gap analysis as a CSV file.

    Compares the supplied skills against the top 30 in-demand skills for the
    given role and classifies each as ``matched``, ``missing``, or ``bonus``.

    If no data exists the file contains only the header row.
    """
    role = role_category.strip().lower()
    user_skills_lower = {s.strip().lower() for s in user_skills.split(",") if s.strip()}
    filename = f"roleprint_gap_{role.replace(' ', '_')}_{_today()}.csv"

    latest = session.scalar(
        select(SkillTrend.week_start).order_by(SkillTrend.week_start.desc()).limit(1)
    )
    if not latest:
        return _csv_response([], _COLUMNS_GAP, filename)

    all_rows = list(session.scalars(
        select(SkillTrend)
        .where(SkillTrend.week_start == latest, SkillTrend.role_category == role)
        .order_by(SkillTrend.mention_count.desc())
    ))
    if not all_rows:
        return _csv_response([], _COLUMNS_GAP, filename)

    top30 = all_rows[:30]
    top30_lower = {r.skill.lower() for r in top30}
    beyond_index = {r.skill.lower(): r for r in all_rows[30:]}

    csv_rows = []

    for row in top30:
        status = "matched" if row.skill.lower() in user_skills_lower else "missing"
        csv_rows.append([row.skill, status, round(row.pct_of_postings * 100, 1), role])

    for user_skill in user_skills_lower:
        if user_skill not in top30_lower and user_skill in beyond_index:
            row = beyond_index[user_skill]
            csv_rows.append([row.skill, "bonus", round(row.pct_of_postings * 100, 1), role])

    # Sort: matched first, then missing (by demand desc), then bonus
    order = {"matched": 0, "missing": 1, "bonus": 2}
    csv_rows.sort(key=lambda r: (order[r[1]], -r[2]))

    return _csv_response(csv_rows, _COLUMNS_GAP, filename)
