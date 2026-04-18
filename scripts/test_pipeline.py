#!/usr/bin/env python3
"""End-to-end pipeline test.

Runs in order:
  1. Scrape  — data analyst + software engineer, 2 pages per source
  2. NLP     — process all unprocessed postings, print a sample
  3. Trends  — top 5 skills from skill_trends
  4. API     — hit every live endpoint, report pass/fail
  5. Seed    — seed_demo_data.py for a fuller dataset

Usage:
    DATABASE_URL=postgresql+psycopg2://... PYTHONPATH=src \\
        python scripts/test_pipeline.py

    # Skip heavy steps during a re-run:
    DATABASE_URL=... PYTHONPATH=src \\
        python scripts/test_pipeline.py --skip-scrape --skip-seed

    # Point at a different API host:
    DATABASE_URL=... PYTHONPATH=src \\
        python scripts/test_pipeline.py \\
        --api-url https://roleprint-production.up.railway.app
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

# ── Colours ───────────────────────────────────────────────────────────────────
G, R, Y, B, W, Z = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[97m", "\033[0m"

def ok(msg):   print(f"  {G}✓{Z} {msg}")
def err(msg):  print(f"  {R}✗{Z} {msg}")
def warn(msg): print(f"  {Y}!{Z} {msg}")
def hdr(msg):  print(f"\n{W}{'─'*60}\n  {msg}\n{'─'*60}{Z}")


# ── Step 1 — Scrape ───────────────────────────────────────────────────────────

def step_scrape() -> int:
    hdr("Step 1 — Scrape (data analyst + software engineer, 2 pages)")

    from sqlalchemy import text
    from roleprint.db.session import SessionLocal
    from roleprint.scraper.reed import ReedScraper
    from roleprint.scraper.remoteok import RemoteOKScraper
    from roleprint.scraper.runner import _save_postings

    TEST_ROLES = ["data analyst", "software engineer"]

    session = SessionLocal()
    before = session.execute(text("SELECT COUNT(*) FROM job_postings")).scalar() or 0
    session.close()

    total_saved = 0

    async def _run():
        nonlocal total_saved
        for role in TEST_ROLES:
            print(f"\n  Role: {role}")

            # Reed
            try:
                async with ReedScraper() as scraper:
                    raw = await scraper.search(role, pages=2)
                s = SessionLocal()
                deduped = scraper.deduplicate(raw, s)
                saved = _save_postings(deduped, s)
                s.commit()
                s.close()
                total_saved += saved
                ok(f"Reed: fetched {len(raw)}, saved {saved} new")
            except Exception as exc:
                err(f"Reed [{role}]: {exc}")
                traceback.print_exc()

            # RemoteOK
            try:
                async with RemoteOKScraper() as scraper:
                    raw = await scraper.search(role)
                s = SessionLocal()
                deduped = scraper.deduplicate(raw, s)
                saved = _save_postings(deduped, s)
                s.commit()
                s.close()
                total_saved += saved
                ok(f"RemoteOK: fetched {len(raw)}, saved {saved} new")
            except Exception as exc:
                err(f"RemoteOK [{role}]: {exc}")
                traceback.print_exc()

    asyncio.run(_run())

    session = SessionLocal()
    after = session.execute(text("SELECT COUNT(*) FROM job_postings")).scalar() or 0
    session.close()

    print(f"\n  Before: {before}  |  After: {after}  |  Net new: {after - before}")
    return after - before


# ── Step 2 — NLP pipeline ─────────────────────────────────────────────────────

def step_nlp() -> int:
    hdr("Step 2 — NLP pipeline")

    from sqlalchemy import text
    from roleprint.db.session import SessionLocal
    from roleprint.nlp.pipeline import run_all

    session = SessionLocal()
    unprocessed = session.execute(
        text("SELECT COUNT(*) FROM job_postings WHERE is_processed = false")
    ).scalar() or 0
    session.close()

    print(f"  Unprocessed: {unprocessed}")
    if unprocessed == 0:
        warn("Nothing to process — all postings already processed")
        return 0

    result = run_all()
    ok(f"Processed: {result['processed']}  Failed: {result['failed']}  Skipped: {result['skipped']}")

    # Sample output
    session = SessionLocal()
    row = session.execute(text("""
        SELECT jp.title, jp.company,
               pp.skills_extracted, pp.sentiment_score,
               pp.sentiment_label, pp.urgency_count,
               pp.entities, pp.topic_id
        FROM processed_postings pp
        JOIN job_postings jp ON jp.id = pp.job_posting_id
        ORDER BY pp.id DESC
        LIMIT 1
    """)).fetchone()
    session.close()

    if row:
        print(f"\n  {B}Sample (most recently processed):{Z}")
        print(f"    Title:     {row.title}")
        print(f"    Company:   {row.company}")
        print(f"    Skills:    {row.skills_extracted}")
        print(f"    Sentiment: {row.sentiment_score:.3f} ({row.sentiment_label}), urgency={row.urgency_count}")
        print(f"    Entities:  {row.entities}")
        print(f"    Topic ID:  {row.topic_id}")

    return result["processed"]


# ── Step 3 — Trends ───────────────────────────────────────────────────────────

def step_trends() -> None:
    hdr("Step 3 — Trend data")

    from sqlalchemy import text
    from roleprint.db.session import SessionLocal

    session = SessionLocal()
    trend_rows = session.execute(text("SELECT COUNT(*) FROM skill_trends")).scalar() or 0
    top5 = session.execute(text("""
        SELECT skill, SUM(mention_count) AS total
        FROM skill_trends
        GROUP BY skill
        ORDER BY total DESC
        LIMIT 5
    """)).fetchall()
    session.close()

    print(f"  skill_trends rows: {trend_rows}")
    if top5:
        print(f"\n  {B}Top 5 skills:{Z}")
        for i, r in enumerate(top5, 1):
            print(f"    {i}. {r.skill:<35} {r.total} mentions")
    else:
        warn("No skill_trends rows yet — NLP pipeline may not have run trend aggregation")


# ── Step 4 — API tests ────────────────────────────────────────────────────────

def step_api(api_url: str) -> tuple[int, int]:
    hdr(f"Step 4 — Live API tests\n  {api_url}")

    endpoints = [
        "/health",
        "/api/stats/summary",
        "/api/roles",
        "/api/skills/trending?role_category=data+analyst&weeks=4",
        "/api/skills/emerging",
        "/api/sentiment/timeline?role_category=data+analyst&weeks=4",
        "/api/topics?role_category=data+analyst",
    ]

    passed = failed = 0
    for path in endpoints:
        url = api_url.rstrip("/") + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    note = f"{len(data)} items"
                    has_data = len(data) > 0
                else:
                    note = ", ".join(f"{k}={v!r}" for k, v in list(data.items())[:3])
                    has_data = any(v not in (None, [], {}, 0) for v in data.values())

                if has_data:
                    ok(f"{resp.status} {path}  ({note})")
                else:
                    warn(f"{resp.status} {path}  (empty — {note})")
                passed += 1
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:300]
            err(f"{exc.code} {path}  → {body}")
            failed += 1
        except Exception as exc:
            err(f"ERR {path}  → {exc}")
            failed += 1

    return passed, failed


# ── Step 5 — Seed ─────────────────────────────────────────────────────────────

def step_seed() -> None:
    hdr("Step 5 — Seed demo data (200 postings, 8 weeks, all roles)")
    import subprocess
    r = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "seed_demo_data.py"),
         "--count", "200", "--weeks", "8"],
        env={**os.environ, "PYTHONPATH": str(_ROOT / "src")},
    )
    if r.returncode == 0:
        ok("Seed complete")
    else:
        err(f"Seed exited with code {r.returncode}")


# ── Summary ───────────────────────────────────────────────────────────────────

def summary(scraped: int, processed: int, api_pass: int, api_fail: int, issues: list) -> None:
    hdr("Summary")
    from sqlalchemy import text
    from roleprint.db.session import SessionLocal

    s = SessionLocal()
    total_jp = s.execute(text("SELECT COUNT(*) FROM job_postings")).scalar() or 0
    total_pp = s.execute(text("SELECT COUNT(*) FROM processed_postings")).scalar() or 0
    total_st = s.execute(text("SELECT COUNT(*) FROM skill_trends")).scalar() or 0
    s.close()

    print(f"  job_postings:      {total_jp}")
    print(f"  processed_postings:{total_pp}")
    print(f"  skill_trends rows: {total_st}")
    print(f"  Scraped this run:  {scraped}")
    print(f"  NLP this run:      {processed}")
    print(f"  API pass/fail:     {G}{api_pass}{Z} / {R if api_fail else G}{api_fail}{Z}")

    if issues:
        print(f"\n  {Y}Issues:{Z}")
        for i in issues: print(f"    • {i}")
    else:
        ok("All steps completed without errors")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api-url", default="https://roleprint-production.up.railway.app")
    p.add_argument("--skip-scrape",  action="store_true")
    p.add_argument("--skip-nlp",     action="store_true")
    p.add_argument("--skip-trends",  action="store_true")
    p.add_argument("--skip-api",     action="store_true")
    p.add_argument("--skip-seed",    action="store_true")
    args = p.parse_args()

    if not os.environ.get("DATABASE_URL"):
        sys.exit(
            f"{R}Error:{Z} DATABASE_URL not set.\n"
            "Run as: DATABASE_URL=postgresql+psycopg2://... PYTHONPATH=src "
            "python scripts/test_pipeline.py"
        )

    issues: list[str] = []
    scraped = processed = api_pass = api_fail = 0

    steps = [
        ("scrape",  args.skip_scrape,  lambda: globals().update(scraped=step_scrape())),
        ("nlp",     args.skip_nlp,     lambda: globals().update(processed=step_nlp())),
        ("trends",  args.skip_trends,  step_trends),
        ("api",     args.skip_api,     None),  # handled separately for pass/fail
        ("seed",    args.skip_seed,    step_seed),
    ]

    if not args.skip_scrape:
        try: scraped = step_scrape()
        except Exception as e: issues.append(f"scrape: {e}"); traceback.print_exc()

    if not args.skip_nlp:
        try: processed = step_nlp()
        except Exception as e: issues.append(f"nlp: {e}"); traceback.print_exc()

    if not args.skip_trends:
        try: step_trends()
        except Exception as e: issues.append(f"trends: {e}"); traceback.print_exc()

    if not args.skip_api:
        try:
            api_pass, api_fail = step_api(args.api_url)
            if api_fail: issues.append(f"{api_fail} API endpoint(s) failing")
        except Exception as e: issues.append(f"api: {e}"); traceback.print_exc()

    if not args.skip_seed:
        try: step_seed()
        except Exception as e: issues.append(f"seed: {e}"); traceback.print_exc()

    summary(scraped, processed, api_pass, api_fail, issues)


if __name__ == "__main__":
    main()
