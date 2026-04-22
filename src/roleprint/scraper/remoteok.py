"""RemoteOK public JSON API scraper.

Endpoint: https://remoteok.com/api
No auth required.  First element of the array is a legal/metadata notice;
all subsequent elements are job postings.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Any, List, Optional

import httpx
import structlog

from roleprint.scraper.agents import random_agent
from roleprint.scraper.base import BaseJobScraper

log = structlog.get_logger(__name__)

_API_URL = "https://remoteok.com/api"
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_JITTER_MAX = 1.0

# Role keyword aliases used to match RemoteOK tags / position titles
_ROLE_KEYWORDS: dict = {
    "data analyst": ["data analyst", "analytics", "data analysis"],
    "data scientist": ["data scientist", "data science", "machine learning"],
    "ml engineer": ["ml engineer", "machine learning engineer", "mlops"],
    "data engineer": ["data engineer", "data pipeline", "etl"],
    "software engineer": ["software engineer", "software developer", "swe"],
    "backend engineer": ["backend", "back end", "back-end", "api developer"],
    "frontend engineer": ["frontend", "front end", "front-end", "react", "vue"],
    "product manager": ["product manager", "product management", "pm"],
    "devops": ["devops", "sre", "site reliability", "platform engineer"],
    "ai researcher": ["ai researcher", "research scientist", "nlp researcher"],
}


class RemoteOKScraper(BaseJobScraper):
    """Scrape the RemoteOK public JSON API.

    Because RemoteOK returns all jobs in one payload, ``pages`` is ignored —
    filtering is done client-side on the full response.

    Usage::

        async with RemoteOKScraper() as scraper:
            postings = await scraper.search("data analyst")
    """

    SOURCE = "remoteok"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Optional[List[dict]] = None  # raw API payload, fetched once

    # ── context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "RemoteOKScraper":
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": random_agent(),
                "Accept": "application/json",
            },
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── public API ────────────────────────────────────────────────────────────

    async def search(
        self,
        role: str,
        location: str = "Remote",
        pages: int = 1,  # API returns everything at once; pages unused
    ) -> List[dict]:
        """Return postings whose tags or title match *role*.

        Fetches the full API payload once and caches it for subsequent
        ``search()`` calls within the same context manager session.
        """
        if self._client is None:
            raise RuntimeError("Use 'async with RemoteOKScraper() as s:' context manager.")

        raw_jobs = await self._fetch_all()
        keywords = _ROLE_KEYWORDS.get(role.lower(), [role.lower()])

        matched: List[dict] = []
        for job in raw_jobs:
            parsed = self.parse_posting(job)
            if parsed and self._matches_role(job, keywords):
                parsed["role_category"] = role
                matched.append(parsed)

        log.info("remoteok.search_complete", role=role, matched=len(matched))
        return matched

    def parse_posting(self, raw: Any) -> Optional[dict]:
        """Normalise a single RemoteOK API job object.

        Args:
            raw: Either a ``dict`` (from the API) or a JSON string.

        Returns:
            Normalised posting dict, or ``None`` if the input is invalid /
            a metadata entry (the first element RemoteOK returns).
        """
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None

        if not isinstance(raw, dict):
            return None

        # Skip the first "legal" element which has no "id" or "position" key
        if "position" not in raw:
            return None

        job_id = raw.get("id", "")
        url = raw.get("url") or f"https://remoteok.com/l/{job_id}"

        title = raw.get("position") or raw.get("title", "")
        company = raw.get("company", "Unknown")
        location = raw.get("location") or "Remote"

        # posted_at — RemoteOK provides an epoch timestamp
        posted_at: Optional[datetime] = None
        epoch = raw.get("epoch")
        if epoch:
            try:
                posted_at = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            except (ValueError, OSError):
                pass

        # raw_text: strip HTML tags from description field
        description = raw.get("description", "") or ""
        raw_text = BeautifulSoup_strip(description) if description else ""

        return {
            "source": self.SOURCE,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "raw_text": raw_text,
            "posted_at": posted_at,
        }

    # ── private helpers ───────────────────────────────────────────────────────

    async def _fetch_all(self) -> List[dict]:
        """Fetch the full RemoteOK API payload (cached within session)."""
        if self._cache is not None:
            return self._cache

        assert self._client is not None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._client.headers.update({"User-Agent": random_agent()})
                resp = await self._client.get(_API_URL)

                if resp.status_code == 200:
                    data = resp.json()
                    # Skip first element (legal notice, not a job)
                    self._cache = [item for item in data if isinstance(item, dict)]
                    log.info("remoteok.fetched", total=len(self._cache))
                    return self._cache

                if resp.status_code in (429, 503):
                    wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                    log.warning(
                        "remoteok.rate_limited",
                        status=resp.status_code,
                        attempt=attempt,
                        wait=round(wait, 2),
                    )
                    await asyncio.sleep(wait)
                    continue

                log.error("remoteok.unexpected_status", status=resp.status_code)
                return []

            except (httpx.RequestError, ValueError) as exc:
                wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                log.warning("remoteok.request_error", error=str(exc), attempt=attempt)
                await asyncio.sleep(wait)

        log.error("remoteok.max_retries_exceeded")
        return []

    @staticmethod
    def _matches_role(job: dict, keywords: List[str]) -> bool:
        """Return True if any keyword appears in the job's tags or title.

        Tags are normalised (hyphens → spaces) before comparison so that
        e.g. "data-science" matches keyword "data science".
        """
        # Normalise tags: lower-case and replace hyphens with spaces
        tags = [t.lower().replace("-", " ") for t in (job.get("tags") or [])]
        title = (job.get("position") or "").lower()
        return any(kw in title or any(kw in tag for tag in tags) for kw in keywords)


def BeautifulSoup_strip(html: str) -> str:
    """Strip HTML tags from a string using BeautifulSoup."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
