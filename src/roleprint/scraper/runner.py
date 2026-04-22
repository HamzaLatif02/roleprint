"""Scrape runner — orchestrates all scrapers across all role categories.

Run directly:
    python -m roleprint.scraper.runner

Or via Makefile:
    make scrape
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from roleprint.db.models import JobPosting
from roleprint.db.session import SessionLocal
from roleprint.scraper.adzuna_scraper import AdzunaScraper
from roleprint.scraper.reed import ReedScraper
from roleprint.scraper.remoteok import RemoteOKScraper

load_dotenv()

log = structlog.get_logger(__name__)

ROLE_CATEGORIES: List[str] = [
    "data analyst",
    "data scientist",
    "ml engineer",
    "data engineer",
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "product manager",
    "devops",
    "ai researcher",
]

# How many pages to scrape per role on Reed
REED_PAGES_PER_ROLE = int(os.getenv("REED_PAGES_PER_ROLE", "3"))
REED_LOCATION = os.getenv("REED_LOCATION", "United Kingdom")

# How many pages to scrape per role on Adzuna
ADZUNA_PAGES_PER_ROLE = int(os.getenv("ADZUNA_PAGES_PER_ROLE", "3"))


# ── helpers ────────────────────────────────────────────────────────────────────


def _save_postings(postings: List[dict], session: Session) -> int:
    """Bulk-insert postings, skipping duplicates.  Returns rows inserted."""
    inserted = 0
    for p in postings:
        obj = JobPosting(
            source=p["source"],
            role_category=p["role_category"],
            title=p["title"],
            company=p["company"],
            location=p.get("location", ""),
            raw_text=p.get("raw_text", ""),
            url=p["url"],
            scraped_at=datetime.now(tz=timezone.utc),
            posted_at=p.get("posted_at"),
            is_processed=False,
        )
        session.add(obj)
        try:
            session.flush()
            inserted += 1
        except IntegrityError:
            session.rollback()
            log.debug("runner.duplicate_skipped", url=p["url"])
    return inserted


# ── Reed scrape ────────────────────────────────────────────────────────────────


async def scrape_reed(session: Session) -> dict:
    """Run the Reed scraper across all role categories."""
    counts: dict = defaultdict(int)

    async with ReedScraper() as scraper:
        for role in ROLE_CATEGORIES:
            log.info("runner.reed.start", role=role)
            try:
                raw = await scraper.search(role, location=REED_LOCATION, pages=REED_PAGES_PER_ROLE)
                new = scraper.deduplicate(raw, session)
                saved = _save_postings(new, session)
                session.commit()
                counts[role] = saved
                log.info("runner.reed.done", role=role, fetched=len(raw), saved=saved)
            except Exception as exc:
                log.error("runner.reed.error", role=role, error=str(exc))
                session.rollback()

    return dict(counts)


# ── RemoteOK scrape ────────────────────────────────────────────────────────────


async def scrape_remoteok(session: Session) -> dict:
    """Run the RemoteOK scraper across all role categories."""
    counts: dict = defaultdict(int)

    async with RemoteOKScraper() as scraper:
        for role in ROLE_CATEGORIES:
            log.info("runner.remoteok.start", role=role)
            try:
                raw = await scraper.search(role)
                new = scraper.deduplicate(raw, session)
                saved = _save_postings(new, session)
                session.commit()
                counts[role] = saved
                log.info("runner.remoteok.done", role=role, fetched=len(raw), saved=saved)
            except Exception as exc:
                log.error("runner.remoteok.error", role=role, error=str(exc))
                session.rollback()

    return dict(counts)


# ── Adzuna scrape ──────────────────────────────────────────────────────────────


async def scrape_adzuna(session: Session) -> dict:
    """Run the Adzuna scraper across all role categories.

    Skipped gracefully if ``ADZUNA_APP_ID`` or ``ADZUNA_APP_KEY`` are unset.
    """
    import os

    if not os.getenv("ADZUNA_APP_ID") or not os.getenv("ADZUNA_APP_KEY"):
        log.warning("runner.adzuna.skipped", reason="ADZUNA_APP_ID/ADZUNA_APP_KEY not set")
        return {}

    counts: dict = defaultdict(int)

    async with AdzunaScraper() as scraper:
        for role in ROLE_CATEGORIES:
            log.info("runner.adzuna.start", role=role)
            try:
                raw = await scraper.search(role, pages=ADZUNA_PAGES_PER_ROLE)
                new = scraper.deduplicate(raw, session)
                saved = _save_postings(new, session)
                session.commit()
                counts[role] = saved
                log.info("runner.adzuna.done", role=role, fetched=len(raw), saved=saved)
            except Exception as exc:
                log.error("runner.adzuna.error", role=role, error=str(exc))
                session.rollback()

    return dict(counts)


# ── orchestrator ───────────────────────────────────────────────────────────────


async def run_all(session: Optional[Session] = None) -> dict:
    """Run both scrapers and return a summary dict.

    Args:
        session: Optional externally-managed session (useful for tests).
                 When ``None``, a new session is created from ``SessionLocal``.
    """
    _configure_logging()

    own_session = session is None
    if own_session:
        session = SessionLocal()

    summary: dict = {"reed": {}, "remoteok": {}, "adzuna": {}}
    try:
        log.info("runner.start", roles=len(ROLE_CATEGORIES))

        reed_counts = await scrape_reed(session)
        remoteok_counts = await scrape_remoteok(session)
        adzuna_counts = await scrape_adzuna(session)

        summary["reed"] = reed_counts
        summary["remoteok"] = remoteok_counts
        summary["adzuna"] = adzuna_counts

        total = (
            sum(reed_counts.values()) + sum(remoteok_counts.values()) + sum(adzuna_counts.values())
        )
        log.info("runner.complete", total_saved=total, summary=summary)

    except Exception as exc:
        log.error("runner.fatal_error", error=str(exc))
    finally:
        if own_session and session:
            session.close()

    return summary


def _configure_logging() -> None:
    """Configure structlog for console output."""
    import logging

    import structlog

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
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


def main() -> None:
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
