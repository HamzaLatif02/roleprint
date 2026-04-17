# ── Build stage ────────────────────────────────────────────────────────────────
# Compile psycopg2 and any C extensions here, then discard the toolchain.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifests + readme (hatchling requires readme at metadata-build time)
COPY pyproject.toml README.md ./

# Stub src package so pip can resolve project metadata without copying full source
RUN mkdir -p src/roleprint && touch src/roleprint/__init__.py

# Install into a prefix we can copy to the final image.
# Use CPU-only PyTorch index to avoid pulling ~1.5 GB of CUDA wheels.
RUN pip install --upgrade pip --quiet \
 && pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    .

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Runtime-only system libs (no compiler toolchain)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# Download NLP models at build time so there's no cold-start network hit
RUN python -m spacy download en_core_web_sm --quiet
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True)"

ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Shell form so $PORT is expanded by sh before uvicorn receives it.
# Railway injects $PORT at runtime; falls back to 8000 locally.
CMD uvicorn roleprint.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
