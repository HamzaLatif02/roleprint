"""Adzuna API scraper — async httpx, exponential backoff, paginated results."""

from __future__ import annotations

import asyncio
import os
import random
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from roleprint.scraper.base import BaseJobScraper

log = structlog.get_logger(__name__)

_API_BASE = "https://api.adzuna.com/v1/api/jobs/gb/search/{page}"
_RESULTS_PER_PAGE = 50

# Backoff config
_MAX_RETRIES = 4
_BACKOFF_BASE = 2.0  # seconds; doubles each retry
_JITTER_MAX = 1.0


class AdzunaScraper(BaseJobScraper):
    """Scrape Adzuna job listings via their REST API.

    Requires ``ADZUNA_APP_ID`` and ``ADZUNA_APP_KEY`` environment variables.

    Usage::

        async with AdzunaScraper() as scraper:
            postings = await scraper.search("data analyst", pages=3)
    """

    SOURCE = "adzuna"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._app_id = os.getenv("ADZUNA_APP_ID", "")
        self._app_key = os.getenv("ADZUNA_APP_KEY", "")

    # ── context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> AdzunaScraper:
        if not self._app_id or not self._app_key:
            raise RuntimeError(
                "ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables must be set."
            )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
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
    ) -> list[dict]:
        """Fetch *pages* pages of Adzuna results for *role*.

        Returns a list of normalised posting dicts.
        ``location`` is accepted for API compatibility but Adzuna UK endpoint
        is already scoped to GB; it is not forwarded as a query param.
        """
        if self._client is None:
            raise RuntimeError("Use 'async with AdzunaScraper() as s:' context manager.")

        results: list[dict] = []

        for page in range(1, pages + 1):
            url = _API_BASE.format(page=page)
            params = {
                "app_id": self._app_id,
                "app_key": self._app_key,
                "what": role,
                "results_per_page": _RESULTS_PER_PAGE,
                "content-type": "application/json",
            }

            log.info("adzuna.fetch_page", role=role, page=page)
            data = await self._fetch(url, params)
            if data is None:
                log.warning("adzuna.page_failed", role=role, page=page)
                break

            raw_results = data.get("results", [])
            if not raw_results:
                log.info("adzuna.no_more_results", role=role, page=page)
                break

            page_postings: list[dict] = []
            for raw in raw_results:
                parsed = self.parse_posting(raw)
                if parsed:
                    parsed["role_category"] = role
                    page_postings.append(parsed)

            log.info(
                "adzuna.page_parsed",
                role=role,
                page=page,
                raw=len(raw_results),
                parsed=len(page_postings),
            )
            results.extend(page_postings)

            # Polite API delay between pages
            if page < pages:
                await asyncio.sleep(random.uniform(0.5, 1.5))

        return results

    def parse_posting(self, raw: Any) -> dict | None:
        """Parse a single Adzuna API result dict into a normalised posting dict.

        Args:
            raw: A dict from ``results[]`` in the Adzuna API response.

        Returns:
            Normalised dict, or ``None`` if required fields are missing.
        """
        if not isinstance(raw, dict):
            return None

        title = (raw.get("title") or "").strip()
        url = (raw.get("redirect_url") or "").strip()

        if not title or not url:
            return None

        company_obj = raw.get("company") or {}
        company = (company_obj.get("display_name") or "Unknown").strip()

        location_obj = raw.get("location") or {}
        location = (location_obj.get("display_name") or "").strip()

        raw_text = (raw.get("description") or "").strip()

        posted_at: datetime | None = None
        created = raw.get("created")
        if created:
            try:
                posted_at = datetime.fromisoformat(created.rstrip("Z")).replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                pass

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

    async def _fetch(self, url: str, params: dict) -> dict | None:
        """GET *url* with *params*, exponential backoff on 429."""
        assert self._client is not None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await self._client.get(url, params=params)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 429:
                    wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                    log.warning(
                        "adzuna.rate_limited",
                        attempt=attempt,
                        wait=round(wait, 2),
                        url=url,
                    )
                    await asyncio.sleep(wait)
                    continue

                log.error(
                    "adzuna.unexpected_status",
                    status=resp.status_code,
                    url=url,
                )
                return None

            except httpx.RequestError as exc:
                wait = _BACKOFF_BASE**attempt + random.uniform(0, _JITTER_MAX)
                log.warning(
                    "adzuna.request_error",
                    error=str(exc),
                    attempt=attempt,
                    wait=round(wait, 2),
                )
                await asyncio.sleep(wait)

        log.error("adzuna.max_retries_exceeded", url=url)
        return None
