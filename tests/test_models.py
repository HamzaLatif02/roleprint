"""Unit tests for ORM models and query helpers (SQLite in-memory, no Postgres needed)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from roleprint.db.base import Base
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend
from roleprint.db.queries import (
    get_posting_with_analysis,
    get_recent_postings_by_role,
    get_skill_trends_by_role,
    get_top_skills_overall,
    get_unprocessed_postings,
)


@pytest.fixture(scope="module")
def session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(scope="module")
def seed(session: Session):
    """Insert a minimal set of rows used across multiple tests."""
    now = datetime.now(tz=timezone.utc)
    p1 = JobPosting(
        source="reed",
        role_category="data analyst",
        title="Data Analyst",
        company="Acme",
        location="London",
        raw_text="Python SQL Tableau",
        url="https://example.com/1",
        scraped_at=now,
        is_processed=False,
    )
    p2 = JobPosting(
        source="linkedin",
        role_category="ml engineer",
        title="ML Engineer",
        company="BetaCo",
        location="Remote",
        raw_text="PyTorch Kubernetes",
        url="https://example.com/2",
        scraped_at=now,
        is_processed=True,
    )
    session.add_all([p1, p2])
    session.flush()

    proc = ProcessedPosting(
        posting_id=p2.id,
        skills_extracted=["PyTorch", "Kubernetes"],
        sentiment_score=0.4,
        topics={"topic_0": ["ml", "model"]},
        entities={"tools": ["PyTorch"], "locations": ["Remote"]},
        processed_at=now,
    )
    trend = SkillTrend(
        skill="python",
        role_category="data analyst",
        week_start=date(2026, 4, 7),
        mention_count=42,
        pct_of_postings=0.65,
    )
    session.add_all([proc, trend])
    session.commit()
    return {"p1": p1, "p2": p2, "proc": proc, "trend": trend}


def test_job_posting_repr(seed):
    assert "Data Analyst" in repr(seed["p1"])


def test_get_unprocessed_postings(session, seed):
    rows = get_unprocessed_postings(session)
    assert all(not r.is_processed for r in rows)
    assert any(r.url == "https://example.com/1" for r in rows)


def test_get_unprocessed_postings_role_filter(session, seed):
    rows = get_unprocessed_postings(session, role_category="ml engineer")
    # p2 is processed, so should not appear
    assert len(rows) == 0


def test_get_skill_trends_by_role(session, seed):
    rows = get_skill_trends_by_role(session, "data analyst")
    assert len(rows) >= 1
    assert rows[0].skill == "python"


def test_get_skill_trends_since_filter(session, seed):
    future = date(2030, 1, 1)
    rows = get_skill_trends_by_role(session, "data analyst", since=future)
    assert rows == []


def test_get_posting_with_analysis(session, seed):
    result = get_posting_with_analysis(session, seed["p2"].id)
    assert result is not None
    assert result.processed is not None
    assert "PyTorch" in result.processed.skills_extracted


def test_get_posting_with_analysis_missing(session):
    assert get_posting_with_analysis(session, uuid.uuid4()) is None


def test_get_recent_postings_by_role(session, seed):
    rows = get_recent_postings_by_role(session, "data analyst")
    assert any(r.title == "Data Analyst" for r in rows)


def test_get_top_skills_overall(session, seed):
    rows = get_top_skills_overall(session, since=date(2026, 1, 1))
    assert len(rows) >= 1
    assert rows[0].mention_count >= 1
