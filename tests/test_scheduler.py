"""Tests for the scheduler package.

Covers:
  - Subscriber model creation + constraints
  - POST /api/subscribe  (create, update, reactivate, duplicate)
  - GET  /api/unsubscribe?token=...
  - generate_digest_data  (with seeded skill/sentiment data)
  - render_digest_html    (template renders without errors)
  - weekly_digest_job     (send_fn is mocked, no real SendGrid)
  - build_scheduler       (jobs registered with correct IDs)

All DB operations use an in-memory SQLite database with StaticPool so
there are no thread-safety issues with the TestClient.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from roleprint.api.deps import get_session
from roleprint.api.main import app
from roleprint.db.base import Base
from roleprint.db.models import (
    JobPosting,
    ProcessedPosting,
    SkillTrend,
    Subscriber,
)
from roleprint.scheduler.jobs import (
    generate_digest_data,
    render_digest_html,
    weekly_digest_job,
)

# ── Shared SQLite engine ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture(scope="module")
def db(engine):
    s = Session(engine)
    yield s
    s.close()


# ── Seed helpers ──────────────────────────────────────────────────────────────

WEEK = date(2026, 4, 13)       # a Monday
PREV_WEEK = WEEK - timedelta(weeks=1)
SCRAPED_AT = datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def seeded_db(db):
    """Populate DB with minimal deterministic data."""
    jp = JobPosting(
        id=uuid.uuid4(),
        title="Data Engineer",
        company="Acme",
        location="London",
        url="https://example.com/j/1",
        source="reed",
        role_category="data engineer",
        raw_text="Immediately hiring! Python and Spark skills required urgently.",
        scraped_at=SCRAPED_AT,
        is_processed=True,
    )
    db.add(jp)
    db.flush()

    pp = ProcessedPosting(
        id=uuid.uuid4(),
        posting_id=jp.id,
        skills_extracted=["python", "spark"],
        sentiment_score=0.15,
        topics={"topic_id": 0, "topic_label": "data_eng", "probability": 0.8},
        entities={},
    )
    db.add(pp)

    # Current week skill trends
    for skill, count, pct in [("python", 12, 0.8), ("spark", 8, 0.55)]:
        db.add(SkillTrend(
            id=uuid.uuid4(),
            skill=skill,
            role_category="data engineer",
            week_start=WEEK,
            mention_count=count,
            pct_of_postings=pct,
        ))

    # Previous week (python only — spark is "new")
    db.add(SkillTrend(
        id=uuid.uuid4(),
        skill="python",
        role_category="data engineer",
        week_start=PREV_WEEK,
        mention_count=8,
        pct_of_postings=0.55,
    ))

    db.commit()
    return db


# ── Subscriber model ──────────────────────────────────────────────────────────

class TestSubscriberModel:
    def test_create_subscriber(self, db):
        sub = Subscriber(email="alice@example.com", role_preferences=["data engineer"])
        db.add(sub)
        db.flush()
        assert sub.id is not None
        assert sub.is_active is True
        assert len(sub.unsubscribe_token) > 10
        db.rollback()

    def test_unsubscribe_token_is_unique(self, db):
        s1 = Subscriber(email="b1@example.com")
        s2 = Subscriber(email="b2@example.com")
        db.add_all([s1, s2])
        db.flush()
        assert s1.unsubscribe_token != s2.unsubscribe_token
        db.rollback()

    def test_default_role_preferences_empty(self, db):
        sub = Subscriber(email="c1@example.com")
        db.add(sub)
        db.flush()
        assert sub.role_preferences == []
        db.rollback()


# ── API client fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(seeded_db):
    def override():
        yield seeded_db

    app.dependency_overrides[get_session] = override
    with patch("roleprint.api.cache.get", return_value=None), \
         patch("roleprint.api.cache.set"), \
         patch("roleprint.api.cache.is_available", return_value=False):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    app.dependency_overrides.clear()


# ── POST /api/subscribe ───────────────────────────────────────────────────────

class TestSubscribeEndpoint:
    def test_subscribe_new_email(self, client):
        resp = client.post("/api/subscribe", json={"email": "test1@example.com"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "subscribed"
        assert body["email"] == "test1@example.com"

    def test_subscribe_with_role_preferences(self, client):
        resp = client.post(
            "/api/subscribe",
            json={"email": "test2@example.com", "role_preferences": ["data engineer"]},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "subscribed"

    def test_subscribe_existing_active_updates_prefs(self, client):
        resp = client.post(
            "/api/subscribe",
            json={"email": "test1@example.com", "role_preferences": ["ml engineer"]},
        )
        # Should be 200 or 201 — status updated
        assert resp.status_code in (200, 201)
        assert resp.json()["status"] == "updated"

    def test_subscribe_reactivates_inactive(self, client, seeded_db):
        # Manually deactivate then resubscribe
        from sqlalchemy import select
        sub = seeded_db.scalar(
            select(Subscriber).where(Subscriber.email == "test2@example.com")
        )
        if sub:
            sub.is_active = False
            seeded_db.commit()

        resp = client.post(
            "/api/subscribe",
            json={"email": "test2@example.com"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["status"] in ("reactivated", "subscribed")

    def test_subscribe_invalid_email_rejected(self, client):
        resp = client.post("/api/subscribe", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_subscribe_missing_email_rejected(self, client):
        resp = client.post("/api/subscribe", json={})
        assert resp.status_code == 422


# ── GET /api/unsubscribe ──────────────────────────────────────────────────────

class TestUnsubscribeEndpoint:
    def _get_token(self, db) -> str:
        """Helper: return the unsubscribe_token for a subscribed address."""
        from sqlalchemy import select
        sub = db.scalar(
            select(Subscriber).where(Subscriber.email == "test1@example.com")
        )
        return sub.unsubscribe_token if sub else "unknown"

    def test_valid_token_unsubscribes(self, client, seeded_db):
        token = self._get_token(seeded_db)
        resp = client.get(f"/api/unsubscribe?token={token}")
        assert resp.status_code == 200
        assert "Unsubscribed" in resp.text

        # Confirm DB flag flipped
        from sqlalchemy import select
        sub = seeded_db.scalar(
            select(Subscriber).where(Subscriber.email == "test1@example.com")
        )
        assert sub is None or not sub.is_active

    def test_invalid_token_returns_html(self, client):
        resp = client.get("/api/unsubscribe?token=deadbeef1234")
        assert resp.status_code == 200
        assert "Invalid" in resp.text or "Not Found" in resp.text

    def test_missing_token_returns_422(self, client):
        resp = client.get("/api/unsubscribe")
        assert resp.status_code == 422


# ── generate_digest_data ──────────────────────────────────────────────────────

class TestGenerateDigestData:
    def test_returns_none_when_no_data(self, db):
        # Fresh empty session
        eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(eng)
        with Session(eng) as empty_session:
            result = generate_digest_data(empty_session)
        assert result is None

    def test_returns_dict_with_keys(self, seeded_db):
        result = generate_digest_data(seeded_db)
        assert result is not None
        for key in ("week", "total_postings_this_week", "top_skills", "emerging", "sentiment_by_role"):
            assert key in result, f"Missing key: {key}"

    def test_top_skills_ordered_by_count(self, seeded_db):
        result = generate_digest_data(seeded_db)
        counts = [s["mention_count"] for s in result["top_skills"]]
        assert counts == sorted(counts, reverse=True)

    def test_top_skills_have_change_pct(self, seeded_db):
        result = generate_digest_data(seeded_db)
        for skill in result["top_skills"]:
            assert "change_pct" in skill
            assert isinstance(skill["change_pct"], float)

    def test_python_wow_change_calculated(self, seeded_db):
        result = generate_digest_data(seeded_db)
        python_row = next(
            (s for s in result["top_skills"] if s["skill"] == "python"), None
        )
        assert python_row is not None
        # 12 current / 8 prev → 50% increase
        assert python_row["change_pct"] == pytest.approx(50.0, abs=0.5)

    def test_spark_new_skill_100_pct(self, seeded_db):
        result = generate_digest_data(seeded_db)
        spark_row = next(
            (s for s in result["top_skills"] if s["skill"] == "spark"), None
        )
        assert spark_row is not None
        # No prev week row → 100% change
        assert spark_row["change_pct"] == pytest.approx(100.0, abs=0.1)

    def test_week_string_matches_latest(self, seeded_db):
        result = generate_digest_data(seeded_db)
        assert result["week"] == str(WEEK)


# ── render_digest_html ────────────────────────────────────────────────────────

class TestRenderDigestHtml:
    def _context(self):
        return {
            "week": "2026-04-13",
            "total_postings_this_week": 42,
            "top_skills": [
                {"skill": "python", "role_category": "data engineer",
                 "mention_count": 12, "prev_count": 8, "change_pct": 50.0},
            ],
            "emerging": [
                {"skill": "dbt", "role_category": "data engineer",
                 "growth_pct": 200.0, "current_count": 6, "old_count": 2,
                 "current_week": "2026-04-13"},
            ],
            "sentiment_by_role": [
                {"role_category": "data engineer", "avg_sentiment": 0.15,
                 "posting_count": 12, "urgency_total": 4},
            ],
        }

    def test_renders_without_error(self):
        html = render_digest_html(self._context(), subscriber_token="abc123")
        assert isinstance(html, str)
        assert len(html) > 500

    def test_contains_week(self):
        html = render_digest_html(self._context(), subscriber_token="abc123")
        assert "2026-04-13" in html

    def test_contains_top_skill(self):
        html = render_digest_html(self._context(), subscriber_token="abc123")
        assert "python" in html

    def test_contains_emerging_skill(self):
        html = render_digest_html(self._context(), subscriber_token="abc123")
        assert "dbt" in html

    def test_contains_unsubscribe_token(self):
        html = render_digest_html(self._context(), subscriber_token="mytoken42")
        assert "mytoken42" in html

    def test_contains_sentiment_row(self):
        html = render_digest_html(self._context(), subscriber_token="abc123")
        assert "data engineer" in html

    def test_no_template_errors_empty_lists(self):
        ctx = {**self._context(), "top_skills": [], "emerging": [], "sentiment_by_role": []}
        html = render_digest_html(ctx, subscriber_token="tok")
        assert "No skill data" in html or "No emerging" in html or "No sentiment" in html

    def test_change_arrow_up(self):
        html = render_digest_html(self._context(), subscriber_token="tok")
        assert "▲" in html  # positive change_pct

    def test_change_arrow_down(self):
        ctx = {**self._context(), "top_skills": [
            {"skill": "python", "role_category": "data engineer",
             "mention_count": 5, "prev_count": 10, "change_pct": -50.0},
        ]}
        html = render_digest_html(ctx, subscriber_token="tok")
        assert "▼" in html


# ── weekly_digest_job ─────────────────────────────────────────────────────────

class TestWeeklyDigestJob:
    def _add_subscriber(self, db, email: str, active: bool = True) -> Subscriber:
        from sqlalchemy import select
        existing = db.scalar(select(Subscriber).where(Subscriber.email == email))
        if existing:
            existing.is_active = active
            db.commit()
            return existing
        sub = Subscriber(email=email, is_active=active)
        db.add(sub)
        db.commit()
        return sub

    def test_sends_to_active_subscribers(self, seeded_db):
        self._add_subscriber(seeded_db, "digest_recv@example.com", active=True)
        calls = []
        mock_send = lambda to, subj, html: calls.append(to)

        with patch("roleprint.scheduler.jobs.SessionLocal", return_value=seeded_db):
            result = weekly_digest_job(send_fn=mock_send)

        assert result["sent"] >= 1
        assert "digest_recv@example.com" in calls

    def test_skips_inactive_subscribers(self, seeded_db):
        self._add_subscriber(seeded_db, "inactive_test@example.com", active=False)
        calls = []
        mock_send = lambda to, subj, html: calls.append(to)

        with patch("roleprint.scheduler.jobs.SessionLocal", return_value=seeded_db):
            result = weekly_digest_job(send_fn=mock_send)

        assert "inactive_test@example.com" not in calls

    def test_counts_failures(self, seeded_db):
        self._add_subscriber(seeded_db, "fail_test@example.com", active=True)

        def failing_send(to, subj, html):
            if to == "fail_test@example.com":
                raise RuntimeError("SendGrid error")

        with patch("roleprint.scheduler.jobs.SessionLocal", return_value=seeded_db):
            result = weekly_digest_job(send_fn=failing_send)

        assert result["failed"] >= 1

    def test_no_data_returns_zero_counts(self):
        eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(eng)
        empty_session = Session(eng)

        with patch("roleprint.scheduler.jobs.SessionLocal", return_value=empty_session):
            result = weekly_digest_job(send_fn=lambda *a: None)

        empty_session.close()
        assert result == {"sent": 0, "skipped": 0, "failed": 0}

    def test_role_preferences_filter_skips_non_matching(self, seeded_db):
        # Subscriber only wants "ai researcher" — none in test data
        sub = self._add_subscriber(seeded_db, "filtered@example.com", active=True)
        sub.role_preferences = ["ai researcher"]
        seeded_db.commit()

        calls = []
        mock_send = lambda to, subj, html: calls.append(to)

        with patch("roleprint.scheduler.jobs.SessionLocal", return_value=seeded_db):
            result = weekly_digest_job(send_fn=mock_send)

        assert "filtered@example.com" not in calls


# ── build_scheduler ───────────────────────────────────────────────────────────

class TestBuildScheduler:
    def test_three_jobs_registered(self):
        from roleprint.scheduler.main import build_scheduler
        scheduler = build_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {"scrape_job", "process_job", "weekly_digest_job"}
        # BlockingScheduler must be started before shutdown — just verify jobs

    def test_digest_job_is_cron(self):
        from apscheduler.triggers.cron import CronTrigger
        from roleprint.scheduler.main import build_scheduler
        scheduler = build_scheduler()
        digest = scheduler.get_job("weekly_digest_job")
        assert isinstance(digest.trigger, CronTrigger)

    def test_scrape_and_process_jobs_registered(self):
        from roleprint.scheduler.main import build_scheduler
        scheduler = build_scheduler()
        assert scheduler.get_job("scrape_job") is not None
        assert scheduler.get_job("process_job") is not None

    def test_custom_scrape_interval_env(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_INTERVAL_HRS", "12")
        monkeypatch.setenv("DIGEST_HOUR", "9")
        import importlib
        from roleprint.scheduler import main as sched_main
        importlib.reload(sched_main)
        scheduler = sched_main.build_scheduler()
        jobs = {j.id: j for j in scheduler.get_jobs()}
        assert "scrape_job" in jobs
        assert "process_job" in jobs
        assert "weekly_digest_job" in jobs
