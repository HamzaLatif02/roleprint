# Roleprint

> Live NLP job market analytics — track skill demand trends across tech roles, powered by real job postings scraped daily from Reed, RemoteOK, and Adzuna.

[![CI](https://github.com/HamzaLatif02/roleprint/actions/workflows/ci.yml/badge.svg)](https://github.com/HamzaLatif02/roleprint/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-311/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Live demo → [roleprint.xyz](https://roleprint.xyz)**  
**Source → [github.com/HamzaLatif02/roleprint](https://github.com/HamzaLatif02/roleprint)**

---

## Overview

Roleprint scrapes thousands of job postings every six hours from three independent sources, runs each posting through a four-stage NLP pipeline (spaCy, NLTK VADER, BERTopic, named entity recognition), and aggregates the results into a live analytics dashboard. It tracks which skills are in demand across 10 tech roles, how demand shifts week over week, and lets users run a skill gap analysis to see precisely what to learn next for a target role. The dataset currently holds 6,000+ processed postings across 9 weeks of trend data, updated automatically without manual intervention.

There are two audiences for this project. For job seekers, the dashboard is a live, data-driven view of the market — built from actual employer requirements, not surveys or editorial opinion. For technical reviewers and hiring managers, it is a complete end-to-end data engineering project: async scraping pipeline, multi-stage NLP processing, PostgreSQL with Alembic migrations, FastAPI REST API with Redis caching, a fully responsive React dashboard, scheduled automation, and cloud deployment across three platforms — all live and publicly accessible.

---

## Features

**Data Collection**
- Three scrapers running in parallel: Reed (httpx + BeautifulSoup), RemoteOK (public JSON API), Adzuna (official REST API) — no manual data collection at any stage
- 10 role categories tracked: Data Analyst, Data Scientist, ML Engineer, Data Engineer, Software Engineer, Backend Engineer, Frontend Engineer, Product Manager, DevOps, AI Researcher
- Scraper runs every 6 hours automatically via APScheduler with cron triggers
- Deduplication on URL before every insert — no duplicate postings stored regardless of scraper restarts
- Exponential backoff and retry logic on all HTTP scrapers; individual posting failures do not abort the batch

**NLP Pipeline**
- Skill extraction using spaCy noun chunk matching against a curated vocabulary of 100+ technical and soft skills, with longest-match precedence and word-boundary anchors to prevent false positives
- Sentiment analysis using NLTK VADER — scores each posting −1.0 to +1.0 on the compound scale, plus a separate urgency signal that counts phrase matches ("immediately", "ASAP", "urgent hire", and 10 further patterns)
- Topic modelling with BERTopic backed by `all-MiniLM-L6-v2` sentence transformers — model trained once on 500+ postings, persisted to `models/topic_model.pkl`, loaded at inference time
- Named entity recognition with spaCy `en_core_web_sm` — extracts organisation names, capitalised tool names, and locations from raw posting text
- Processed in batches of 50 with per-posting error handling; a failed posting is logged and skipped without rolling back the batch

**Analytics & Dashboard**
- Skill trends over time — top skills by role with week-over-week % change, colour-coded rising and falling indicators
- Rising skills — any skill growing more than 20% week on week is surfaced automatically in the Overview and Trends panels
- Emerging skills — skills with near-zero presence four weeks ago that are now appearing in postings, ranked by growth rate
- Role comparison — cosine similarity between two role skill vectors plus Jaccard overlap %, shared skill set, and unique skills per role
- Sentiment timeline — average VADER score and cumulative urgency hits per role over 8 weeks
- Skill gap analysis — input your current skills, choose a target role, and receive a match score (0–100), a prioritised list of missing skills ranked by market demand, and your bonus skills that appear in postings but outside the top 30
- CSV export on all trend and gap analysis views
- Last scraped timestamp displayed in the sidebar with colour-coded staleness indicator

**Engineering**
- FastAPI REST API with Pydantic v2 response models and Redis response caching (5 minute TTL on all trend endpoints)
- React dashboard with Recharts visualisations, dark/light mode toggle, fully responsive mobile layout with 44px touch targets throughout
- PostgreSQL on Supabase — SQLAlchemy ORM, Alembic migrations, composite indexes on all filtered columns
- Pagination on all table views with configurable page size and ellipsis-style page controls
- Skeleton loaders, empty state screens, and error states with retry logic across every page and chart
- GitHub Actions CI — ruff format check, ruff lint, and pytest on every push to main
- Deployed on Railway (API service + scheduler worker), Vercel (dashboard), and Supabase PostgreSQL

---

## Screenshots

<!-- Add screenshots to docs/screenshots/ and they will appear here -->

<p align="center">
  <img src="docs/screenshots/overview.png" width="800"/>
</p>
<p align="center"><i>Overview page — stat bar, top skills bar chart, and rising skills panel with week-over-week badges.</i></p>

<p align="center">
  <img src="docs/screenshots/trends.png" width="800"/>
</p>
<p align="center"><i>Trends page — skill momentum line chart, rising skill sparkline cards, and emerging skills table.</i></p>

<p align="center">
  <img src="docs/screenshots/compare.png" width="800"/>
</p>
<p align="center"><i>Role comparison — Jaccard overlap percentage, Venn diagram, cosine similarity, and unique/shared skill breakdown.</i></p>

<p align="center">
  <img src="docs/screenshots/skill-gap.png" width="800"/>
</p>
<p align="center"><i>Skill gap analysis — match score ring, matched skills, prioritised missing skills, and bonus skills columns.</i></p>

<p align="center">
  <img src="docs/screenshots/sentiment.png" width="800"/>
</p>
<p align="center"><i>Sentiment timeline — VADER composite area chart with dashed urgency overlay and weekly breakdown table.</i></p>

<p align="center">
  <img src="docs/screenshots/postings.png" width="800"/>
</p>
<p align="center"><i>Postings page — paginated recent job postings with NLP enrichment fields, role filter, and configurable page size.</i></p>

---

## Tech Stack

**Backend**

| Technology | Purpose |
|---|---|
| Python 3.11 | Core language |
| FastAPI | REST API framework |
| SQLAlchemy + Alembic | ORM and database migrations |
| spaCy (`en_core_web_sm`) | Skill extraction via noun chunk matching and named entity recognition |
| NLTK VADER | Sentiment analysis on job posting text |
| BERTopic | Topic modelling across role-filtered posting corpora |
| httpx + BeautifulSoup4 | Async HTTP scraping with HTML parsing |
| APScheduler | Cron-based scraping and NLP processing jobs |
| Redis | API response caching (5 minute TTL) |
| PostgreSQL (Supabase) | Primary database |
| uvicorn | ASGI server |

**Frontend**

| Technology | Purpose |
|---|---|
| React + Vite | Component-based UI with fast HMR build tooling |
| Recharts | Data visualisation — bar, line, area, and composed charts |
| Tailwind CSS | Utility-first responsive styling with CSS variable theming |
| useApi hook | Standardised data fetching with typed error handling and abort support |

**Infrastructure**

| Technology | Purpose |
|---|---|
| Railway | API service and scheduler worker deployment |
| Vercel | React dashboard hosting with global CDN and custom domain |
| Supabase | Managed PostgreSQL database |
| GitHub Actions | CI — ruff lint, ruff format check, and pytest on every push |

---

## Architecture

The scraper, NLP pipeline, and API are three distinct concerns running across two Railway services. The scheduler worker runs separately from the API — `scrape_job` fires every 6 hours across all role categories, and `process_job` runs 1 hour later on all unprocessed postings. The FastAPI app serves the REST API only and never touches the scheduler. The React dashboard is a separate static deployment on Vercel that calls the Railway API at `/api/*` — the Vercel `rewrites` config proxies those paths to Railway so the frontend never has a hardcoded backend URL in client-side code. All three services (API, worker, dashboard) share the same Supabase PostgreSQL database via `DATABASE_URL`.

```
roleprint/
├── src/roleprint/
│   ├── scraper/
│   │   ├── base.py             BaseJobScraper abstract class
│   │   ├── reed.py             Reed.co.uk scraper (httpx + BeautifulSoup)
│   │   ├── remoteok.py         RemoteOK JSON API scraper
│   │   ├── adzuna_scraper.py   Adzuna REST API scraper
│   │   └── runner.py           Orchestrates all scrapers across role categories
│   ├── nlp/
│   │   ├── cleaner.py          HTML stripping and text normalisation
│   │   ├── skill_extractor.py  spaCy noun chunk skill matching
│   │   ├── sentiment.py        VADER sentiment scoring and urgency phrase counting
│   │   ├── topic_model.py      BERTopic training and inference
│   │   ├── ner.py              spaCy named entity recognition
│   │   ├── pipeline.py         Orchestrates all NLP modules in sequence with batching
│   │   ├── trends.py           WoW change, cosine similarity, emerging skill detection
│   │   └── ab_test.py          A/B comparison of skill extractor approaches
│   ├── db/
│   │   ├── models.py           SQLAlchemy ORM models
│   │   ├── queries.py          Typed query helpers
│   │   └── session.py          Database session factory
│   ├── api/
│   │   ├── main.py             FastAPI app factory with CORS and lifespan
│   │   ├── schemas.py          Pydantic v2 response models
│   │   ├── cache.py            Redis cache wrapper
│   │   └── routers/            skills, sentiment, topics, stats, roles, postings, export
│   └── scheduler/
│       ├── jobs.py             scrape_job and process_job implementations
│       └── main.py             APScheduler entry point
├── dashboard/
│   └── src/
│       ├── pages/              Overview, Trends, Comparison, Sentiment, SkillGap, Postings, About
│       ├── components/         EmptyState, ErrorState, Skeleton, Sidebar, Layout, ExportButton
│       ├── hooks/              useApi, useWindowWidth
│       ├── api/                client.js — typed API methods
│       └── context/            AppContext — global role filter and dark mode state
├── alembic/                    Database migration files
├── tests/                      pytest unit tests (SQLite in-memory, no infra required)
├── scripts/                    seed_demo_data.py, evaluate_sentiment.py,
│                               evaluate_topics.py, generate_trend_report.py
├── data/                       skills_vocab.json, sentiment_labels.csv
├── models/                     topic_model.pkl (saved BERTopic model)
├── reports/                    sentiment_eval.md, topic_coherence.png
├── .github/workflows/          ci.yml
├── Dockerfile                  Python 3.11-slim for Railway
├── railway.toml                Railway web service config
└── pyproject.toml              Hatchling build, production and dev dependencies
```

---

## Quick Start

### Option A — Live demo

Visit [roleprint.xyz](https://roleprint.xyz) — no account or setup required.

### Option B — Local setup

```bash
# Clone the repo
git clone https://github.com/HamzaLatif02/roleprint.git
cd roleprint

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -e ".[dev]"

# Download NLP models (first time only)
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('vader_lexicon')"

# Copy the environment template and fill in your credentials
cp .env.example .env

# Run database migrations
alembic upgrade head

# Seed demo data so the dashboard has something to show
PYTHONPATH=src python scripts/seed_demo_data.py

# Start the API server → http://localhost:8000 (OpenAPI at /docs)
python -m roleprint.api.main

# In a second terminal, start the React dashboard → http://localhost:5173
cd dashboard && npm install && npm run dev
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string, e.g. `postgresql+psycopg2://user:pass@host/db` |
| `REDIS_URL` | Yes | Redis connection URL for API response caching |
| `ADZUNA_APP_ID` | Yes | Adzuna API app ID — register at [developer.adzuna.com](https://developer.adzuna.com) |
| `ADZUNA_APP_KEY` | Yes | Adzuna API key |
| `SCRAPE_INTERVAL_HRS` | No | Scraper run cadence in hours. Default: `6` |
| `PROCESS_DELAY_HRS` | No | Hours after scrape before NLP run. Default: `1` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Default: `*` (restrict in production) |
| `VITE_API_BASE_URL` | Yes (frontend) | Railway API URL used by the React dashboard build |

> **Never commit `.env` to git.** The `.env.example` file is safe to commit — it contains no real credentials.

---

## API Reference

All endpoints that return trend or posting data accept an optional `?role_category=<role>` filter parameter. Interactive documentation is available at [roleprint.xyz/docs](https://roleprint.xyz/docs).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — always 200 if the process is up |
| `GET` | `/api/roles` | All tracked role categories with posting and processing counts |
| `GET` | `/api/stats/summary` | Total postings, roles tracked, weeks of data, last scraped timestamp |
| `GET` | `/api/skills/trending` | Top skills for the current week with week-over-week % change |
| `GET` | `/api/skills/trending/paged` | Paginated version of `/trending` with full envelope response |
| `GET` | `/api/skills/compare` | Jaccard overlap %, cosine similarity, and shared/unique skills for two roles |
| `GET` | `/api/skills/emerging` | Fastest growing skills over a configurable lookback window |
| `GET` | `/api/topics` | BERTopic clusters aggregated across all processed postings |
| `GET` | `/api/sentiment/timeline` | Average VADER sentiment and urgency score per week |
| `GET` | `/api/postings/recent` | Paginated recent postings with NLP enrichment fields |
| `POST` | `/api/skills/gap` | Skill gap analysis — body: `{"role_category": "...", "user_skills": [...]}` |
| `GET` | `/api/export/skills/trending` | Download current-week trending skills as CSV |
| `GET` | `/api/export/skills/gap` | Download skill gap analysis as CSV |

---

## NLP Methodology

**Skill extraction** uses spaCy's noun chunk parser to identify candidate phrases, which are then matched against `data/skills_vocab.json` — a curated vocabulary of 100+ skills across 11 technical sub-categories (languages, databases, cloud platforms, ML frameworks, etc.) plus soft skills. Noun chunk matching was chosen over simple keyword search because it respects phrase boundaries and reduces false positives from partial matches. The tradeoff is slightly lower recall on abbreviated skill names, which the vocabulary compensates for with common aliases per entry. The approach was validated with an A/B test against a pure regex implementation — see `src/roleprint/nlp/ab_test.py`.

**Sentiment analysis** uses NLTK VADER (Valence Aware Dictionary for sEntiment Reasoning). VADER was selected over TextBlob and fine-tuned transformer models for two reasons: its lexicon includes professional affect markers common in job descriptions (words like "competitive", "dynamic", "demanding"), and it treats the wide neutral band of professional register correctly without requiring labelled training data. The urgency signal is a separate phrase counter for 13 patterns ("ASAP", "immediately", "urgent hire", "start immediately", etc.) that VADER's compound score would absorb into a near-zero neutral value. A comparison of VADER, TextBlob, and DistilBERT-SST2 on 50 manually labelled postings is in `reports/sentiment_eval.md`, produced by `scripts/evaluate_sentiment.py`.

**Topic modelling** uses BERTopic with `all-MiniLM-L6-v2` sentence transformer embeddings. The model is trained once on a corpus of 500+ postings and persisted to `models/topic_model.pkl`; subsequent runs load the saved model for inference rather than retraining. The number of topics was selected by running BERTopic at `nr_topics ∈ {5, 10, 20}` and measuring c_v coherence via gensim. The coherence plot is in `reports/topic_coherence.png`, generated by `scripts/evaluate_topics.py`.

**Evaluation artefacts** were built deliberately to support methodology conversations. The skill extractor A/B test (`src/roleprint/nlp/ab_test.py`) measures precision, recall, and F1 for the vocabulary matcher versus spaCy noun chunks on 30 gold-standard annotated job excerpts. The sentiment evaluation (`scripts/evaluate_sentiment.py`) compares three approaches on 50 labelled postings. All evaluation outputs are committed to `reports/` so the reasoning behind each model choice is reproducible.

---

## Deployment

**Railway (API + scheduler)**

The project deploys as two Railway services from the same GitHub repository — one for the API and one for the scheduler worker. The only difference between them is the start command.

- `roleprint-api`: `uvicorn roleprint.api.main:app --host 0.0.0.0 --port $PORT`
- `roleprint-worker`: `python -m roleprint.scheduler.main`

Both services share the same environment variables set at the project level. Railway auto-deploys from the `main` branch on every push.

**Vercel (dashboard)**

The React dashboard is deployed from the `dashboard/` subdirectory. `vercel.json` rewrites all `/api/*` requests to the Railway API URL, so the frontend code uses relative paths and the backend URL never appears in the client bundle. The custom domain `roleprint.xyz` is configured in Vercel with automatic SSL provisioning. Vercel auto-deploys from `main` on every push.

**Supabase (database)**

A managed PostgreSQL instance on Supabase's free tier. All tables are created via Alembic migrations (`alembic upgrade head`) — there is no manual schema setup. Both Railway services connect via `DATABASE_URL`. Row Level Security is enabled on all tables.

---

## CI/CD

| Job | Trigger | What it runs |
|---|---|---|
| Test | Push or PR to `main` | `ruff format --check`, `ruff check`, `pytest` with coverage |

Tests run against SQLite in-memory and a mocked Redis cache — no external services are required in CI. The coverage report is uploaded as a build artefact on every run.

---

## Model Evaluation

The `reports/` directory contains reproducible evaluation artefacts for each NLP component:

```bash
# Compare VADER vs TextBlob vs DistilBERT on 50 labelled postings
pip install ".[eval]"
PYTHONPATH=src python scripts/evaluate_sentiment.py
# → reports/sentiment_eval.md

# Train BERTopic at n_topics ∈ {5, 10, 20} and measure coherence
PYTHONPATH=src python scripts/evaluate_topics.py
# → reports/topic_coherence.png
# → reports/topic_coherence.md

# A/B test: vocabulary matcher vs spaCy noun chunks on 30 annotated excerpts
PYTHONPATH=src python src/roleprint/nlp/ab_test.py
PYTHONPATH=src python src/roleprint/nlp/ab_test.py --verbose
```

---

## Development Commands

```bash
make test      # pytest with coverage report
make lint      # ruff check src/ tests/
make format    # ruff format src/ tests/
make scrape    # one-off scrape run (all role categories)
make migrate   # alembic upgrade head
```

---

## Disclaimer

This project is built for educational and portfolio purposes. Job posting data is collected from public sources in accordance with each platform's terms of service. Skill demand figures reflect the postings collected and should not be treated as statistically representative of the entire job market.

---

## Author

**Hamza Latif**  
MSc Data Science — King's College London (Distinction)  
BSc Computer Science — City, University of London (First Class)

[GitHub](https://github.com/HamzaLatif02) · [LinkedIn](https://www.linkedin.com/in/latif-hamza/) · [lhamza1020@gmail.com](mailto:lhamza1020@gmail.com)
