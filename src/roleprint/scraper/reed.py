"""Reed.co.uk scraper — async httpx, exponential backoff, robots.txt aware."""

from __future__ import annotations

import asyncio
import random
import urllib.robotparser
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import quote_plus, urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from roleprint.scraper.agents import random_agent
from roleprint.scraper.base import BaseJobScraper

log = structlog.get_logger(__name__)

_BASE_URL = "https://www.reed.co.uk"
_SEARCH_URL = "https://www.reed.co.uk/jobs/{role}?locationName={location}&pageno={page}"
_ROBOTS_URL = "https://www.reed.co.uk/robots.txt"

# Backoff config
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds; doubles each retry
_JITTER_MAX = 1.0


class ReedScraper(BaseJobScraper):
    """Scrape reed.co.uk search results with async httpx.

    Usage::

        async with ReedScraper() as scraper:
            postings = await scraper.search("data analyst", pages=2)
    """

    SOURCE = "reed"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._robots: Optional[urllib.robotparser.RobotFileParser] = None

    # ── context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "ReedScraper":
        self._client = httpx.AsyncClient(
            headers={"User-Agent": random_agent()},
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        )
        await self._load_robots()
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── public API ────────────────────────────────────────────────────────────

    async def search(
        self,
        role: str,
        location: str = "United Kingdom",
        pages: int = 3,
    ) -> List[dict]:
        """Scrape *pages* pages of Reed search results for *role*.

        Returns a list of normalised posting dicts.
        """
        if self._client is None:
            raise RuntimeError("Use 'async with ReedScraper() as s:' context manager.")

        results: List[dict] = []
        role_slug = quote_plus(role.lower().replace(" ", "-"))

        for page in range(1, pages + 1):
            url = _SEARCH_URL.format(
                role=role_slug,
                location=quote_plus(location),
                page=page,
            )

            if not self._is_allowed(url):
                log.warning("reed.robots_disallowed", url=url)
                break

            log.info("reed.fetch_page", role=role, page=page, url=url)
            html = await self._fetch(url)
            if html is None:
                log.warning("reed.page_failed", role=role, page=page)
                break

            page_results = self._parse_search_page(html, role)
            log.info("reed.page_parsed", role=role, page=page, count=len(page_results))
            results.extend(page_results)

            # Polite crawl delay
            await asyncio.sleep(random.uniform(1.5, 3.5))

        return results

    def parse_posting(self, raw: Any) -> Optional[dict]:
        """Parse a single ``<article>`` HTML fragment into a posting dict.

        Args:
            raw: HTML string of one Reed job card ``<article>`` element.

        Returns:
            Normalised dict, or ``None`` if the card can't be parsed.
        """
        if not isinstance(raw, str) or not raw.strip():
            return None

        soup = BeautifulSoup(raw, "html.parser")
        article = soup.find("article") or soup

        # ── title & URL ───────────────────────────────────────────────────────
        title_tag = (
            article.find("a", attrs={"data-qa": "job-card-title"})
            or article.find("a", attrs={"data-element": "job_title"})
            or (article.find("h2") and article.find("h2").find("a"))
            or article.find("a", class_=lambda c: c and "title" in c.lower() if c else False)
        )
        if title_tag is None:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = urljoin(_BASE_URL, href) if href else ""

        if not title or not url:
            return None

        # ── company ───────────────────────────────────────────────────────────
        company_tag = (
            article.find("a", class_=lambda c: c and "recruiter" in c.lower() if c else False)
            or article.find("span", class_=lambda c: c and "recruiter" in c.lower() if c else False)
            # Reed now uses /jobs/{company-slug}/p{id} pattern for employer links
            or next(
                (
                    a
                    for a in article.find_all("a")
                    if a.get("href", "").startswith("/jobs/")
                    and "/p" in a.get("href", "")
                    and a.get("data-qa") != "job-card-title"
                    and a.get_text(strip=True)
                ),
                None,
            )
        )
        company = company_tag.get_text(strip=True) if company_tag else "Unknown"

        # ── location ──────────────────────────────────────────────────────────
        location_tag = article.find(
            lambda t: (
                t.name == "li"
                and t.get("class")
                and any("location" in c.lower() for c in t.get("class", []))
            )
        )
        if location_tag is None:
            # fall back: second <li> in the metadata list
            meta_items = article.select("ul li")
            location_tag = meta_items[1] if len(meta_items) > 1 else None
        location = location_tag.get_text(strip=True) if location_tag else ""

        # ── posted_at ─────────────────────────────────────────────────────────
        time_tag = article.find("time")
        posted_at: Optional[datetime] = None
        if time_tag and time_tag.get("datetime"):
            try:
                posted_at = datetime.fromisoformat(time_tag["datetime"].rstrip("Z")).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass

        # ── description / raw_text ────────────────────────────────────────────
        desc_tag = article.find(
            lambda t: (
                t.name in ("div", "p")
                and t.get("class")
                and any("description" in c.lower() for c in t.get("class", []))
            )
        )
        raw_text = desc_tag.get_text(" ", strip=True) if desc_tag else ""

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

    async def _fetch(self, url: str) -> Optional[str]:
        """GET *url* with exponential backoff on 429/503."""
        assert self._client is not None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # Rotate user agent on each attempt
                self._client.headers.update({"User-Agent": random_agent()})
                resp = await self._client.get(url)

                if resp.status_code == 200:
                    return resp.text

                if resp.status_code in (429, 503):
                    wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                    log.warning(
                        "reed.rate_limited",
                        status=resp.status_code,
                        attempt=attempt,
                        wait=round(wait, 2),
                        url=url,
                    )
                    await asyncio.sleep(wait)
                    continue

                log.error("reed.unexpected_status", status=resp.status_code, url=url)
                return None

            except httpx.RequestError as exc:
                wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                log.warning(
                    "reed.request_error",
                    error=str(exc),
                    attempt=attempt,
                    wait=round(wait, 2),
                )
                await asyncio.sleep(wait)

        log.error("reed.max_retries_exceeded", url=url)
        return None

    async def _load_robots(self) -> None:
        """Fetch and cache robots.txt."""
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(_ROBOTS_URL)
        try:
            assert self._client is not None
            resp = await self._client.get(_ROBOTS_URL)
            rp.parse(resp.text.splitlines())
            self._robots = rp
            log.debug("reed.robots_loaded")
        except Exception as exc:
            log.warning("reed.robots_load_failed", error=str(exc))
            self._robots = None

    def _is_allowed(self, url: str) -> bool:
        if self._robots is None:
            return True
        return self._robots.can_fetch("*", url)

    def _parse_search_page(self, html: str, role: str) -> List[dict]:
        """Extract all job cards from a search results page."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("article", attrs={"data-qa": "job-card"})

        postings: List[dict] = []
        for card in cards:
            parsed = self.parse_posting(str(card))
            if parsed:
                parsed["role_category"] = role
                postings.append(parsed)

        return postings
