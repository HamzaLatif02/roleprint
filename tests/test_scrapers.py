"""Parser tests for ReedScraper and RemoteOKScraper.

All tests are offline — no HTTP calls made.  Fixtures live in tests/fixtures/.
"""

from __future__ import annotations

import json
import uuid
from datetime import timezone
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from roleprint.db.base import Base
from roleprint.db.models import JobPosting
from roleprint.scraper.adzuna_scraper import AdzunaScraper
from roleprint.scraper.reed import ReedScraper
from roleprint.scraper.remoteok import RemoteOKScraper

FIXTURES = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def adzuna_payload() -> dict:
    return json.loads((FIXTURES / "adzuna_response.json").read_text())


@pytest.fixture(scope="module")
def reed_html() -> str:
    return (FIXTURES / "reed_search.html").read_text()


@pytest.fixture(scope="module")
def remoteok_payload() -> List[dict]:
    return json.loads((FIXTURES / "remoteok_api.json").read_text())


@pytest.fixture(scope="module")
def reed_cards(reed_html) -> List[str]:
    """Extract individual <article> card HTML strings from the fixture page."""
    soup = BeautifulSoup(reed_html, "html.parser")
    return [str(card) for card in soup.find_all("article", attrs={"data-job-id": True})]


@pytest.fixture(scope="module")
def db_session():
    """In-memory SQLite session seeded with one existing URL."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        existing = JobPosting(
            id=uuid.uuid4(),
            source="reed",
            role_category="data analyst",
            title="Existing Posting",
            company="OldCo",
            location="London",
            raw_text="already in db",
            url="https://www.reed.co.uk/jobs/data-analyst/old-co/54321001",
        )
        s.add(existing)
        s.commit()
        yield s


# ─────────────────────────────────────────────────────────────────────────────
# ReedScraper — parse_posting
# ─────────────────────────────────────────────────────────────────────────────


class TestReedParser:
    def setup_method(self):
        self.scraper = ReedScraper()

    def test_parses_title(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert result["title"] == "Senior Data Analyst"

    def test_parses_company(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert result["company"] == "Acme Corporation"

    def test_parses_location(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert "London" in result["location"]

    def test_parses_url(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert result["url"].startswith("https://www.reed.co.uk/jobs/")
        assert "54321001" in result["url"]

    def test_parses_posted_at_with_datetime(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert result["posted_at"] is not None
        assert result["posted_at"].tzinfo == timezone.utc
        assert result["posted_at"].year == 2026
        assert result["posted_at"].month == 4

    def test_posted_at_none_when_no_datetime_attr(self, reed_cards):
        # Card 2 has <time> but no datetime attribute
        result = self.scraper.parse_posting(reed_cards[1])
        assert result is not None
        assert result["posted_at"] is None

    def test_parses_description(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert "Python" in result["raw_text"]
        assert "SQL" in result["raw_text"]

    def test_parses_span_company_fallback(self, reed_cards):
        # Card 3 has <span> not <a> for company name
        result = self.scraper.parse_posting(reed_cards[2])
        assert result is not None
        assert result["company"] == "Gamma Tech"

    def test_skips_card_without_valid_url(self, reed_cards):
        # Card 4 has an <a> with no href — should be skipped
        result = self.scraper.parse_posting(reed_cards[3])
        assert result is None

    def test_returns_none_for_empty_string(self):
        assert self.scraper.parse_posting("") is None

    def test_returns_none_for_non_string(self):
        assert self.scraper.parse_posting(None) is None  # type: ignore[arg-type]

    def test_source_is_reed(self, reed_cards):
        result = self.scraper.parse_posting(reed_cards[0])
        assert result is not None
        assert result["source"] == "reed"

    def test_parse_search_page_returns_all_valid_cards(self, reed_html):
        results = self.scraper._parse_search_page(reed_html, "data analyst")
        # 4 cards in fixture, 1 (card 4) has no valid href → 3 valid
        assert len(results) == 3

    def test_parse_search_page_sets_role_category(self, reed_html):
        results = self.scraper._parse_search_page(reed_html, "data analyst")
        assert all(r["role_category"] == "data analyst" for r in results)


# ─────────────────────────────────────────────────────────────────────────────
# RemoteOKScraper — parse_posting
# ─────────────────────────────────────────────────────────────────────────────


class TestRemoteOKParser:
    def setup_method(self):
        self.scraper = RemoteOKScraper()

    def test_skips_legal_metadata_entry(self, remoteok_payload):
        # First element has no "position" key
        result = self.scraper.parse_posting(remoteok_payload[0])
        assert result is None

    def test_parses_title(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert result["title"] == "Senior Data Scientist"

    def test_parses_company(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert result["company"] == "DataFlow Inc"

    def test_parses_url(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert result["url"] == "https://remoteok.com/l/remote-ok-190001"

    def test_parses_posted_at_from_epoch(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert result["posted_at"] is not None
        assert result["posted_at"].tzinfo == timezone.utc
        assert result["posted_at"].year == 2026

    def test_posted_at_none_when_epoch_null(self, remoteok_payload):
        # Last entry has epoch: null
        result = self.scraper.parse_posting(remoteok_payload[4])
        assert result is not None
        assert result["posted_at"] is None

    def test_strips_html_from_description(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert "<p>" not in result["raw_text"]
        assert "<strong>" not in result["raw_text"]
        assert "DataFlow Inc" in result["raw_text"]

    def test_parses_from_json_string(self, remoteok_payload):
        json_str = json.dumps(remoteok_payload[2])
        result = self.scraper.parse_posting(json_str)
        assert result is not None
        assert result["title"] == "Data Engineer – Spark & dbt"

    def test_returns_none_for_invalid_json(self):
        assert self.scraper.parse_posting("{not valid json") is None

    def test_returns_none_for_non_dict(self):
        assert self.scraper.parse_posting("just a string") is None

    def test_source_is_remoteok(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        assert result["source"] == "remoteok"

    def test_empty_raw_text_when_no_description(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[4])
        assert result is not None
        assert result["raw_text"] == ""

    def test_location_defaults_to_remote(self, remoteok_payload):
        result = self.scraper.parse_posting(remoteok_payload[1])
        assert result is not None
        # "Worldwide" is in the fixture, not "Remote"
        assert result["location"] == "Worldwide"

    def test_matches_role_by_tag(self):
        job = {"position": "Generic Developer", "tags": ["data-science", "python"]}
        assert RemoteOKScraper._matches_role(job, ["data scientist", "data science"])

    def test_matches_role_by_title(self):
        job = {"position": "Senior ML Engineer", "tags": []}
        assert RemoteOKScraper._matches_role(job, ["ml engineer"])

    def test_no_match_returns_false(self):
        job = {"position": "Office Manager", "tags": ["administration"]}
        assert not RemoteOKScraper._matches_role(job, ["data analyst", "python"])


# ─────────────────────────────────────────────────────────────────────────────
# BaseJobScraper — deduplicate
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# AdzunaScraper — parse_posting
# ─────────────────────────────────────────────────────────────────────────────


class TestAdzunaParser:
    def setup_method(self):
        self.scraper = AdzunaScraper()

    def test_parses_title(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert result["title"] == "Senior Data Analyst"

    def test_parses_company(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert result["company"] == "Acme Analytics Ltd"

    def test_parses_location(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert "London" in result["location"]

    def test_parses_url(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert result["url"] == "https://www.adzuna.co.uk/jobs/details/4290123456"

    def test_parses_description(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert "Python" in result["raw_text"]
        assert "SQL" in result["raw_text"]

    def test_parses_posted_at(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert result["posted_at"] is not None
        assert result["posted_at"].tzinfo == timezone.utc
        assert result["posted_at"].year == 2026
        assert result["posted_at"].month == 4

    def test_posted_at_none_when_created_null(self, adzuna_payload):
        # results[2] has "created": null
        result = self.scraper.parse_posting(adzuna_payload["results"][2])
        assert result is not None
        assert result["posted_at"] is None

    def test_skips_posting_with_empty_title(self, adzuna_payload):
        # results[3] has empty title
        result = self.scraper.parse_posting(adzuna_payload["results"][3])
        assert result is None

    def test_skips_posting_with_empty_url(self, adzuna_payload):
        # results[4] has empty redirect_url
        result = self.scraper.parse_posting(adzuna_payload["results"][4])
        assert result is None

    def test_company_defaults_to_unknown_when_null(self, adzuna_payload):
        # results[4] has company: null — parse_posting returns None due to empty URL,
        # test null-company path via a synthetic dict
        result = self.scraper.parse_posting(
            {
                "title": "Analyst",
                "redirect_url": "https://adzuna.co.uk/jobs/1",
                "company": None,
                "location": None,
                "description": None,
                "created": None,
            }
        )
        assert result is not None
        assert result["company"] == "Unknown"

    def test_location_empty_when_null(self, adzuna_payload):
        result = self.scraper.parse_posting(
            {
                "title": "Analyst",
                "redirect_url": "https://adzuna.co.uk/jobs/1",
                "company": None,
                "location": None,
                "description": None,
                "created": None,
            }
        )
        assert result is not None
        assert result["location"] == ""

    def test_raw_text_empty_when_description_null(self, adzuna_payload):
        result = self.scraper.parse_posting(
            {
                "title": "Analyst",
                "redirect_url": "https://adzuna.co.uk/jobs/1",
                "company": {"display_name": "Co"},
                "location": {"display_name": "London"},
                "description": None,
                "created": None,
            }
        )
        assert result is not None
        assert result["raw_text"] == ""

    def test_returns_none_for_non_dict(self):
        assert self.scraper.parse_posting("not a dict") is None
        assert self.scraper.parse_posting(None) is None  # type: ignore[arg-type]
        assert self.scraper.parse_posting([]) is None  # type: ignore[arg-type]

    def test_source_is_adzuna(self, adzuna_payload):
        result = self.scraper.parse_posting(adzuna_payload["results"][0])
        assert result is not None
        assert result["source"] == "adzuna"

    def test_search_sets_role_category(self, adzuna_payload, monkeypatch):
        """search() should attach role_category to every parsed posting."""
        import os

        monkeypatch.setenv("ADZUNA_APP_ID", "test_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "test_key")

        scraper = AdzunaScraper()

        async def mock_fetch(url, params):
            return adzuna_payload

        scraper._client = MagicMock()
        scraper._fetch = mock_fetch  # type: ignore[assignment]

        import asyncio

        results = asyncio.run(scraper.search("data analyst", pages=1))
        # 5 items in fixture, 2 are invalid (empty title, empty URL) → 3 valid
        assert len(results) == 3
        assert all(r["role_category"] == "data analyst" for r in results)


# ─────────────────────────────────────────────────────────────────────────────
# TestDeduplicate (existing)
# ─────────────────────────────────────────────────────────────────────────────


class TestDeduplicate:
    def setup_method(self):
        self.scraper = ReedScraper()  # use ReedScraper as a concrete impl

    def test_removes_existing_url(self, db_session):
        postings = [
            {
                "url": "https://www.reed.co.uk/jobs/data-analyst/old-co/54321001",
                "title": "Existing Posting",
            },
            {
                "url": "https://www.reed.co.uk/jobs/data-analyst/new-co/99999",
                "title": "Brand New Posting",
            },
        ]
        result = self.scraper.deduplicate(postings, db_session)
        assert len(result) == 1
        assert result[0]["url"] == "https://www.reed.co.uk/jobs/data-analyst/new-co/99999"

    def test_returns_all_when_none_exist(self, db_session):
        postings = [
            {"url": "https://www.reed.co.uk/jobs/x/1"},
            {"url": "https://www.reed.co.uk/jobs/x/2"},
        ]
        result = self.scraper.deduplicate(postings, db_session)
        assert len(result) == 2

    def test_returns_empty_for_empty_input(self, db_session):
        assert self.scraper.deduplicate([], db_session) == []
