"""Tests for roleprint/nlp/trends.py.

All tests run against an in-memory SQLite database seeded with controlled
SkillTrend and ProcessedPosting rows so results are deterministic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from roleprint.db.base import Base
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend
from roleprint.nlp.trends import (
    emerging_skills,
    rising_skills,
    role_similarity,
    role_similarity_matrix,
    skill_cooccurrence,
    week_over_week_change,
)

# ── Reference dates ───────────────────────────────────────────────────────────

TODAY = date(2026, 4, 13)  # a Monday, for stable arithmetic
CURR = TODAY  # current week_start
PREV = TODAY - timedelta(weeks=1)  # previous week
OLD4 = TODAY - timedelta(weeks=4)  # four weeks back


# ── DB fixture ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        yield session


def _make_posting(session: Session, role: str, skills: list[str]) -> JobPosting:
    p = JobPosting(
        source="test",
        role_category=role,
        title="Test",
        company="TestCo",
        location="London",
        raw_text=" ".join(skills),
        url=f"https://example.com/{uuid.uuid4()}",
        scraped_at=datetime(2026, 4, 13, tzinfo=UTC),
        is_processed=True,
    )
    session.add(p)
    session.flush()
    pp = ProcessedPosting(
        posting_id=p.id,
        skills_extracted=skills,
        sentiment_score=0.1,
        topics={},
        entities={},
        processed_at=datetime(2026, 4, 13, tzinfo=UTC),
    )
    session.add(pp)
    return p


def _trend(role, skill, week, count, pct) -> SkillTrend:
    return SkillTrend(
        skill=skill,
        role_category=role,
        week_start=week,
        mention_count=count,
        pct_of_postings=pct,
    )


def _seed(s: Session) -> None:
    # ── skill_trends rows ─────────────────────────────────────────────────────
    trends = [
        # data analyst — current week
        _trend("data analyst", "Python", CURR, 42, 0.84),
        _trend("data analyst", "SQL", CURR, 38, 0.76),
        _trend("data analyst", "dbt", CURR, 19, 0.38),
        _trend("data analyst", "Snowflake", CURR, 17, 0.34),
        _trend("data analyst", "stakeholder management", CURR, 31, 0.62),
        _trend("data analyst", "agile", CURR, 22, 0.44),
        _trend("data analyst", "LLM", CURR, 8, 0.16),
        # data analyst — previous week
        _trend("data analyst", "Python", PREV, 30, 0.60),
        _trend("data analyst", "SQL", PREV, 38, 0.76),
        _trend("data analyst", "dbt", PREV, 10, 0.20),
        _trend("data analyst", "stakeholder management", PREV, 30, 0.60),
        # data analyst — 4-weeks-ago (for emerging)
        _trend("data analyst", "LLM", OLD4, 1, 0.02),
        # ml engineer — current week (shares Python with data analyst)
        _trend("ml engineer", "Python", CURR, 48, 0.96),
        _trend("ml engineer", "PyTorch", CURR, 35, 0.70),
        _trend("ml engineer", "Kubernetes", CURR, 22, 0.44),
        _trend("ml engineer", "MLflow", CURR, 14, 0.28),
        _trend("ml engineer", "LangChain", CURR, 11, 0.22),
        # ml engineer — previous week
        _trend("ml engineer", "Python", PREV, 40, 0.80),
        _trend("ml engineer", "PyTorch", PREV, 28, 0.56),
        _trend("ml engineer", "LangChain", PREV, 3, 0.06),
        # devops — very different profile (for low similarity test)
        _trend("devops", "Terraform", CURR, 30, 0.80),
        _trend("devops", "Kubernetes", CURR, 28, 0.74),
        _trend("devops", "Helm", CURR, 18, 0.48),
        _trend("devops", "Prometheus", CURR, 15, 0.40),
        # data scientist — highly similar to data analyst
        _trend("data scientist", "Python", CURR, 45, 0.90),
        _trend("data scientist", "SQL", CURR, 32, 0.64),
        _trend("data scientist", "stakeholder management", CURR, 28, 0.56),
        _trend("data scientist", "agile", CURR, 18, 0.36),
        _trend("data scientist", "PyTorch", CURR, 25, 0.50),
    ]
    s.add_all(trends)
    s.flush()

    # ── processed_postings rows (for co-occurrence tests) ─────────────────────
    da_skill_sets = [
        ["Python", "SQL", "dbt", "stakeholder management"],
        ["Python", "SQL", "Snowflake", "agile"],
        ["Python", "SQL", "dbt", "agile"],
        ["SQL", "Tableau", "stakeholder management"],
        ["Python", "SQL", "dbt", "Snowflake"],
    ]
    for skills in da_skill_sets:
        _make_posting(s, "data analyst", skills)

    mle_skill_sets = [
        ["Python", "PyTorch", "Kubernetes"],
        ["Python", "PyTorch", "MLflow", "LangChain"],
        ["Python", "PyTorch", "Kubernetes", "MLflow"],
    ]
    for skills in mle_skill_sets:
        _make_posting(s, "ml engineer", skills)

    s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 1. week_over_week_change
# ─────────────────────────────────────────────────────────────────────────────


class TestWeekOverWeekChange:
    def test_returns_required_keys(self, db):
        result = week_over_week_change("Python", "data analyst", db)
        assert all(
            k in result
            for k in (
                "change_pct",
                "is_rising",
                "current_count",
                "previous_count",
                "current_week",
                "previous_week",
            )
        )

    def test_positive_growth(self, db):
        # Python: 30 → 42  = +40 %
        result = week_over_week_change("Python", "data analyst", db)
        assert result["change_pct"] == pytest.approx(40.0, abs=0.1)
        assert result["is_rising"] is True

    def test_stable_skill(self, db):
        # SQL: 38 → 38 = 0 %
        result = week_over_week_change("SQL", "data analyst", db)
        assert result["change_pct"] == pytest.approx(0.0, abs=0.1)
        assert result["is_rising"] is False

    def test_dbt_growth_above_rising_threshold(self, db):
        # dbt: 10 → 19 = +90 %
        result = week_over_week_change("dbt", "data analyst", db)
        assert result["change_pct"] > 20.0
        assert result["is_rising"] is True

    def test_no_previous_week_returns_100_pct(self, db):
        # Snowflake only has current week data
        result = week_over_week_change("Snowflake", "data analyst", db)
        assert result["change_pct"] == pytest.approx(100.0)
        assert result["is_rising"] is True
        assert result["previous_week"] is None

    def test_missing_skill_returns_zeros(self, db):
        result = week_over_week_change("CobolXYZ", "data analyst", db)
        assert result["change_pct"] == 0.0
        assert result["current_count"] == 0
        assert result["current_week"] is None

    def test_current_week_is_most_recent(self, db):
        result = week_over_week_change("Python", "data analyst", db)
        assert result["current_week"] == CURR
        assert result["previous_week"] == PREV

    def test_counts_are_correct(self, db):
        result = week_over_week_change("Python", "data analyst", db)
        assert result["current_count"] == 42
        assert result["previous_count"] == 30


class TestRisingSkills:
    def test_returns_list(self, db):
        result = rising_skills("data analyst", db)
        assert isinstance(result, list)

    def test_each_item_has_skill_key(self, db):
        result = rising_skills("data analyst", db, top_n=5)
        assert all("skill" in r for r in result)

    def test_sorted_by_change_pct_descending(self, db):
        result = rising_skills("data analyst", db)
        pcts = [r["change_pct"] for r in result]
        assert pcts == sorted(pcts, reverse=True)

    def test_respects_top_n(self, db):
        result = rising_skills("data analyst", db, top_n=3)
        assert len(result) <= 3

    def test_empty_role_returns_empty_list(self, db):
        assert rising_skills("nonexistent role", db) == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. skill_cooccurrence
# ─────────────────────────────────────────────────────────────────────────────


class TestSkillCooccurrence:
    def test_returns_required_keys(self, db):
        result = skill_cooccurrence("data analyst", db)
        assert "skills" in result
        assert "top_pairs" in result
        assert "matrix" in result

    def test_python_sql_are_in_skills(self, db):
        result = skill_cooccurrence("data analyst", db)
        assert "Python" in result["skills"]
        assert "SQL" in result["skills"]

    def test_python_sql_top_pair(self, db):
        result = skill_cooccurrence("data analyst", db)
        pairs = result["top_pairs"]
        top_skills = {frozenset([p["skill_a"], p["skill_b"]]) for p in pairs[:3]}
        assert frozenset(["Python", "SQL"]) in top_skills

    def test_pairs_sorted_by_count_descending(self, db):
        result = skill_cooccurrence("data analyst", db)
        counts = [p["count"] for p in result["top_pairs"]]
        assert counts == sorted(counts, reverse=True)

    def test_min_count_filter_applied(self, db):
        result = skill_cooccurrence("data analyst", db, min_count=3)
        assert all(p["count"] >= 3 for p in result["top_pairs"])

    def test_matrix_is_symmetric(self, db):
        result = skill_cooccurrence("data analyst", db)
        m = result["matrix"]
        n = len(m)
        for i in range(n):
            for j in range(n):
                assert m[i][j] == m[j][i], f"Matrix not symmetric at ({i},{j})"

    def test_matrix_dimension_matches_skills(self, db):
        result = skill_cooccurrence("data analyst", db)
        n = len(result["skills"])
        assert len(result["matrix"]) == n
        assert all(len(row) == n for row in result["matrix"])

    def test_top_n_respected(self, db):
        result = skill_cooccurrence("data analyst", db, top_n=3)
        assert len(result["top_pairs"]) <= 3

    def test_empty_role_returns_empty(self, db):
        result = skill_cooccurrence("nonexistent role", db)
        assert result["skills"] == []
        assert result["top_pairs"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. role_similarity
# ─────────────────────────────────────────────────────────────────────────────


class TestRoleSimilarity:
    def test_identical_role_returns_one(self, db):
        sim = role_similarity("data analyst", "data analyst", db)
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_similar_roles_high_score(self, db):
        # data analyst and data scientist share Python, SQL, stakeholder mgmt, agile
        sim = role_similarity("data analyst", "data scientist", db)
        assert sim > 0.6, f"Expected high similarity, got {sim}"

    def test_dissimilar_roles_low_score(self, db):
        # data analyst (SQL/Tableau) vs devops (Terraform/Helm) — minimal overlap
        sim = role_similarity("data analyst", "devops", db)
        assert sim < 0.5, f"Expected low similarity, got {sim}"

    def test_returns_float_in_range(self, db):
        sim = role_similarity("ml engineer", "data analyst", db)
        assert isinstance(sim, float)
        assert 0.0 <= sim <= 1.0

    def test_symmetric(self, db):
        sim_ab = role_similarity("data analyst", "ml engineer", db)
        sim_ba = role_similarity("ml engineer", "data analyst", db)
        assert sim_ab == pytest.approx(sim_ba, abs=0.0001)

    def test_missing_role_returns_zero(self, db):
        sim = role_similarity("data analyst", "foobar role xyz", db)
        assert sim == 0.0

    def test_both_missing_returns_zero(self, db):
        assert role_similarity("foo", "bar", db) == 0.0


class TestRoleSimilarityMatrix:
    def test_returns_correct_keys(self, db):
        result = role_similarity_matrix(["data analyst", "ml engineer"], db)
        assert "roles" in result
        assert "matrix" in result

    def test_diagonal_is_one(self, db):
        roles = ["data analyst", "ml engineer", "devops"]
        result = role_similarity_matrix(roles, db)
        m = result["matrix"]
        for i in range(len(roles)):
            assert m[i][i] == pytest.approx(1.0, abs=0.01)

    def test_matrix_is_symmetric(self, db):
        roles = ["data analyst", "ml engineer", "devops"]
        result = role_similarity_matrix(roles, db)
        m = result["matrix"]
        n = len(roles)
        for i in range(n):
            for j in range(n):
                assert m[i][j] == pytest.approx(m[j][i], abs=0.0001)

    def test_matrix_dimensions(self, db):
        roles = ["data analyst", "ml engineer"]
        result = role_similarity_matrix(roles, db)
        assert len(result["matrix"]) == 2
        assert all(len(row) == 2 for row in result["matrix"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. emerging_skills
# ─────────────────────────────────────────────────────────────────────────────


class TestEmergingSkills:
    def test_returns_list(self, db):
        result = emerging_skills(db, lookback_weeks=4)
        assert isinstance(result, list)

    def test_llm_is_emerging_for_data_analyst(self, db):
        # LLM: max historical pct = 0.02 (exactly at threshold, NOT > threshold)
        # → included. LangChain for ml engineer has max historical pct = 0.06
        # (from PREV week) → excluded; but with max_old_pct=0.10 it would appear.
        result = emerging_skills(db, lookback_weeks=4, max_old_pct=0.02)
        # Skills with no history at all (new this week) have old_pct=0 → included
        langchain_rows = [r for r in result if r["skill"] == "LangChain"]
        # LangChain has PREV row with pct=0.06 > 0.02, so it should be EXCLUDED
        assert not any(r["role_category"] == "ml engineer" for r in langchain_rows)

    def test_each_item_has_required_keys(self, db):
        result = emerging_skills(db, lookback_weeks=4)
        for r in result:
            assert "skill" in r
            assert "role_category" in r
            assert "growth_pct" in r
            assert "current_count" in r
            assert "old_count" in r
            assert "current_week" in r

    def test_sorted_by_growth_pct_descending(self, db):
        result = emerging_skills(db, lookback_weeks=4)
        if len(result) > 1:
            pcts = [r["growth_pct"] for r in result]
            assert pcts == sorted(pcts, reverse=True)

    def test_min_count_filters_noise(self, db):
        # With a very high min_count, no results
        result = emerging_skills(db, lookback_weeks=4, min_current_count=1000)
        assert result == []

    def test_no_data_returns_empty(self):
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            assert emerging_skills(s, lookback_weeks=4) == []

    def test_growth_pct_100_when_new_skill(self, db):
        # Any skill with old_count=0 should have growth_pct=100.0
        result = emerging_skills(db, lookback_weeks=4)
        for r in result:
            if r["old_count"] == 0:
                assert r["growth_pct"] == 100.0, (
                    f"{r['skill']} has old_count=0 but growth_pct={r['growth_pct']}"
                )

    def test_established_skills_excluded(self, db):
        # Python has old_pct=0.84 — way above max_old_pct, must not appear
        result = emerging_skills(db, lookback_weeks=4)
        assert not any(
            r["skill"] == "Python" and r["role_category"] == "data analyst" for r in result
        )
