"""NLP pipeline orchestrator.

Reads unprocessed job postings from the database in batches, runs each
through the full NLP stack, writes results to ``processed_postings``, marks
the source posting as processed, and maintains the ``skill_trends`` aggregates.

Run:
    python -m roleprint.nlp.pipeline
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import structlog
from dotenv import load_dotenv
from sqlalchemy import func as sa_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend
from roleprint.db.queries import get_unprocessed_postings
from roleprint.db.session import SessionLocal
from roleprint.nlp import cleaner, ner, sentiment, skill_extractor, topic_model

load_dotenv()
log = structlog.get_logger(__name__)

BATCH_SIZE = int(os.getenv("NLP_BATCH_SIZE", "50"))


# ── Individual posting processor ─────────────────────────────────────────────


def process_posting(
    posting: JobPosting,
    nlp: Optional[Any] = None,
    topic_mdl: Optional[Any] = None,
) -> Dict:
    """Run the full NLP stack on one ``JobPosting``.

    Args:
        posting:    ORM object with at least ``raw_text`` and ``role_category``.
        nlp:        Optional pre-loaded spaCy model (avoids repeated disk loads).
        topic_mdl:  Optional pre-loaded BERTopic model.

    Returns:
        Dict with keys matching ``ProcessedPosting`` columns:
        ``skills_extracted``, ``sentiment_score``, ``topics``, ``entities``.
    """
    # 1. Clean
    cleaned = cleaner.clean(posting.raw_text or "")
    cleaned_lower = cleaned.lower()

    # 2. Skills
    skills = skill_extractor.extract_skills(cleaned, nlp=nlp)

    # 3. Sentiment
    sentiment_result = sentiment.analyse(cleaned)
    compound = sentiment_result["compound"]

    # 4. NER
    if nlp is not None:
        entities = ner.extract_entities(cleaned, nlp=nlp)
        entities = ner.merge_tool_entities(entities, list(skills.keys()))
    else:
        entities = {"orgs": [], "locations": [], "products": []}

    # 5. Topics
    if topic_mdl is not None:
        topic_results = topic_model.assign_topics([cleaned], model=topic_mdl)
        topics = topic_results[0] if topic_results else {}
    else:
        topics = {}

    return {
        "skills_extracted": list(skills.keys()),
        "sentiment_score": compound,
        "topics": topics,
        "entities": entities,
    }


# ── Database write helpers ────────────────────────────────────────────────────


def _write_result(session: Session, posting: JobPosting, result: Dict) -> None:
    """Insert a ``ProcessedPosting`` row and mark the source as processed."""
    proc = ProcessedPosting(
        posting_id=posting.id,
        skills_extracted=result["skills_extracted"],
        sentiment_score=result["sentiment_score"],
        topics=result["topics"],
        entities=result["entities"],
        processed_at=datetime.now(tz=timezone.utc),
    )
    session.add(proc)
    posting.is_processed = True


def _week_start(dt: datetime) -> date:
    """Return the ISO Monday of the week containing *dt*."""
    d = dt.date() if isinstance(dt, datetime) else dt
    return d - timedelta(days=d.weekday())


def _upsert_skill_trend(
    session: Session,
    skill: str,
    role_category: str,
    week_start: date,
    delta_count: int,
    total_this_week: int,
) -> None:
    """Create or update a SkillTrend row.

    pct_of_postings is calculated as mention_count / true_weekly_total where
    true_weekly_total is the count of ALL postings for (role_category, week_start)
    in job_postings — not just the current batch. This prevents values > 1
    when the pipeline runs multiple batches across the same week.

    SQLAlchemy-level merge compatible with both SQLite (tests) and PostgreSQL.
    """
    # Query the actual number of postings for this role/week, not just the batch.
    from datetime import time as dt_time

    week_end = week_start + timedelta(days=7)
    true_total: int = (
        session.scalar(
            select(sa_func.count(JobPosting.id)).where(
                JobPosting.role_category == role_category,
                JobPosting.scraped_at >= datetime.combine(week_start, dt_time.min),
                JobPosting.scraped_at < datetime.combine(week_end, dt_time.min),
            )
        )
        or total_this_week
    )  # fall back to batch size if query returns 0 (e.g. tests)

    existing = session.scalar(
        select(SkillTrend).where(
            SkillTrend.skill == skill,
            SkillTrend.role_category == role_category,
            SkillTrend.week_start == week_start,
        )
    )
    if existing:
        existing.mention_count += delta_count
        pct = existing.mention_count / true_total if true_total > 0 else 0.0
        existing.pct_of_postings = round(pct, 4)
    else:
        pct = delta_count / true_total if true_total > 0 else 0.0
        session.add(
            SkillTrend(
                skill=skill,
                role_category=role_category,
                week_start=week_start,
                mention_count=delta_count,
                pct_of_postings=round(pct, 4),
            )
        )


def _update_skill_trends(session: Session, batch_results: List[Tuple[JobPosting, Dict]]) -> None:
    """Aggregate skill mentions from a processed batch and upsert skill_trends."""

    # Collect (role, week) → {skill: count, _total: n}
    aggregated: Dict[Tuple[str, date], Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for posting, result in batch_results:
        role = posting.role_category
        week = _week_start(posting.scraped_at or datetime.now(tz=timezone.utc))
        key = (role, week)

        aggregated[key]["_total"] += 1
        for skill in result["skills_extracted"]:
            aggregated[key][skill] += 1

    for (role, week), counts in aggregated.items():
        total = counts.pop("_total", 1)
        for skill, count in counts.items():
            _upsert_skill_trend(session, skill, role, week, count, total)


# ── Batch runner ──────────────────────────────────────────────────────────────


def run_batch(
    session: Session,
    batch_size: int = BATCH_SIZE,
    nlp: Optional[Any] = None,
    topic_mdl: Optional[Any] = None,
) -> Dict:
    """Process one batch of unprocessed postings.

    Args:
        session:    Active SQLAlchemy session.
        batch_size: How many postings to pull at once.
        nlp:        Pre-loaded spaCy model (loaded on first call if None).
        topic_mdl:  Pre-loaded BERTopic model.

    Returns:
        Summary dict: ``{"processed": int, "errors": int}``.
    """
    postings = get_unprocessed_postings(session, limit=batch_size)
    if not postings:
        log.info("pipeline.batch_empty")
        return {"processed": 0, "errors": 0}

    # Lazy-load spaCy if requested but not injected
    if nlp is None:
        try:
            nlp = ner.get_nlp()
        except RuntimeError:
            log.warning("pipeline.spacy_unavailable")

    processed_count = 0
    error_count = 0
    batch_results: List[Tuple[JobPosting, Dict]] = []

    for posting in postings:
        try:
            result = process_posting(posting, nlp=nlp, topic_mdl=topic_mdl)
            _write_result(session, posting, result)
            batch_results.append((posting, result))
            processed_count += 1
        except Exception as exc:
            log.error(
                "pipeline.posting_error",
                posting_id=str(posting.id),
                error=str(exc),
            )
            error_count += 1
            session.rollback()
            continue

    try:
        session.flush()
        _update_skill_trends(session, batch_results)
        session.commit()
    except Exception as exc:
        log.error("pipeline.commit_error", error=str(exc))
        session.rollback()

    log.info(
        "pipeline.batch_complete",
        processed=processed_count,
        errors=error_count,
        skill_trends_updated=len(batch_results),
    )
    return {"processed": processed_count, "errors": error_count}


def run_all(session: Optional[Session] = None) -> Dict:
    """Process all unprocessed postings until exhausted.

    Args:
        session: Optional externally-managed session (for tests).

    Returns:
        Cumulative summary dict.
    """
    own_session = session is None
    if own_session:
        session = SessionLocal()

    total = {"processed": 0, "errors": 0}

    try:
        nlp_model = None
        try:
            nlp_model = ner.get_nlp()
        except RuntimeError:
            log.warning("pipeline.spacy_unavailable")

        topic_mdl = topic_model._load_or_none()

        while True:
            result = run_batch(
                session,
                batch_size=BATCH_SIZE,
                nlp=nlp_model,
                topic_mdl=topic_mdl,
            )
            if result["processed"] == 0:
                break
            total["processed"] += result["processed"]
            total["errors"] += result["errors"]

        log.info("pipeline.run_complete", **total)
    finally:
        if own_session and session:
            session.close()

    return total


def main() -> None:
    _configure_logging()
    run_all()


def _configure_logging() -> None:
    import logging
    import structlog

    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


if __name__ == "__main__":
    main()
