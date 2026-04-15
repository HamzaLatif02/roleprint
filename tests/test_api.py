"""Integration tests for the FastAPI application.

All tests run against an in-memory SQLite database.  The ``get_session``
FastAPI dependency is overridden so no real Postgres is needed.  Redis is
patched at the ``cache`` module level so endpoints exercise the full code
path without requiring a running Redis server.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from roleprint.api.deps import get_session
from roleprint.api.main import app
from roleprint.db.base import Base
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend

# ── Fixtures ──────────────────────────────────────────────────────────────────


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
def db_session(engine):
    s = Session(engine)
    yield s
    s.close()


@pytest.fixture(scope="module")
def seeded_session(db_session):
    """Populate the in-memory DB with a small deterministic dataset."""
    week = date(2026, 4, 13)  # a Monday
    prev_week = date(2026, 4, 6)
    scraped = datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)

    # Two job postings in different roles
    jp1 = JobPosting(
        id=uuid.uuid4(),
        title="Data Analyst",
        company="Acme Corp",
        location="London",
        url="https://example.com/job/1",
        source="reed",
        role_category="data analyst",
        raw_text="Looking for Python and SQL skills",
        scraped_at=scraped,
        is_processed=True,
    )
    jp2 = JobPosting(
        id=uuid.uuid4(),
        title="ML Engineer",
        company="Beta Inc",
        location="Remote",
        url="https://example.com/job/2",
        source="remoteok",
        role_category="ml engineer",
        raw_text="Immediate opening! PyTorch experience required urgently.",
        scraped_at=scraped,
        is_processed=True,
    )
    jp3 = JobPosting(
        id=uuid.uuid4(),
        title="Backend Engineer",
        company="Gamma Ltd",
        location="New York",
        url="https://example.com/job/3",
        source="reed",
        role_category="data analyst",
        raw_text="SQL and dbt experience needed",
        scraped_at=scraped,
        is_processed=False,
    )
    db_session.add_all([jp1, jp2, jp3])
    db_session.flush()

    # Processed postings for jp1 and jp2
    pp1 = ProcessedPosting(
        id=uuid.uuid4(),
        posting_id=jp1.id,
        skills_extracted=["python", "sql"],
        sentiment_score=0.25,
        topics={"topic_id": 0, "topic_label": "data_analysis", "probability": 0.8},
        entities={"ORG": ["Acme Corp"]},
    )
    pp2 = ProcessedPosting(
        id=uuid.uuid4(),
        posting_id=jp2.id,
        skills_extracted=["pytorch", "python"],
        sentiment_score=-0.10,
        topics={"topic_id": 1, "topic_label": "machine_learning", "probability": 0.9},
        entities={},
    )
    db_session.add_all([pp1, pp2])
    db_session.flush()

    # Skill trends: current and previous week for data analyst
    trends = [
        SkillTrend(
            id=uuid.uuid4(),
            skill="python",
            role_category="data analyst",
            week_start=week,
            mention_count=10,
            pct_of_postings=0.8,
        ),
        SkillTrend(
            id=uuid.uuid4(),
            skill="sql",
            role_category="data analyst",
            week_start=week,
            mention_count=8,
            pct_of_postings=0.64,
        ),
        SkillTrend(
            id=uuid.uuid4(),
            skill="python",
            role_category="data analyst",
            week_start=prev_week,
            mention_count=6,
            pct_of_postings=0.5,
        ),
        SkillTrend(
            id=uuid.uuid4(),
            skill="pytorch",
            role_category="ml engineer",
            week_start=week,
            mention_count=5,
            pct_of_postings=0.7,
        ),
    ]
    db_session.add_all(trends)
    db_session.commit()

    return db_session


@pytest.fixture(scope="module")
def client(seeded_session):
    """TestClient with DB dependency overridden and Redis disabled."""

    def override_session():
        yield seeded_session

    app.dependency_overrides[get_session] = override_session

    # Patch cache so nothing tries to reach Redis
    with patch("roleprint.api.cache.get", return_value=None), \
         patch("roleprint.api.cache.set"), \
         patch("roleprint.api.cache.is_available", return_value=False):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ── /health ───────────────────────────────────────────────────────────────────


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
    assert body["redis"] == "unavailable"
    assert "version" in body


# ── /api/roles ────────────────────────────────────────────────────────────────


def test_roles_returns_list(client):
    resp = client.get("/api/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_roles_fields(client):
    resp = client.get("/api/roles")
    item = resp.json()[0]
    assert "role_category" in item
    assert "posting_count" in item
    assert "processed_count" in item
    assert "unprocessed_count" in item


def test_roles_counts_add_up(client):
    resp = client.get("/api/roles")
    for item in resp.json():
        assert item["posting_count"] == item["processed_count"] + item["unprocessed_count"]


# ── /api/skills/trending ─────────────────────────────────────────────────────


def test_trending_returns_list(client):
    resp = client.get("/api/skills/trending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_trending_filter_by_role(client):
    resp = client.get("/api/skills/trending?role_category=data+analyst")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["role_category"] == "data analyst" for item in data)


def test_trending_fields(client):
    resp = client.get("/api/skills/trending?role_category=data+analyst")
    item = resp.json()[0]
    for field in ("skill", "role_category", "mention_count", "pct_of_postings", "wow_change", "is_rising"):
        assert field in item


def test_trending_wow_change_calculated(client):
    # python: 10 current vs 6 prev → 66.7% increase
    resp = client.get("/api/skills/trending?role_category=data+analyst")
    data = resp.json()
    python_row = next((r for r in data if r["skill"] == "python"), None)
    assert python_row is not None
    assert python_row["wow_change"] == pytest.approx(66.7, abs=0.2)
    assert python_row["is_rising"] is True


# ── /api/skills/compare ───────────────────────────────────────────────────────


def test_compare_two_roles(client):
    resp = client.get("/api/skills/compare?roles=data+analyst,ml+engineer")
    assert resp.status_code == 200
    body = resp.json()
    assert "overlap_pct" in body
    assert "similarity_score" in body
    assert "shared_skills" in body
    assert "role_profiles" in body


def test_compare_requires_two_roles(client):
    resp = client.get("/api/skills/compare?roles=data+analyst")
    assert resp.status_code == 422


# ── /api/skills/emerging ─────────────────────────────────────────────────────


def test_emerging_returns_list(client):
    resp = client.get("/api/skills/emerging")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── /api/topics ───────────────────────────────────────────────────────────────


def test_topics_returns_list(client):
    resp = client.get("/api/topics")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_topics_fields(client):
    resp = client.get("/api/topics")
    data = resp.json()
    if data:
        item = data[0]
        for field in ("topic_id", "topic_label", "posting_count", "avg_probability"):
            assert field in item


def test_topics_filter_by_role(client):
    resp = client.get("/api/topics?role_category=data+analyst")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── /api/sentiment/timeline ───────────────────────────────────────────────────


def test_sentiment_timeline_returns_list(client):
    resp = client.get("/api/sentiment/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_sentiment_timeline_sorted_chronologically(client):
    resp = client.get("/api/sentiment/timeline")
    weeks = [item["week"] for item in resp.json()]
    assert weeks == sorted(weeks)


def test_sentiment_timeline_fields(client):
    resp = client.get("/api/sentiment/timeline")
    data = resp.json()
    if data:
        item = data[0]
        for field in ("week", "avg_sentiment", "urgency_score", "posting_count"):
            assert field in item


# ── /api/postings/recent ─────────────────────────────────────────────────────


def test_recent_postings_default_limit(client):
    resp = client.get("/api/postings/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 20


def test_recent_postings_fields(client):
    resp = client.get("/api/postings/recent")
    data = resp.json()
    assert len(data) > 0
    item = data[0]
    for field in ("id", "title", "company", "location", "url", "source",
                  "role_category", "scraped_at", "skills", "topics", "entities"):
        assert field in item


def test_recent_postings_filter_by_role(client):
    resp = client.get("/api/postings/recent?role_category=data+analyst")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["role_category"] == "data analyst" for item in data)


def test_recent_postings_limit_param(client):
    resp = client.get("/api/postings/recent?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_recent_postings_limit_too_large(client):
    resp = client.get("/api/postings/recent?limit=999")
    assert resp.status_code == 422


# ── /api/stats/summary ────────────────────────────────────────────────────────


def test_stats_summary_fields(client):
    resp = client.get("/api/stats/summary")
    assert resp.status_code == 200
    body = resp.json()
    for field in ("total_postings", "processed_postings", "unprocessed_postings",
                  "roles_tracked", "weeks_of_data", "sources"):
        assert field in body


def test_stats_summary_counts(client):
    resp = client.get("/api/stats/summary")
    body = resp.json()
    assert body["total_postings"] == 3
    assert body["processed_postings"] == 2
    assert body["unprocessed_postings"] == 1
    assert body["roles_tracked"] == 2


def test_stats_summary_sources(client):
    resp = client.get("/api/stats/summary")
    sources = resp.json()["sources"]
    assert "reed" in sources
    assert "remoteok" in sources


# ── OpenAPI schema ────────────────────────────────────────────────────────────


def test_openapi_schema_accessible(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Roleprint API"


def test_docs_accessible(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
