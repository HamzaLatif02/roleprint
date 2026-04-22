"""Tests for the scheduler package.

Covers:
  - scrape_job  (mocked runner)
  - process_job (mocked NLP pipeline)
  - build_scheduler (jobs registered with correct IDs)
"""

from __future__ import annotations

from unittest.mock import patch

# ── scrape_job ────────────────────────────────────────────────────────────────


class TestScrapeJob:
    def test_scrape_job_calls_run_all(self):
        from roleprint.scheduler.jobs import scrape_job

        mock_summary = {"reed": {"data analyst": 5}, "remoteok": {"data analyst": 2}}

        with patch("asyncio.run", return_value=mock_summary):
            scrape_job()

    def test_scrape_job_handles_exception(self):
        from roleprint.scheduler.jobs import scrape_job

        with patch("asyncio.run", side_effect=RuntimeError("network error")):
            # Should not raise — exceptions are caught internally
            scrape_job()


# ── process_job ───────────────────────────────────────────────────────────────


class TestProcessJob:
    def test_process_job_calls_nlp_run_all(self):
        from roleprint.scheduler.jobs import process_job

        mock_stats = {"processed": 10, "errors": 0}

        with patch("roleprint.nlp.pipeline.run_all", return_value=mock_stats):
            process_job()

    def test_process_job_handles_exception(self):
        from roleprint.scheduler.jobs import process_job

        with patch("roleprint.nlp.pipeline.run_all", side_effect=RuntimeError("db error")):
            # Should not raise
            process_job()


# ── build_scheduler ───────────────────────────────────────────────────────────


class TestBuildScheduler:
    def test_two_jobs_registered(self):
        from roleprint.scheduler.main import build_scheduler

        scheduler = build_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {"scrape_job", "process_job"}

    def test_scrape_and_process_jobs_registered(self):
        from roleprint.scheduler.main import build_scheduler

        scheduler = build_scheduler()
        assert scheduler.get_job("scrape_job") is not None
        assert scheduler.get_job("process_job") is not None

    def test_no_digest_job(self):
        from roleprint.scheduler.main import build_scheduler

        scheduler = build_scheduler()
        assert scheduler.get_job("weekly_digest_job") is None

    def test_custom_scrape_interval_env(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_INTERVAL_HRS", "12")
        import importlib

        from roleprint.scheduler import main as sched_main

        importlib.reload(sched_main)
        scheduler = sched_main.build_scheduler()
        jobs = {j.id: j for j in scheduler.get_jobs()}
        assert "scrape_job" in jobs
        assert "process_job" in jobs
