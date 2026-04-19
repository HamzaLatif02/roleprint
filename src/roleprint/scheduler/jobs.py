"""APScheduler job implementations.

Two scheduled jobs:
  - scrape_job      every 6 h — scrapes all role categories
  - process_job     every 6 h (1 h after scrape) — NLP pipeline on unprocessed rows

Each job opens its own database session and closes it when done.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Job 1 — Scrape
# ─────────────────────────────────────────────────────────────────────────────

def scrape_job() -> None:
    """Run the full scrape pipeline across all role categories.

    Creates a fresh DB session, delegates to :func:`roleprint.scraper.runner.run_all`,
    then logs a summary of postings scraped / duplicates skipped / errors.
    """
    import asyncio

    from roleprint.scraper.runner import run_all

    log.info("scrape_job.start")
    try:
        summary = asyncio.run(run_all())
        total = sum(
            v for source_counts in summary.values()
            for v in (source_counts.values() if isinstance(source_counts, dict) else [source_counts])
        )
        log.info("scrape_job.complete", total_saved=total, summary=summary)
    except Exception:
        log.exception("scrape_job.error")


# ─────────────────────────────────────────────────────────────────────────────
# Job 2 — NLP processing
# ─────────────────────────────────────────────────────────────────────────────

def process_job() -> None:
    """Run the NLP pipeline on all unprocessed job postings.

    Delegates to :func:`roleprint.nlp.pipeline.run_all` which handles
    batching, progress logging, and error recovery per posting.
    """
    from roleprint.nlp.pipeline import run_all as nlp_run_all

    log.info("process_job.start")
    try:
        stats = nlp_run_all()
        log.info("process_job.complete", **stats)
    except Exception:
        log.exception("process_job.error")
