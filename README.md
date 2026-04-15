# Roleprint

> NLP-powered job market analytics — scrape, analyze, and surface trends across thousands of job postings in real time.

---

## What it does

Roleprint continuously scrapes job boards (Reed, RemoteOK, LinkedIn), runs NLP pipelines over raw postings, and exposes a FastAPI backend + React dashboard so you can:

- Track skill demand over time (e.g. "how fast is Rust growing vs Go?")
- Cluster job roles by topic (BERTopic)
- Get alerts when a new role pattern emerges in your target market

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Roleprint                            │
│                                                             │
│  ┌──────────┐   raw    ┌──────────┐  entities  ┌────────┐  │
│  │ Scraper  │ ───────► │   NLP    │ ──────────► │   DB   │  │
│  │(Playwright│         │ Pipeline │             │(Postgres│  │
│  │  / httpx)│         │(spaCy,   │             │+ Alembic│  │
│  └──────────┘         │ BERTopic)│             └────────┘  │
│                        └──────────┘                  │      │
│  ┌───────────┐                                       │      │
│  │ Scheduler │  (APScheduler — runs scraper on cron) │      │
│  └───────────┘                                       ▼      │
│                                               ┌──────────┐  │
│                                               │ FastAPI  │  │
│                                               │   API    │  │
│                                               └────┬─────┘  │
│                                                    │        │
│                                               ┌────▼─────┐  │
│                                               │  React   │  │
│                                               │Dashboard │  │
│                                               │  (Vite)  │  │
│                                               └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 20+ (for dashboard)

### Steps

```bash
# 1. Clone
git clone https://github.com/HamzaLatif02/roleprint.git
cd roleprint

# 2. Copy env
cp .env.example .env
# Edit .env with your local DB / Redis credentials

# 3. Install Python deps + Playwright
make install

# 4. Run migrations
make migrate

# 5. Start API
make dev

# 6. (Optional) Start dashboard
cd src/roleprint/dashboard
npm install && npm run dev
```

---

## Project Structure

```
roleprint/
├── src/
│   └── roleprint/
│       ├── scraper/        # Playwright + httpx scrapers per job board
│       ├── nlp/            # spaCy pipelines, BERTopic, skill extractor
│       ├── db/             # SQLAlchemy models, Alembic env, query helpers
│       ├── api/            # FastAPI app, routers, schemas
│       ├── scheduler/      # APScheduler job definitions
│       ├── dashboard/      # React + Vite frontend
│       └── scripts/        # One-off utilities (seed, backfill, export)
├── tests/
├── alembic/
├── pyproject.toml
├── Makefile
└── .env.example
```

---

## Development

```bash
make test      # run test suite with coverage
make lint      # ruff check
make format    # ruff format
make scrape    # trigger a one-off scrape run
```

---

## Roadmap

- [ ] Phase 1 — Project scaffold
- [ ] Phase 2 — DB schema + Alembic migrations
- [ ] Phase 3 — Scraper pipeline (Reed, RemoteOK)
- [ ] Phase 4 — NLP pipeline (skill extraction, topic modelling)
- [ ] Phase 5 — FastAPI endpoints
- [ ] Phase 6 — APScheduler integration
- [ ] Phase 7 — React dashboard
