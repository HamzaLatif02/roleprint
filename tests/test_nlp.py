"""NLP pipeline unit tests.

All tests are offline — no spaCy model, no VADER download, no BERTopic.
spaCy and the topic model are mocked where needed.
Sentiment uses real VADER (downloaded in session-scoped fixture).
"""

from __future__ import annotations

import json
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# ── Sample fixtures ───────────────────────────────────────────────────────────
from tests.fixtures.sample_jobs import DATA_ANALYST_JD, PM_JD, SWE_JD

# ── Project imports ───────────────────────────────────────────────────────────
from roleprint.db.base import Base
from roleprint.db.models import JobPosting, ProcessedPosting, SkillTrend
from roleprint.nlp import cleaner, ner, sentiment, skill_extractor, topic_model
from roleprint.nlp.pipeline import (
    _update_skill_trends,
    _week_start,
    _write_result,
    process_posting,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared DB fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_posting(role: str, text: str, source: str = "reed") -> JobPosting:
    return JobPosting(
        id=uuid.uuid4(),
        source=source,
        role_category=role,
        title="Test Role",
        company="TestCo",
        location="London",
        raw_text=text,
        url=f"https://example.com/{uuid.uuid4()}",
        scraped_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        is_processed=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. cleaner.py
# ─────────────────────────────────────────────────────────────────────────────


class TestCleaner:
    def test_strip_html_tags(self):
        html = "<p>We need <strong>Python</strong> and <em>SQL</em> skills.</p>"
        out = cleaner.strip_html(html)
        assert "<p>" not in out
        assert "Python" in out
        assert "SQL" in out

    def test_strip_nested_html(self):
        html = "<div><ul><li>React</li><li>TypeScript</li></ul></div>"
        out = cleaner.strip_html(html)
        assert "React" in out
        assert "TypeScript" in out

    def test_empty_string_returns_empty(self):
        assert cleaner.clean("") == ""
        assert cleaner.clean("   ") == ""

    def test_removes_equal_opportunities_boilerplate(self):
        text = "Great role. We are an equal opportunities employer and welcome all."
        out = cleaner.remove_boilerplate(text)
        assert "equal opportunities" not in out.lower()

    def test_removes_right_to_work_clause(self):
        text = (
            "You must have the right to work in the United Kingdom. Strong Python skills required."
        )
        out = cleaner.remove_boilerplate(text)
        assert "right to work" not in out.lower()
        # Preserves the important part
        assert "Python" in out

    def test_removes_no_agencies(self):
        text = "Looking for a Data Engineer. No agencies please."
        out = cleaner.remove_boilerplate(text)
        assert "no agencies" not in out.lower()

    def test_normalise_unicode_replaces_smart_quotes(self):
        text = "\u201cSenior\u201d role in \u2018London\u2019"
        out = cleaner.normalise_unicode(text)
        assert '"Senior"' in out or "'London'" in out

    def test_normalise_whitespace_collapses_spaces(self):
        text = "Python   and    SQL"
        out = cleaner.normalise_whitespace(text)
        assert "  " not in out

    def test_clean_pipeline_end_to_end_analyst(self):
        out = cleaner.clean(DATA_ANALYST_JD)
        # Boilerplate removed
        assert "equal opportunities" not in out.lower()
        assert "no agencies" not in out.lower()
        assert "right to work" not in out.lower()
        # Content preserved
        assert "Python" in out
        assert "Snowflake" in out
        assert "stakeholder" in out

    def test_clean_pipeline_end_to_end_swe(self):
        out = cleaner.clean(SWE_JD)
        assert "GDPR" not in out
        assert "Kubernetes" in out

    def test_clean_for_analysis_returns_lowercase(self):
        out = cleaner.clean_for_analysis("Python and SQL experience required.")
        assert out == out.lower()
        assert "python" in out


# ─────────────────────────────────────────────────────────────────────────────
# 2. skill_extractor.py
# ─────────────────────────────────────────────────────────────────────────────


class TestSkillExtractor:
    def test_extracts_single_word_technical_skill(self):
        skills = skill_extractor.extract_skills("Must know Python and SQL.")
        assert "Python" in skills
        assert "SQL" in skills

    def test_extracts_multi_word_skill(self):
        skills = skill_extractor.extract_skills("Strong stakeholder management skills required.")
        assert "stakeholder management" in skills

    def test_case_insensitive_match(self):
        skills = skill_extractor.extract_skills("Experience with PYTHON and sql required.")
        assert "Python" in skills
        assert "SQL" in skills

    def test_no_partial_match(self):
        # "R" should not appear because there's no isolated "R" here
        skills = skill_extractor.extract_skills("React and REST API experience.")
        assert "R" not in skills

    def test_counts_multiple_mentions(self):
        text = "Python Python Python. Use Python daily."
        skills = skill_extractor.extract_skills(text)
        assert skills.get("Python", 0) >= 3

    def test_data_analyst_skills(self):
        skills = skill_extractor.extract_skills(DATA_ANALYST_JD)
        expected = ["Python", "SQL", "Snowflake", "Tableau", "dbt", "Power BI", "pandas"]
        for s in expected:
            assert s in skills, f"Expected '{s}' in skills"

    def test_data_analyst_soft_skills(self):
        skills = skill_extractor.extract_skills(DATA_ANALYST_JD)
        soft_expected = ["stakeholder management", "agile", "A/B testing"]
        for s in soft_expected:
            assert s in skills, f"Expected soft skill '{s}'"

    def test_swe_skills(self):
        skills = skill_extractor.extract_skills(SWE_JD)
        expected = [
            "Python",
            "TypeScript",
            "Docker",
            "Kubernetes",
            "Kafka",
            "PostgreSQL",
            "Redis",
            "Terraform",
            "GitHub Actions",
        ]
        for s in expected:
            assert s in skills, f"Expected '{s}' in SWE skills"

    def test_pm_skills(self):
        skills = skill_extractor.extract_skills(PM_JD)
        expected = [
            "SQL",
            "agile",
            "scrum",
            "A/B testing",
            "stakeholder management",
            "roadmap",
            "OKRs",
        ]
        for s in expected:
            assert s in skills, f"Expected '{s}' in PM skills"

    def test_empty_text_returns_empty_dict(self):
        assert skill_extractor.extract_skills("") == {}

    def test_returns_sorted_by_count(self):
        text = "Python Python Python SQL SQL TypeScript"
        skills = skill_extractor.extract_skills(text)
        counts = list(skills.values())
        assert counts == sorted(counts, reverse=True)

    def test_categorise_splits_technical_and_soft(self):
        skills = {"Python": 3, "SQL": 2, "stakeholder management": 1, "agile": 2}
        result = skill_extractor.categorise_skills(skills)
        assert "Python" in result["technical"]
        assert "SQL" in result["technical"]
        assert "stakeholder management" in result["soft"]
        assert "agile" in result["soft"]

    def test_vocab_loads_from_file(self):
        vocab = skill_extractor.load_vocab()
        assert "technical" in vocab
        assert "soft" in vocab
        flat = skill_extractor.flatten_vocab(vocab)
        assert "Python" in flat
        assert "stakeholder management" in flat

    def test_build_patterns_deduplicates(self):
        skills = ["Python", "python", "PYTHON"]
        patterns = skill_extractor.build_patterns(skills)
        names = [name for name, _ in patterns]
        assert len(names) == 1

    def test_spacy_noun_chunk_path(self):
        """Verify noun-chunk matching works when a mock nlp is injected."""
        # Build a mock spaCy doc with a noun chunk matching a vocab skill
        MockChunk = namedtuple("Chunk", ["text"])
        mock_doc = MagicMock()
        mock_doc.noun_chunks = [MockChunk("stakeholder management"), MockChunk("sprint planning")]

        mock_nlp = MagicMock(return_value=mock_doc)

        text = "This role requires stakeholder management and sprint planning experience."
        skills = skill_extractor.extract_skills(text, nlp=mock_nlp)
        assert "stakeholder management" in skills


# ─────────────────────────────────────────────────────────────────────────────
# 3. sentiment.py
# ─────────────────────────────────────────────────────────────────────────────


class TestSentiment:
    def test_returns_all_keys(self):
        result = sentiment.analyse("We are looking for a passionate engineer.")
        assert all(k in result for k in ("compound", "positive", "negative", "neutral", "urgency"))

    def test_positive_tone_job(self):
        text = "Exciting opportunity! Join our fantastic, supportive team."
        result = sentiment.analyse(text)
        assert result["compound"] > 0

    def test_negative_tone_job(self):
        text = "Demanding role. Stressful deadlines. Toxic culture expected."
        result = sentiment.analyse(text)
        assert result["compound"] < 0

    def test_empty_text_returns_zero_scores(self):
        result = sentiment.analyse("")
        assert result["compound"] == 0.0
        assert result["urgency"] == 0

    def test_urgency_detected_asap(self):
        assert sentiment.count_urgency("Please apply ASAP for this role.") >= 1

    def test_urgency_detected_immediate_start(self):
        assert sentiment.count_urgency("Immediate start available.") >= 1

    def test_urgency_detected_urgent(self):
        assert sentiment.count_urgency("URGENT: we need someone now.") >= 1

    def test_swe_jd_has_urgency(self):
        result = sentiment.analyse(SWE_JD)
        assert result["urgency"] >= 2  # "IMMEDIATE START", "ASAP", "urgently"

    def test_analyst_jd_no_urgency(self):
        result = sentiment.analyse(DATA_ANALYST_JD)
        assert result["urgency"] == 0

    def test_compound_score_helper(self):
        score = sentiment.compound_score("Great opportunity to learn and grow.")
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0

    def test_scores_are_bounded(self):
        result = sentiment.analyse(DATA_ANALYST_JD)
        assert -1.0 <= result["compound"] <= 1.0
        assert 0.0 <= result["positive"] <= 1.0
        assert 0.0 <= result["negative"] <= 1.0
        assert 0.0 <= result["neutral"] <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. ner.py
# ─────────────────────────────────────────────────────────────────────────────

# Build a minimal mock spaCy model that returns predictable entities
MockEnt = namedtuple("Ent", ["text", "label_"])


def _make_mock_nlp(entities: list) -> MagicMock:
    """Return a callable mock that acts like spacy.load(...)."""
    mock_doc = MagicMock()
    mock_doc.ents = [MockEnt(text=t, label_=l) for t, l in entities]
    nlp = MagicMock(return_value=mock_doc)
    return nlp


class TestNER:
    def test_extracts_orgs(self):
        mock_nlp = _make_mock_nlp([("Acme Corp", "ORG"), ("London", "GPE")])
        result = ner.extract_entities("Acme Corp is in London.", nlp=mock_nlp)
        assert "Acme Corp" in result["orgs"]

    def test_extracts_locations(self):
        mock_nlp = _make_mock_nlp([("Manchester", "GPE"), ("TechCorp", "ORG")])
        result = ner.extract_entities("TechCorp is in Manchester.", nlp=mock_nlp)
        assert "Manchester" in result["locations"]

    def test_extracts_products(self):
        mock_nlp = _make_mock_nlp([("Snowflake", "PRODUCT")])
        result = ner.extract_entities("We use Snowflake.", nlp=mock_nlp)
        assert "Snowflake" in result["products"]

    def test_filters_out_other_labels(self):
        mock_nlp = _make_mock_nlp([("2026", "DATE"), ("John", "PERSON")])
        result = ner.extract_entities("John in 2026.", nlp=mock_nlp)
        assert result["orgs"] == []
        assert result["locations"] == []
        assert result["products"] == []

    def test_deduplicates_entities(self):
        mock_nlp = _make_mock_nlp([("London", "GPE"), ("London", "GPE"), ("TechCorp", "ORG")])
        result = ner.extract_entities("London London TechCorp", nlp=mock_nlp)
        assert result["locations"].count("London") == 1

    def test_returns_sorted_lists(self):
        mock_nlp = _make_mock_nlp([("Zurich", "GPE"), ("Amsterdam", "GPE"), ("Berlin", "GPE")])
        result = ner.extract_entities("text", nlp=mock_nlp)
        assert result["locations"] == sorted(result["locations"])

    def test_empty_text_returns_empty_buckets(self):
        result = ner.extract_entities("", nlp=MagicMock())
        assert result == {"orgs": [], "locations": [], "products": []}

    def test_merge_tool_entities_adds_capitalised_skills(self):
        entities = {"orgs": ["Acme"], "locations": [], "products": []}
        skills = ["Python", "Kubernetes", "stakeholder management"]
        merged = ner.merge_tool_entities(entities, skills)
        assert "Python" in merged["orgs"]
        assert "Kubernetes" in merged["orgs"]
        # lowercase skills should NOT be added
        assert "stakeholder management" not in merged["orgs"]

    def test_merge_tool_entities_does_not_mutate_original(self):
        entities = {"orgs": ["Acme"], "locations": [], "products": []}
        ner.merge_tool_entities(entities, ["Python"])
        assert "Python" not in entities["orgs"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. topic_model.py
# ─────────────────────────────────────────────────────────────────────────────


class TestTopicModel:
    def setup_method(self):
        topic_model.reset()

    def test_assign_topics_without_model_returns_empty(self):
        results = topic_model.assign_topics(["some text"], model=None)
        assert results == [{}]

    def test_assign_topics_length_matches_input(self):
        texts = ["text one", "text two", "text three"]
        results = topic_model.assign_topics(texts, model=None)
        assert len(results) == len(texts)

    def test_train_requires_min_docs(self):
        # Fewer than MIN_DOCS → returns None without calling BERTopic
        result = topic_model.train(["doc1", "doc2"])
        assert result is None

    def test_assign_topics_with_mock_model(self):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1], [0.9, 0.7])
        import pandas as pd

        mock_model.get_topic_info.return_value = pd.DataFrame(
            {
                "Topic": [0, 1],
                "Name": ["data analysis", "machine learning"],
            }
        )
        texts = ["data SQL analysis", "machine learning pytorch"]
        results = topic_model.assign_topics(texts, model=mock_model)
        assert len(results) == 2
        assert results[0]["topic_id"] == 0
        assert results[0]["topic_label"] == "data analysis"
        assert results[0]["probability"] == 0.9
        assert results[1]["topic_id"] == 1

    def test_reset_clears_cache(self):
        topic_model._topic_model = MagicMock()
        topic_model.reset()
        assert topic_model._topic_model is None


# ─────────────────────────────────────────────────────────────────────────────
# 6. pipeline.py integration
# ─────────────────────────────────────────────────────────────────────────────


class TestPipeline:
    def test_process_posting_returns_required_keys(self):
        posting = _make_posting("data analyst", DATA_ANALYST_JD)
        result = process_posting(posting, nlp=None, topic_mdl=None)
        assert "skills_extracted" in result
        assert "sentiment_score" in result
        assert "topics" in result
        assert "entities" in result

    def test_process_posting_extracts_skills_data_analyst(self):
        posting = _make_posting("data analyst", DATA_ANALYST_JD)
        result = process_posting(posting, nlp=None)
        assert "Python" in result["skills_extracted"]
        assert "SQL" in result["skills_extracted"]

    def test_process_posting_extracts_skills_swe(self):
        posting = _make_posting("software engineer", SWE_JD)
        result = process_posting(posting, nlp=None)
        assert "Python" in result["skills_extracted"]
        assert "Docker" in result["skills_extracted"]
        assert "Kubernetes" in result["skills_extracted"]

    def test_process_posting_extracts_skills_pm(self):
        posting = _make_posting("product manager", PM_JD)
        result = process_posting(posting, nlp=None)
        assert "agile" in result["skills_extracted"]
        assert "SQL" in result["skills_extracted"]

    def test_process_posting_sentiment_is_float(self):
        posting = _make_posting("data analyst", DATA_ANALYST_JD)
        result = process_posting(posting)
        assert isinstance(result["sentiment_score"], float)
        assert -1.0 <= result["sentiment_score"] <= 1.0

    def test_process_posting_with_ner_mock(self):
        mock_nlp = _make_mock_nlp([("Acme Analytics", "ORG"), ("London", "GPE")])
        posting = _make_posting("data analyst", DATA_ANALYST_JD)
        result = process_posting(posting, nlp=mock_nlp)
        assert "Acme Analytics" in result["entities"]["orgs"]
        assert "London" in result["entities"]["locations"]

    def test_week_start_returns_monday(self):
        # 2026-04-14 is a Tuesday
        dt = datetime(2026, 4, 14, tzinfo=timezone.utc)
        ws = _week_start(dt)
        assert ws.weekday() == 0  # Monday
        assert str(ws) == "2026-04-13"

    def test_write_result_marks_posting_processed(self, db):
        posting = _make_posting("data analyst", DATA_ANALYST_JD)
        db.add(posting)
        db.flush()

        result = {
            "skills_extracted": ["Python", "SQL"],
            "sentiment_score": 0.3,
            "topics": {},
            "entities": {"orgs": [], "locations": [], "products": []},
        }
        _write_result(db, posting, result)
        db.flush()

        assert posting.is_processed is True
        proc = db.scalar(
            __import__("sqlalchemy")
            .select(ProcessedPosting)
            .where(ProcessedPosting.posting_id == posting.id)
        )
        assert proc is not None
        assert proc.sentiment_score == 0.3
        assert "Python" in proc.skills_extracted

    def test_update_skill_trends_creates_rows(self, db):
        posting = _make_posting("ml engineer", SWE_JD)
        db.add(posting)
        db.flush()

        result = {
            "skills_extracted": ["Python", "Docker", "Kubernetes"],
            "sentiment_score": 0.1,
            "topics": {},
            "entities": {"orgs": [], "locations": [], "products": []},
        }
        _update_skill_trends(db, [(posting, result)])
        db.commit()

        from sqlalchemy import select as sa_select

        trends = list(
            db.scalars(sa_select(SkillTrend).where(SkillTrend.role_category == "ml engineer"))
        )
        skill_names = {t.skill for t in trends}
        assert "Python" in skill_names
        assert "Docker" in skill_names

    def test_update_skill_trends_increments_existing(self, db):
        # Insert initial trend
        ws = _week_start(datetime(2026, 4, 14, tzinfo=timezone.utc))
        initial = SkillTrend(
            skill="Python",
            role_category="test_role",
            week_start=ws,
            mention_count=5,
            pct_of_postings=0.5,
        )
        db.add(initial)
        db.commit()

        posting = _make_posting("test_role", "Python and SQL")
        posting.scraped_at = datetime(2026, 4, 14, tzinfo=timezone.utc)
        db.add(posting)
        db.flush()

        result = {
            "skills_extracted": ["Python"],
            "sentiment_score": 0.0,
            "topics": {},
            "entities": {"orgs": [], "locations": [], "products": []},
        }
        _update_skill_trends(db, [(posting, result)])
        db.commit()

        from sqlalchemy import select as sa_select

        trend = db.scalar(
            sa_select(SkillTrend).where(
                SkillTrend.skill == "Python",
                SkillTrend.role_category == "test_role",
                SkillTrend.week_start == ws,
            )
        )
        assert trend.mention_count == 6
