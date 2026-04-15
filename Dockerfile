FROM python:3.11-slim

# System packages:
#   build-essential + libpq-dev  — compile psycopg2
#   Playwright Chromium runtime  — JS-rendered job board pages
#   ca-certificates              — HTTPS fetches
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpq5 \
    ca-certificates \
    wget \
    # Playwright / Chromium system dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests first so this layer is cached when only source changes
COPY pyproject.toml ./
# Stub src package so pip can resolve the project metadata without full source
RUN mkdir -p src/roleprint && touch src/roleprint/__init__.py

# Install production deps only (no [dev] extras)
RUN pip install --upgrade pip --quiet \
 && pip install --no-cache-dir .

# Now copy the real source (replaces the stub)
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# Download models at build time — baked into the image so there's no cold-start
# network hit per container launch.
RUN python -m spacy download en_core_web_sm --quiet
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True)"
RUN python -m playwright install chromium 2>/dev/null || true

ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Railway injects $PORT; the start command in railway.toml references it.
EXPOSE 8000

# Default entrypoint — Railway overrides this per service.
CMD ["uvicorn", "roleprint.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
