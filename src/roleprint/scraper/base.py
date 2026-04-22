"""Abstract base class for all Roleprint job scrapers."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from roleprint.db.models import JobPosting

log = structlog.get_logger(__name__)


class BaseJobScraper(ABC):
    """Contract every scraper must satisfy.

    Subclasses implement ``search`` (network I/O, always async) and
    ``parse_posting`` (pure parsing logic, synchronous).  ``deduplicate``
    is provided here — it checks a batch of candidate postings against the
    ``job_postings.url`` column and returns only genuinely new ones.
    """

    #: String identifier written to ``job_postings.source``
    SOURCE: str = ""

    # ── abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def search(
        self,
        role: str,
        location: str = "United Kingdom",
        pages: int = 3,
    ) -> List[dict]:
        """Fetch job listings for *role* and return a list of raw posting dicts.

        Each dict must contain at minimum:
            title, company, location, raw_text, url, role_category, source

        Optional: posted_at (ISO string or datetime)
        """

    @abstractmethod
    def parse_posting(self, raw: Any) -> Optional[dict]:
        """Parse a single raw result (HTML fragment or API dict) into a
        normalised posting dict.  Return ``None`` to skip the result.
        """

    # ── shared helpers ────────────────────────────────────────────────────────

    def deduplicate(self, postings: List[dict], session: Session) -> List[dict]:
        """Remove postings whose URL already exists in *job_postings*.

        Args:
            postings: Candidate postings from the current scrape run.
            session:  Active SQLAlchemy session for the URL lookup.

        Returns:
            Subset of *postings* not yet present in the database.
        """
        if not postings:
            return []

        candidate_urls = {p["url"] for p in postings}

        existing_urls: set = set(
            session.scalars(select(JobPosting.url).where(JobPosting.url.in_(candidate_urls)))
        )

        new_postings = [p for p in postings if p["url"] not in existing_urls]

        log.debug(
            "dedup.complete",
            source=self.SOURCE,
            candidates=len(postings),
            existing=len(existing_urls),
            new=len(new_postings),
        )
        return new_postings
