#!/usr/bin/env python3
"""Weekly job-market trend digest.

Prints a plain-text report to stdout that can be piped directly into an
email, saved to a file, or consumed by the scheduler.

Usage:
    # With a running Postgres database:
    python scripts/generate_trend_report.py

    # Override database URL:
    DATABASE_URL=postgresql+psycopg2://... python scripts/generate_trend_report.py

    # Dry-run with sample data (no DB needed):
    python scripts/generate_trend_report.py --demo
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# ── Path bootstrap so the script works without `pip install -e .` ─────────────
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")   # safe import default

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from roleprint.nlp.trends import (
    emerging_skills,
    rising_skills,
    role_similarity_matrix,
    skill_cooccurrence,
    week_over_week_change,
)
from roleprint.scraper.runner import ROLE_CATEGORIES

# ── Formatting helpers ────────────────────────────────────────────────────────

_WIDTH = 72
_SEP = "─" * _WIDTH


def _header(text: str) -> str:
    pad = max(0, _WIDTH - len(text) - 4)
    return f"\n{'─' * 2}  {text}  {'─' * pad}\n"


def _subheader(text: str) -> str:
    return f"\n  {text}\n  {'·' * len(text)}"


def _pct_bar(pct: float, width: int = 20) -> str:
    """ASCII bar proportional to pct (capped at 100 %)."""
    filled = min(int(abs(pct) / 100 * width), width)
    bar = "█" * filled + "░" * (width - filled)
    sign = "+" if pct >= 0 else "-"
    return f"[{bar}] {sign}{abs(pct):.1f}%"


def _arrow(pct: float) -> str:
    if pct > 20:
        return "▲▲"
    if pct > 5:
        return "▲ "
    if pct < -20:
        return "▼▼"
    if pct < -5:
        return "▼ "
    return "→ "


# ── Report sections ───────────────────────────────────────────────────────────

def section_rising_skills(session: Session) -> str:
    lines = [_header("RISING SKILLS  (week-over-week, top 5 per role)")]

    for role in ROLE_CATEGORIES:
        rows = rising_skills(role, session, top_n=5)
        if not rows:
            continue

        lines.append(_subheader(role.title()))
        for r in rows:
            if r["current_count"] == 0:
                continue
            arrow = _arrow(r["change_pct"])
            bar = _pct_bar(r["change_pct"])
            flag = "  ★ RISING" if r["is_rising"] else ""
            lines.append(
                f"    {arrow} {r['skill']:<28} {bar}{flag}"
            )

    return "\n".join(lines)


def section_emerging(session: Session) -> str:
    rows = emerging_skills(session, lookback_weeks=4)
    lines = [_header("EMERGING SKILLS  (near-zero 4 weeks ago → growing now)")]

    if not rows:
        lines.append("    No emerging skills detected this week.")
        return "\n".join(lines)

    lines.append(
        f"    {'Skill':<30} {'Role':<22} {'Growth':>8}  {'Now':>4}  {'Then':>4}"
    )
    lines.append("    " + "─" * 68)

    for r in rows[:20]:
        g = f"+{r['growth_pct']:.0f}%" if r["old_count"] == 0 else f"+{r['growth_pct']:.0f}%"
        lines.append(
            f"    {r['skill']:<30} {r['role_category']:<22} {g:>8}"
            f"  {r['current_count']:>4}  {r['old_count']:>4}"
        )

    return "\n".join(lines)


def section_role_similarity(session: Session) -> str:
    roles = ROLE_CATEGORIES
    result = role_similarity_matrix(roles, session)
    matrix = result["matrix"]

    lines = [_header("ROLE SKILL-PROFILE SIMILARITY  (cosine, 0→1)")]

    # Find top 5 most-similar pairs (excluding self)
    pairs: List[Dict[str, Any]] = []
    n = len(roles)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append({
                "role_a": roles[i],
                "role_b": roles[j],
                "sim": matrix[i][j],
            })
    pairs.sort(key=lambda x: x["sim"], reverse=True)

    lines.append(_subheader("Most similar pairs"))
    for p in pairs[:5]:
        bar_len = int(p["sim"] * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        lines.append(
            f"    {p['role_a']:<22} ↔  {p['role_b']:<22}  [{bar}] {p['sim']:.2f}"
        )

    lines.append(_subheader("Least similar pairs"))
    for p in pairs[-3:]:
        bar_len = int(p["sim"] * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        lines.append(
            f"    {p['role_a']:<22} ↔  {p['role_b']:<22}  [{bar}] {p['sim']:.2f}"
        )

    return "\n".join(lines)


def section_cooccurrence(session: Session) -> str:
    lines = [_header("SKILL CO-OCCURRENCE  (top 5 pairs per role)")]

    for role in ROLE_CATEGORIES:
        result = skill_cooccurrence(role, session, top_n=5, min_count=2)
        if not result["top_pairs"]:
            continue

        lines.append(_subheader(role.title()))
        for pair in result["top_pairs"]:
            lines.append(
                f"    {pair['skill_a']:<24} + {pair['skill_b']:<24}  "
                f"co-occur in {pair['count']} postings"
            )

    return "\n".join(lines)


# ── Demo data injector (--demo flag) ──────────────────────────────────────────

def _inject_demo_data(session: Session) -> None:
    """Seed a minimal in-memory DB so the report renders without real data."""
    from roleprint.db.base import Base
    from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend
    import uuid

    Base.metadata.create_all(session.bind)

    today = date.today()
    current_week = today - timedelta(days=today.weekday())
    prev_week = current_week - timedelta(weeks=1)
    old_week = current_week - timedelta(weeks=4)

    demo_trends = [
        # role, skill, week, count, pct
        ("data analyst", "Python",               current_week, 42, 0.84),
        ("data analyst", "SQL",                  current_week, 38, 0.76),
        ("data analyst", "Tableau",              current_week, 28, 0.56),
        ("data analyst", "dbt",                  current_week, 19, 0.38),
        ("data analyst", "Snowflake",            current_week, 17, 0.34),
        ("data analyst", "stakeholder management", current_week, 31, 0.62),
        ("data analyst", "agile",                current_week, 22, 0.44),
        ("data analyst", "LLM",                  current_week, 8,  0.16),
        ("data analyst", "Python",               prev_week,    30, 0.60),
        ("data analyst", "SQL",                  prev_week,    37, 0.74),
        ("data analyst", "Tableau",              prev_week,    29, 0.58),
        ("data analyst", "dbt",                  prev_week,    10, 0.20),
        ("data analyst", "stakeholder management", prev_week,  30, 0.60),
        ("data analyst", "LLM",                  old_week,     1,  0.02),

        ("ml engineer",  "Python",               current_week, 48, 0.96),
        ("ml engineer",  "PyTorch",              current_week, 35, 0.70),
        ("ml engineer",  "Kubernetes",           current_week, 22, 0.44),
        ("ml engineer",  "MLflow",               current_week, 14, 0.28),
        ("ml engineer",  "LangChain",            current_week, 11, 0.22),
        ("ml engineer",  "Python",               prev_week,    40, 0.80),
        ("ml engineer",  "PyTorch",              prev_week,    28, 0.56),
        ("ml engineer",  "LangChain",            prev_week,    3,  0.06),
        ("ml engineer",  "LangChain",            old_week,     0,  0.00),

        ("data engineer","Python",               current_week, 45, 0.90),
        ("data engineer","Spark",                current_week, 32, 0.64),
        ("data engineer","Kafka",                current_week, 27, 0.54),
        ("data engineer","dbt",                  current_week, 24, 0.48),
        ("data engineer","Airflow",              current_week, 21, 0.42),
        ("data engineer","Python",               prev_week,    38, 0.76),
        ("data engineer","Spark",                prev_week,    30, 0.60),

        ("software engineer","Python",           current_week, 41, 0.82),
        ("software engineer","TypeScript",       current_week, 33, 0.66),
        ("software engineer","Docker",           current_week, 28, 0.56),
        ("software engineer","Kubernetes",       current_week, 24, 0.48),
        ("software engineer","Python",           prev_week,    35, 0.70),
        ("software engineer","TypeScript",       prev_week,    28, 0.56),
    ]

    for role, skill, week, count, pct in demo_trends:
        existing = session.scalar(
            __import__("sqlalchemy").select(SkillTrend).where(
                SkillTrend.skill == skill,
                SkillTrend.role_category == role,
                SkillTrend.week_start == week,
            )
        )
        if not existing:
            session.add(SkillTrend(
                skill=skill, role_category=role,
                week_start=week, mention_count=count, pct_of_postings=pct,
            ))

    # Seed a few processed postings for co-occurrence
    now = datetime.now(tz=timezone.utc)
    demo_docs = [
        ("data analyst", ["Python", "SQL", "Tableau", "stakeholder management", "agile"]),
        ("data analyst", ["Python", "SQL", "dbt", "Snowflake", "agile"]),
        ("data analyst", ["SQL", "Power BI", "Excel", "stakeholder management"]),
        ("ml engineer",  ["Python", "PyTorch", "Kubernetes", "MLflow"]),
        ("ml engineer",  ["Python", "PyTorch", "LangChain", "Docker"]),
        ("data engineer",["Python", "Spark", "Kafka", "Airflow", "dbt"]),
        ("data engineer",["Python", "dbt", "Snowflake", "Airflow"]),
    ]

    for role, skills in demo_docs:
        posting = JobPosting(
            source="demo", role_category=role,
            title="Demo", company="Demo Co", location="Remote",
            raw_text=" ".join(skills),
            url=f"https://demo.example.com/{uuid.uuid4()}",
            scraped_at=now, is_processed=True,
        )
        session.add(posting)
        session.flush()
        session.add(ProcessedPosting(
            posting_id=posting.id,
            skills_extracted=skills,
            sentiment_score=0.1,
            topics={},
            entities={},
            processed_at=now,
        ))

    session.commit()


# ── Main report builder ───────────────────────────────────────────────────────

def build_report(session: Session) -> str:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    header = "\n".join([
        "=" * _WIDTH,
        f"  ROLEPRINT WEEKLY DIGEST  –  week of {week_start}",
        f"  Generated {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * _WIDTH,
    ])

    sections = [
        header,
        section_rising_skills(session),
        section_emerging(session),
        section_cooccurrence(session),
        section_role_similarity(session),
        "\n" + "=" * _WIDTH + "\n  End of report\n" + "=" * _WIDTH + "\n",
    ]

    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Roleprint weekly trend digest")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Inject demo data into an in-memory DB and render without a real DB",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write report to FILE instead of stdout",
    )
    args = parser.parse_args()

    if args.demo:
        engine = create_engine("sqlite:///:memory:", echo=False)
        session = Session(engine)
        _inject_demo_data(session)
    else:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("ERROR: DATABASE_URL not set. Use --demo for a preview.", file=sys.stderr)
            sys.exit(1)
        engine = create_engine(db_url, pool_pre_ping=True)
        session = Session(engine)

    try:
        report = build_report(session)
    finally:
        session.close()

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
