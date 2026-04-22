"""Redis cache helpers.

Designed to degrade gracefully: if Redis is unreachable the helpers
return cache-miss / no-op results rather than raising, so endpoints
continue to work (just without caching).
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_redis_client: Any | None = None
_redis_unavailable: bool = False  # set True after first connection failure


def _get_client() -> Any | None:
    """Lazily connect to Redis; returns ``None`` if unavailable."""
    global _redis_client, _redis_unavailable

    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        import redis

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _redis_client = client
        log.debug("cache.redis_connected", url=url)
    except Exception as exc:
        _redis_unavailable = True
        log.warning("cache.redis_unavailable", error=str(exc))

    return _redis_client


def get(key: str) -> Any | None:
    """Return a cached value, or ``None`` on miss / error."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        log.warning("cache.get_error", key=key, error=str(exc))
        return None


def set(key: str, value: Any, ttl: int = 300) -> None:
    """Store *value* as JSON with a TTL (seconds).  Silently no-ops on error."""
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        log.warning("cache.set_error", key=key, error=str(exc))


def delete(key: str) -> None:
    """Delete a key.  No-op on error."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        pass


def flush_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (use sparingly)."""
    client = _get_client()
    if client is None:
        return
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
    except Exception as exc:
        log.warning("cache.flush_error", pattern=pattern, error=str(exc))


def is_available() -> bool:
    """Return True if Redis is reachable."""
    return _get_client() is not None


# Expose reset for testing
def _reset() -> None:
    global _redis_client, _redis_unavailable
    _redis_client = None
    _redis_unavailable = False
