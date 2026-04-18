"""APScheduler job implementations.

Three scheduled jobs:
  - scrape_job      every 6 h — scrapes all role categories
  - process_job     every 6 h (1 h after scrape) — NLP pipeline on unprocessed rows
  - weekly_digest_job  Mondays 08:00 UTC — renders + sends HTML digest via Resend

Each job opens its own database session and closes it when done.
All side-effects (Resend, DB) are injected/mockable for tests.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend, Subscriber
from roleprint.db.session import SessionLocal
from roleprint.nlp.sentiment import count_urgency
from roleprint.nlp.trends import emerging_skills

log = structlog.get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).parent
_JINJA_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# ── env knobs ─────────────────────────────────────────────────────────────────

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "digest@roleprint.io")
FROM_NAME = os.environ.get("FROM_NAME", "Roleprint")
SITE_URL = os.environ.get("SITE_URL", "https://roleprint.io")


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


# ─────────────────────────────────────────────────────────────────────────────
# Job 3 — Weekly digest
# ─────────────────────────────────────────────────────────────────────────────

def generate_digest_data(session: Session) -> Optional[Dict[str, Any]]:
    """Build the template context dict from live DB data.

    Returns ``None`` when there is no skill-trend data yet (brand-new install).
    """
    # Determine the latest complete week
    latest_week = session.scalar(select(sa_func.max(SkillTrend.week_start)))
    if not latest_week:
        log.warning("digest.no_skill_data")
        return None

    prev_week = latest_week - timedelta(weeks=1)

    # ── Top 10 skills this week (across all roles, by mention count) ─────────
    current_rows = list(session.scalars(
        select(SkillTrend)
        .where(SkillTrend.week_start == latest_week)
        .order_by(SkillTrend.mention_count.desc())
        .limit(10)
    ))

    prev_index: Dict[tuple, int] = {
        (r.skill, r.role_category): r.mention_count
        for r in session.scalars(
            select(SkillTrend).where(SkillTrend.week_start == prev_week)
        )
    }

    top_skills = []
    for row in current_rows:
        prev = prev_index.get((row.skill, row.role_category), 0)
        if prev > 0:
            change_pct = (row.mention_count - prev) / prev * 100.0
        else:
            change_pct = 100.0 if row.mention_count > 0 else 0.0
        top_skills.append({
            "skill": row.skill,
            "role_category": row.role_category,
            "mention_count": row.mention_count,
            "prev_count": prev,
            "change_pct": round(change_pct, 1),
        })

    # ── Top 3 emerging skills ─────────────────────────────────────────────────
    emerging = emerging_skills(session, lookback_weeks=4)[:3]

    # ── Sentiment summary per role (from processed_postings this week) ────────
    # Join to get postings scraped this week, group by role
    week_start_dt = datetime.combine(latest_week, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    week_end_dt = week_start_dt + timedelta(weeks=1)

    sentiment_rows = list(session.execute(
        select(
            JobPosting.role_category,
            sa_func.avg(ProcessedPosting.sentiment_score).label("avg_sentiment"),
            sa_func.count(ProcessedPosting.id).label("posting_count"),
            JobPosting.raw_text,
        )
        .join(ProcessedPosting, JobPosting.id == ProcessedPosting.posting_id)
        .where(
            JobPosting.scraped_at >= week_start_dt,
            JobPosting.scraped_at < week_end_dt,
        )
        .group_by(JobPosting.role_category, JobPosting.raw_text)
    ))

    # Aggregate per role (SQL group-by with raw_text causes multiple rows;
    # re-aggregate in Python so we also get urgency totals)
    role_agg: Dict[str, dict] = defaultdict(
        lambda: {"scores": [], "posting_count": 0, "urgency_total": 0}
    )
    for row in sentiment_rows:
        role = row.role_category
        role_agg[role]["scores"].append(float(row.avg_sentiment) if row.avg_sentiment else 0.0)
        role_agg[role]["posting_count"] += 1
        role_agg[role]["urgency_total"] += count_urgency(row.raw_text or "")

    sentiment_by_role = sorted(
        [
            {
                "role_category": role,
                "avg_sentiment": round(sum(d["scores"]) / len(d["scores"]), 4)
                if d["scores"] else 0.0,
                "posting_count": d["posting_count"],
                "urgency_total": d["urgency_total"],
            }
            for role, d in role_agg.items()
        ],
        key=lambda x: -x["posting_count"],
    )

    # Total postings this week
    total_postings_this_week = session.scalar(
        select(sa_func.count(JobPosting.id)).where(
            JobPosting.scraped_at >= week_start_dt,
            JobPosting.scraped_at < week_end_dt,
        )
    ) or 0

    return {
        "week": str(latest_week),
        "total_postings_this_week": total_postings_this_week,
        "top_skills": top_skills,
        "emerging": emerging,
        "sentiment_by_role": sentiment_by_role,
    }


def render_digest_html(context: Dict[str, Any], subscriber_token: str) -> str:
    """Render the Jinja2 email template for one subscriber."""
    unsubscribe_url = f"{SITE_URL}/api/unsubscribe?token={subscriber_token}"
    tmpl_ctx = {
        **context,
        "subscribe_url": SITE_URL,
        "unsubscribe_url": unsubscribe_url,
    }
    template = _JINJA_ENV.get_template("email_template.html")
    return template.render(**tmpl_ctx)


def _send_via_resend(
    to_email: str,
    subject: str,
    html_content: str,
    api_key: str = RESEND_API_KEY,
) -> None:
    """Send one email via the Resend API.

    Raises on HTTP errors so the caller can catch and log per-recipient.
    """
    import resend  # type: ignore[import]

    resend.api_key = api_key
    response = resend.Emails.send({
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    })
    if not response.get("id"):
        raise RuntimeError(f"Resend returned unexpected response: {response}")


def weekly_digest_job(
    send_fn: Optional[Callable[[str, str, str], None]] = None,
) -> Dict[str, int]:
    """Generate and send the weekly HTML digest to all active subscribers.

    Args:
        send_fn: Optional override for the send function — accepts
                 ``(to_email, subject, html_content)``.  Defaults to
                 :func:`_send_via_resend`.  Pass a mock in tests.

    Returns:
        Dict with ``sent``, ``skipped``, ``failed`` counts.
    """
    if send_fn is None:
        send_fn = lambda to, subj, html: _send_via_resend(to, subj, html)

    log.info("weekly_digest.start")
    sent = skipped = failed = 0

    session: Session = SessionLocal()
    try:
        context = generate_digest_data(session)
        if context is None:
            log.warning("weekly_digest.skipped_no_data")
            return {"sent": 0, "skipped": 0, "failed": 0}

        subscribers = list(session.scalars(
            select(Subscriber).where(Subscriber.is_active.is_(True))
        ))

        if not subscribers:
            log.info("weekly_digest.no_subscribers")
            return {"sent": 0, "skipped": 0, "failed": 0}

        subject = f"Roleprint Weekly Digest — {context['week']}"
        log.info("weekly_digest.sending", count=len(subscribers), week=context["week"])

        for sub in subscribers:
            # Filter: if subscriber has role preferences, skip digest when none
            # of their preferred roles appear in the top skills this week
            if sub.role_preferences:
                roles_in_digest = {s["role_category"] for s in context["top_skills"]}
                if not roles_in_digest.intersection(set(sub.role_preferences)):
                    log.debug(
                        "weekly_digest.subscriber_skipped_no_match",
                        email=sub.email,
                    )
                    skipped += 1
                    continue

            try:
                html = render_digest_html(context, sub.unsubscribe_token)
                send_fn(sub.email, subject, html)
                sent += 1
                log.debug("weekly_digest.sent", email=sub.email)
            except Exception:
                failed += 1
                log.exception("weekly_digest.send_error", email=sub.email)

    except Exception:
        log.exception("weekly_digest.fatal_error")
    finally:
        session.close()

    log.info("weekly_digest.complete", sent=sent, skipped=skipped, failed=failed)
    return {"sent": sent, "skipped": skipped, "failed": failed}
