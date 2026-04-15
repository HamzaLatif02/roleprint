"""Scheduler entry point.

Run as a standalone worker process:
    python -m roleprint.scheduler.main

On Railway, add a second service with the start command:
    python -m roleprint.scheduler.main

Environment variables (all optional except DATABASE_URL):
    DATABASE_URL         PostgreSQL connection string (required)
    SENDGRID_API_KEY     SendGrid API key for digest emails
    FROM_EMAIL           Sender address  (default: digest@roleprint.io)
    FROM_NAME            Sender name     (default: Roleprint)
    SITE_URL             Base URL for links in emails (default: https://roleprint.io)
    SCRAPE_INTERVAL_HRS  Hours between scrape runs (default: 6)
    PROCESS_DELAY_HRS    Hours after scrape before NLP run (default: 1)
    DIGEST_DAY           Day of week for digest, 0=Monday (default: 0)
    DIGEST_HOUR          UTC hour for digest (default: 8)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Bootstrap path for `python -m roleprint.scheduler.main`
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))

load_dotenv(_ROOT / ".env")


def _configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def build_scheduler() -> BlockingScheduler:
    """Construct and return the configured APScheduler instance.

    Jobs are registered but the scheduler is NOT started here — the caller
    does that.  This separation makes unit-testing easier.
    """
    from roleprint.scheduler.jobs import process_job, scrape_job, weekly_digest_job

    scrape_hours = int(os.environ.get("SCRAPE_INTERVAL_HRS", "6"))
    process_delay = int(os.environ.get("PROCESS_DELAY_HRS", "1"))
    digest_day = int(os.environ.get("DIGEST_DAY", "0"))      # 0 = Monday
    digest_hour = int(os.environ.get("DIGEST_HOUR", "8"))

    log = structlog.get_logger(__name__)

    scheduler = BlockingScheduler(timezone="UTC")

    # Job 1 — Scrape (every N hours, starting at 00:00 UTC)
    # hours=6 → fires at 0, 6, 12, 18
    scrape_hours_list = ",".join(
        str(h % 24) for h in range(0, 24, scrape_hours)
    )
    scheduler.add_job(
        scrape_job,
        trigger=CronTrigger(hour=scrape_hours_list, minute=0, timezone="UTC"),
        id="scrape_job",
        name="Scrape all role categories",
        replace_existing=True,
        misfire_grace_time=600,  # 10 min grace if scheduler was down
    )
    log.info(
        "scheduler.job_registered",
        job="scrape_job",
        trigger=f"cron hour={scrape_hours_list} min=0",
    )

    # Job 2 — NLP processing (same cadence, process_delay hours later)
    process_hours_list = ",".join(
        str((h + process_delay) % 24) for h in range(0, 24, scrape_hours)
    )
    scheduler.add_job(
        process_job,
        trigger=CronTrigger(hour=process_hours_list, minute=0, timezone="UTC"),
        id="process_job",
        name="NLP pipeline — process unprocessed postings",
        replace_existing=True,
        misfire_grace_time=600,
    )
    log.info(
        "scheduler.job_registered",
        job="process_job",
        trigger=f"cron hour={process_hours_list} min=0",
    )

    # Job 3 — Weekly digest
    _DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    digest_day_str = _DAY_NAMES[digest_day % 7]
    scheduler.add_job(
        weekly_digest_job,
        trigger=CronTrigger(
            day_of_week=digest_day_str, hour=digest_hour, minute=0, timezone="UTC"
        ),
        id="weekly_digest_job",
        name="Weekly digest email",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 h grace — it's a weekly job
    )
    log.info(
        "scheduler.job_registered",
        job="weekly_digest_job",
        trigger=f"cron day_of_week={digest_day_str} hour={digest_hour}:00 UTC",
    )

    return scheduler


def main() -> None:
    _configure_logging()
    log = structlog.get_logger(__name__)

    # Validate that DATABASE_URL is set before starting
    if not os.environ.get("DATABASE_URL"):
        log.error("scheduler.missing_env", var="DATABASE_URL")
        sys.exit(1)

    log.info("scheduler.starting")
    scheduler = build_scheduler()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler.shutdown")
    except Exception:
        log.exception("scheduler.fatal")
        sys.exit(1)


if __name__ == "__main__":
    main()
