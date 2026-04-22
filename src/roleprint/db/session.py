import os
from collections.abc import Generator
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

# Lazy singletons — created on first use so import doesn't require DATABASE_URL
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ["DATABASE_URL"]
        # Supabase transaction-mode pooler (port 6543) runs PgBouncer.
        # Disable SQLAlchemy's connection pool and let PgBouncer manage
        # pooling; also set a statement timeout as a safety net.
        if "pooler.supabase.com" in url or ":6543" in url:
            from sqlalchemy.pool import NullPool

            _engine = create_engine(
                url,
                poolclass=NullPool,
                connect_args={"options": "-c statement_timeout=30000"},
            )
        else:
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
    return _engine


def SessionLocal() -> Session:  # type: ignore[override]
    """Return a new SQLAlchemy Session bound to the configured database."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal()


def get_session() -> Generator[Session, None, None]:
    """Yield a database session; used as a FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
