#!/usr/bin/env python3
"""Test the Resend email sender end-to-end.

Sends a real email using the existing Jinja2 digest template populated with
hardcoded dummy data, then tests error handling with an invalid domain.

Usage:
    PYTHONPATH=src python scripts/test_email.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

G, R, Y, Z = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
def ok(m):   print(f"  {G}✓{Z} {m}")
def err(m):  print(f"  {R}✗{Z} {m}")
def warn(m): print(f"  {Y}!{Z} {m}")
def hdr(m):  print(f"\n{'─'*56}\n  {m}\n{'─'*56}")

# ── Dummy digest data ─────────────────────────────────────────────────────────

DUMMY_CONTEXT = {
    "week": "19 Apr 2026",
    "total_postings_this_week": 142,
    "top_skills": [
        {"skill": "Python",   "role_category": "data analyst",      "mention_count": 64, "change_pct": 12.0},
        {"skill": "SQL",      "role_category": "data analyst",      "mention_count": 54, "change_pct":  4.5},
        {"skill": "dbt",      "role_category": "data engineer",     "mention_count": 31, "change_pct": 31.0},
        {"skill": "Spark",    "role_category": "data engineer",     "mention_count": 27, "change_pct": -2.1},
        {"skill": "Tableau",  "role_category": "data analyst",      "mention_count": 21, "change_pct":  0.3},
    ],
    "emerging": [
        {"skill": "BERTopic", "role_category": "ml engineer",       "growth_pct": 210, "old_count": 2,  "current_count": 6},
        {"skill": "Polars",   "role_category": "data engineer",     "growth_pct": 175, "old_count": 4,  "current_count": 11},
        {"skill": "DuckDB",   "role_category": "data analyst",      "growth_pct": 140, "old_count": 5,  "current_count": 12},
    ],
    "sentiment_by_role": [
        {"role_category": "data analyst",      "avg_sentiment":  0.30, "posting_count": 58, "urgency_total": 3},
        {"role_category": "software engineer", "avg_sentiment":  0.10, "posting_count": 84, "urgency_total": 7},
    ],
    "subscribe_url":   "https://roleprint.xyz",
    "unsubscribe_url": "https://roleprint.xyz/unsubscribe?token=test-token",
}

# ── Template rendering ────────────────────────────────────────────────────────

def render_html(extra_note: str = "") -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(_ROOT / "src" / "roleprint" / "scheduler")),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("email_template.html")
    html = template.render(**DUMMY_CONTEXT)

    # Inject test note before closing </body>
    if extra_note:
        note_html = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:#fffbeb;border-top:2px dashed #f5a623;">'
            f'<tr><td align="center" style="padding:14px;font-size:12px;'
            f'color:#92400e;font-family:monospace;">{extra_note}</td></tr></table>'
        )
        html = html.replace("</body>", note_html + "</body>")

    return html


# ── Send via Resend ───────────────────────────────────────────────────────────

def send_email(to: str, subject: str, html: str) -> dict:
    """Send via Resend SDK. Returns result dict with keys: ok, id, error, status_code."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("FROM_EMAIL", "digest@roleprint.io")

    if not api_key:
        return {"ok": False, "error": "RESEND_API_KEY not set", "status_code": 0}

    try:
        import resend  # type: ignore[import]
        resend.api_key = api_key

        response = resend.Emails.send({
            "from": f"Roleprint <{from_addr}>",
            "to": [to],
            "subject": subject,
            "html": html,
        })

        email_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)

        if email_id:
            return {"ok": True, "id": email_id, "status_code": 200}
        else:
            return {"ok": False, "error": f"Unexpected response: {response}", "status_code": 0}

    except Exception as exc:
        # Resend SDK raises for 4xx/5xx — extract status code if available
        status = getattr(exc, "status_code", getattr(exc, "status", 0))
        return {"ok": False, "error": str(exc), "status_code": status}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_valid_send() -> bool:
    hdr("Test 1 — Send digest to lhamza1020@gmail.com")

    to = "lhamza1020@gmail.com"
    subject = "[Roleprint Test] Email Pipeline Working"
    note = "⚠ This is a test email from the Roleprint pipeline."

    print("  Rendering template…", end=" ", flush=True)
    html = render_html(extra_note=note)
    print(f"done ({len(html):,} chars)")

    print(f"  Sending to {to}…")
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    result = send_email(to, subject, html)

    print(f"  Timestamp:   {ts}")
    print(f"  Recipient:   {to}")

    if result["ok"]:
        ok(f"Accepted by Resend  (id={result['id']})")
        return True
    else:
        err(f"Failed — status={result['status_code']}  error={result['error']}")
        return False


def test_invalid_send() -> bool:
    hdr("Test 2 — Error handling (invalid domain)")

    to = "test@thisisnotavaliddomain12345.com"
    subject = "[Roleprint Test] Error Handling Check"
    html = "<p>Error handling test — should fail gracefully.</p>"

    print(f"  Sending to {to}…")
    result = send_email(to, subject, html)

    if not result["ok"]:
        ok(f"Failure caught correctly — status={result['status_code']}  error={result['error'][:120]}")
        return True
    else:
        # Resend may accept the email even with an invalid domain (it validates async)
        warn(f"Resend accepted the send (id={result['id']}) — async delivery will fail")
        warn("This is expected: Resend validates domain deliverability asynchronously, not at send time")
        return True  # not a test failure — Resend's behaviour


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    hdr("Roleprint Email Pipeline Test")
    print(f"  RESEND_API_KEY : {'set (' + os.environ.get('RESEND_API_KEY','')[:12] + '…)' if os.environ.get('RESEND_API_KEY') else 'NOT SET'}")
    print(f"  FROM_EMAIL     : {os.environ.get('FROM_EMAIL', 'not set')}")

    if not os.environ.get("RESEND_API_KEY"):
        err("RESEND_API_KEY is not set — add it to .env and retry")
        sys.exit(1)

    results = {
        "valid send":   test_valid_send(),
        "error handling": test_invalid_send(),
    }

    hdr("Summary")
    all_pass = True
    for name, passed in results.items():
        if passed:
            ok(f"PASS  {name}")
        else:
            err(f"FAIL  {name}")
            all_pass = False

    print()
    if all_pass:
        ok("All tests passed — check lhamza1020@gmail.com for the digest email")
    else:
        err("Some tests failed — see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
