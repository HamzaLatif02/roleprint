.PHONY: install dev test migrate scrape lint format

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"
	playwright install chromium

# ── Development ───────────────────────────────────────────────────────────────
dev:
	uvicorn roleprint.api.main:app --reload --host 0.0.0.0 --port 8000

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --cov=src/roleprint --cov-report=term-missing

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate-down:
	alembic downgrade -1

# ── Scraping ──────────────────────────────────────────────────────────────────
scrape:
	PYTHONPATH=src python -m roleprint.scraper.runner

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
