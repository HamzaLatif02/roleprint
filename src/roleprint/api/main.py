"""FastAPI application entry point for Roleprint."""

from __future__ import annotations

import os

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from roleprint.api import cache
from roleprint.api.deps import get_session
from roleprint.api.routers import (  # noqa: E402
    postings,
    roles,
    sentiment,
    skills,
    stats,
    subscribe,
    topics,
)
from roleprint.api.schemas import HealthResponse

log = structlog.get_logger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Roleprint API",
        description="NLP-powered job market analytics — skills, topics, sentiment and trends.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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
    app.include_router(skills.router)
    app.include_router(topics.router)
    app.include_router(sentiment.router)
    app.include_router(roles.router)
    app.include_router(postings.router)
    app.include_router(stats.router)
    app.include_router(subscribe.router)

    # ── /health ───────────────────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health(session: Session = Depends(get_session)):
        """Liveness/readiness probe.

        Returns HTTP 200 with ``status=ok`` when the database is reachable.
        Returns HTTP 503 with ``status=degraded`` when the database is down.
        Redis being unavailable is reflected in the ``redis`` field but does
        NOT change the HTTP status code (cache is optional).
        """
        db_status = "connected"
        http_status = 200
        try:
            session.execute(text("SELECT 1"))
        except Exception as exc:
            db_status = str(exc)
            http_status = 503

        redis_status = "connected" if cache.is_available() else "unavailable"

        body = HealthResponse(
            status="ok" if http_status == 200 else "degraded",
            db=db_status,
            redis=redis_status,
            version="0.1.0",
        )
        return JSONResponse(content=body.model_dump(), status_code=http_status)

    return app


app = create_app()
