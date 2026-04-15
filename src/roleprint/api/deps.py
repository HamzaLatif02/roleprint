"""FastAPI dependency providers.

All dependencies are functions (not classes) so they integrate cleanly
with FastAPI's ``Depends()`` and can be overridden in tests.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Optional

from sqlalchemy.orm import Session

from roleprint.db.session import SessionLocal


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, rolling back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
