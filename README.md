# Roleprint

> NLP-powered job market analytics — live skill trends, sentiment, and role comparisons across thousands of job postings.

**Live dashboard → [roleprint.xyz](https://roleprint.xyz)**  
**API docs → [api.roleprint.xyz/docs](https://api.roleprint.xyz/docs)**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser                                                                 │
│  roleprint.xyz                                                           │
│  React + Vite (Tailwind · Recharts)                                      │
│  Vercel — static CDN                                                     │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │  HTTPS  (CORS: roleprint.xyz)
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Railway — web service                                                  │
│  api.roleprint.xyz                                                      │
│  FastAPI + Uvicorn                                                      │
│  /api/skills  /api/sentiment  /api/topics  /api/stats  …               │
│  Redis cache (Railway add-on, 5-min TTL)                               │
└───────────────────────┬────────────────────────────────────────────────┘
                        │  SQLAlchemy / psycopg2
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│  Supabase — PostgreSQL                                                 │
│  job_postings · processed_postings · skill_trends · subscribers        │
│  Alembic migrations (0001 initial schema · 0002 subscribers)           │
└───────────────────────────────────────────────────────────────────────┘
                        ▲
                        │  SQLAlchemy / psycopg2
┌───────────────────────┴────────────────────────────────────────────────┐
│  Railway — worker service                                               │
│  APScheduler (BlockingScheduler, UTC cron)                              │
│                                                                         │
│  scrape_job     every 6 h — Reed + RemoteOK → job_postings             │
│  process_job    every 6 h (1 h offset) — NLP pipeline                  │
│                   spaCy NER · VADER sentiment · skill extractor         │
│                   BERTopic topics · skill_trends aggregation            │
│  weekly_digest  Mondays 08:00 UTC — Jinja2 HTML email via SendGrid      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How it works

### Data collection
The scraper hits **Reed** (UK job board) and **RemoteOK** via `httpx` with exponential back-off, user-agent rotation, and `robots.txt` compliance. Each 6-hour run fetches the latest postings per role category, deduplicates by URL in a single bulk query, and inserts new rows.

### NLP pipeline
Every new posting passes through five stages:
1. **Cleaner** — strips HTML, normalises Unicode, removes boilerplate (Equal Opportunity clauses, legal disclaimers)
2. **Skill extractor** — regex patterns compiled from a 130-skill vocabulary (11 technical sub-categories + soft skills); longest-match wins, word-boundary anchors prevent false positives
3. **Sentiment** — VADER compound score (−1 to +1) + urgency phrase counter (13 patterns: *ASAP*, *immediately*, *urgent hire*, …)
4. **NER** — spaCy `en_core_web_sm`; organisation names and capitalised technical tools extracted
5. **Topic model** — BERTopic with `all-MiniLM-L6-v2`; trained once, persisted to `models/topic_model.pkl`, assigned per posting

### Trend aggregation
After each NLP batch, `skill_trends` rows are upserted with weekly `mention_count` and `pct_of_postings`. Week-over-week change and Jaccard/cosine comparisons are computed in Python for SQLite + Postgres portability.

### Dashboard
Four views built with React 18, Recharts, and Tailwind CSS (dark/light mode):

| Page | Key charts |
|------|-----------|
| Overview | Stat bar · top-10 skills BarChart · rising skills panel |
| Trends | Momentum LineChart · sparkline cards with WoW badges · emerging table |
| Compare | Venn circles · Jaccard % + cosine similarity · unique/shared skill pills |
| Sentiment | ComposedChart (area + dashed urgency line) · weekly breakdown table |

### Weekly digest
Every Monday, the scheduler generates an HTML email (Jinja2 table-based, Gmail/Outlook compatible) with:
- Top 10 skills + ▲▼ week-over-week arrows
- 3 emerging skills callout cards
- Sentiment summary per role

Sent via SendGrid to the `subscribers` table. One-click unsubscribe via opaque token.

---

## Local Development

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
| Node.js | 20+ |

### Steps

```bash
# Clone
git clone https://github.com/HamzaLatif02/roleprint.git
cd roleprint

# Copy env and fill in credentials
cp .env.example .env

# Install Python deps (includes Playwright)
make install

# Download NLP models (first time only)
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('vader_lexicon')"

# Run database migrations
make migrate

# Seed demo data so the dashboard isn't empty
PYTHONPATH=src python scripts/seed_demo_data.py

# Start the API  →  http://localhost:8000  (OpenAPI at /docs)
make dev

# Start the dashboard  →  http://localhost:5173
cd dashboard && npm install && npm run dev
```

---

## Deployment

### Supabase (database)

1. Create a new Supabase project
2. Copy **Settings → Database → Connection string** (URI / psycopg2 format)
3. Run migrations: `DATABASE_URL=<uri> alembic upgrade head`
4. Seed demo data: `DATABASE_URL=<uri> python scripts/seed_demo_data.py`

### Vercel (dashboard)

1. Push repo to GitHub
2. **Vercel → New Project → Import** → select `roleprint`
3. Set **Root Directory** to `dashboard`
4. Vercel auto-detects Vite — no build command override needed
5. Add environment variable: `VITE_API_BASE_URL` = Railway web service URL
6. Deploy → assign custom domain `roleprint.xyz`

### Railway (API + worker)

```
1. New Project → Deploy from GitHub → roleprint
2. Rename auto-created service to "web"
3. + New Service → GitHub Repo → same repo → rename to "worker"
4. Worker service → Settings → Start Command:
     python -m roleprint.scheduler.main

Shared environment variables (set on both services):
  DATABASE_URL         postgresql+psycopg2://...   (Supabase connection string)
  REDIS_URL            redis://...                  (Railway Redis add-on)
  RESEND_API_KEY       from Resend dashboard
  FROM_EMAIL           digest@roleprint.io
  SITE_URL             https://roleprint.xyz
  CORS_ORIGINS         https://roleprint.xyz,https://www.roleprint.xyz
  SCRAPE_INTERVAL_HRS  6
```

Both services share the same `Dockerfile`. The start command is the only difference.

---

## Project Structure

```
roleprint/
├── src/roleprint/
│   ├── api/           FastAPI app, routers, Pydantic schemas, Redis cache
│   ├── db/            SQLAlchemy models, Alembic env, typed query helpers
│   ├── nlp/           Cleaner, skill extractor, VADER, NER, BERTopic, pipeline
│   ├── scraper/       Reed + RemoteOK scrapers, dedup, async runner
│   └── scheduler/     APScheduler jobs, Jinja2 digest template, entry point
├── dashboard/         React + Vite + Tailwind + Recharts
├── tests/             208 tests — SQLite in-memory, no infra required
├── alembic/           Migrations
├── scripts/           seed_demo_data.py · generate_trend_report.py · evaluate_sentiment.py · evaluate_topics.py
├── data/              sentiment_labels.csv (50 labelled) · skill_labels.csv (30 labelled)
├── reports/           sentiment_eval.md · topic_coherence.md · topic_coherence.png
├── Dockerfile         Python 3.11-slim for Railway (API + worker)
├── railway.toml       Railway web service config
└── pyproject.toml     Hatchling build, prod + dev deps
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills/trending` | Current-week skills with WoW change |
| GET | `/api/skills/compare` | Jaccard overlap + cosine similarity for 2+ roles |
| GET | `/api/skills/emerging` | Fastest-growing skills vs N weeks ago |
| GET | `/api/topics` | BERTopic clusters aggregated across postings |
| GET | `/api/sentiment/timeline` | Avg VADER score + urgency per week |
| GET | `/api/roles` | Role categories with posting counts |
| GET | `/api/postings/recent` | Latest postings with NLP enrichment |
| GET | `/api/stats/summary` | Dataset statistics |
| POST | `/api/subscribe` | Subscribe to weekly digest |
| GET | `/api/unsubscribe` | One-click unsubscribe via token |
| GET | `/health` | Liveness probe (DB + Redis status) |

All trend endpoints accept `?role_category=<role>` filter. Full schema at `/docs`.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push:
- `ruff format --check` + `ruff check` (zero lint errors required)
- `pytest` — 208 tests, SQLite in-memory, no external services needed

Railway and Vercel auto-deploy from the `main` branch on merge.

---

## Development commands

```bash
make test      # pytest with coverage
make lint      # ruff check src/ tests/
make format    # ruff format src/ tests/
make scrape    # one-off scrape run
make migrate   # alembic upgrade head
```

---

## Model Evaluation

Analytical artefacts for interview methodology discussions.

### Sentiment model comparison

Compares VADER (production), TextBlob, and DistilBERT (SST-2) on 50 manually-labelled
job postings.  VADER wins on this domain because its lexicon includes professional affect
markers and the wider neutral band (pos ≥ 0.15, neg ≤ −0.05) handles muted professional
register better than the default ±0.05.

```bash
pip install textblob transformers torch
python -m textblob.download_corpora
PYTHONPATH=src python scripts/evaluate_sentiment.py
# report → reports/sentiment_eval.md
```

### BERTopic coherence evaluation

Trains BERTopic at n_topics ∈ [5, 10, 20] and measures c_v coherence via gensim.
Justifies the production `nr_topics` choice.

```bash
pip install gensim matplotlib
PYTHONPATH=src python scripts/evaluate_topics.py
# plot  → reports/topic_coherence.png
# report → reports/topic_coherence.md
```

### Skill extractor A/B test

Compares the production vocab-regex extractor (A) against a spaCy noun-chunk heuristic
(B) on 30 gold-standard annotated job excerpts.  Measures precision, recall, and F1 for
each approach.

```bash
PYTHONPATH=src python src/roleprint/nlp/ab_test.py
PYTHONPATH=src python src/roleprint/nlp/ab_test.py --verbose   # per-example predictions
```

Install all eval deps at once:
```bash
pip install ".[eval]"
```
