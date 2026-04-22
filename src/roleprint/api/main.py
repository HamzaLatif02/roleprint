"""FastAPI application entry point for Roleprint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from roleprint.api import cache
from roleprint.api.routers import (  # noqa: E402
    export,
    postings,
    roles,
    sentiment,
    skills,
    stats,
    topics,
)

log = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────────
    try:
        from alembic import command
        from alembic.config import Config
        import pathlib

        ini_path = pathlib.Path(__file__).resolve().parents[3] / "alembic.ini"
        alembic_cfg = Config(str(ini_path))
        command.upgrade(alembic_cfg, "head")
        log.info("migrations.done")
    except Exception as exc:
        log.warning("migrations.failed", error=str(exc))
        # don't crash the server — let it start anyway

    yield
    # ── shutdown (nothing to clean up) ────────────────────────────────────────


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title="Roleprint API",
        description="NLP-powered job market analytics — skills, topics, sentiment and trends.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS — set CORS_ORIGINS in production to the Vercel domain, e.g.:
    #   CORS_ORIGINS=https://roleprint.xyz,https://www.roleprint.xyz
    # Falls back to wildcard for local development.
    raw_origins = os.environ.get("CORS_ORIGINS", "*")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(export.router)
    app.include_router(skills.router)
    app.include_router(topics.router)
    app.include_router(sentiment.router)
    app.include_router(roles.router)
    app.include_router(postings.router)
    app.include_router(stats.router)

    # ── /health ───────────────────────────────────────────────────────────────

    @app.get("/health", tags=["meta"])
    def health():
        """Liveness probe — always 200 if the process is up."""
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("roleprint.api.main:app", host="0.0.0.0", port=port)
