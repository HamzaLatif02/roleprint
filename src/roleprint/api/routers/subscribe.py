"""Subscribe / unsubscribe endpoints for the weekly digest."""

from __future__ import annotations

from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from roleprint.api.deps import get_session
from roleprint.db.models import Subscriber

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["subscriptions"])


# ── Request / response schemas ────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    role_preferences: List[str] = Field(
        default_factory=list,
        description="Optional list of role categories to filter the digest",
        max_length=20,
    )


class SubscribeResponse(BaseModel):
    status: str
    email: str
    message: str


# ── POST /api/subscribe ───────────────────────────────────────────────────────

@router.post("/subscribe", response_model=SubscribeResponse, status_code=201)
def subscribe(body: SubscribeRequest, session: Session = Depends(get_session)):
    """Add an email to the weekly digest subscriber list.

    - If the address is new, a subscriber row is created.
    - If the address already exists and is inactive, it is reactivated.
    - If the address already exists and is active, the preferences are
      updated and a 200 response is returned.
    """
    existing = session.scalar(
        select(Subscriber).where(Subscriber.email == body.email)
    )

    if existing:
        if existing.is_active:
            # Update preferences and return 200
            existing.role_preferences = body.role_preferences
            session.flush()
            log.info("subscribe.updated", email=body.email)
            return SubscribeResponse(
                status="updated",
                email=body.email,
                message="Your subscription preferences have been updated.",
            )
        else:
            # Reactivate
            existing.is_active = True
            existing.role_preferences = body.role_preferences
            session.flush()
            log.info("subscribe.reactivated", email=body.email)
            return SubscribeResponse(
                status="reactivated",
                email=body.email,
                message="Your subscription has been reactivated.",
            )

    sub = Subscriber(
        email=body.email,
        role_preferences=body.role_preferences,
    )
    session.add(sub)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email address is already subscribed.",
        )

    log.info("subscribe.created", email=body.email)
    return SubscribeResponse(
        status="subscribed",
        email=body.email,
        message="You're subscribed! You'll receive the next weekly digest.",
    )


# ── GET /api/unsubscribe?token=... ────────────────────────────────────────────

_UNSUBSCRIBE_SUCCESS = """
<!doctype html><html lang="en"><head><meta charset="UTF-8">
<title>Unsubscribed — Roleprint</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #f4f4f7;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; margin: 0; }}
  .card {{ background: #fff; border-radius: 10px; padding: 40px 48px;
            box-shadow: 0 2px 16px rgba(0,0,0,.08); max-width: 420px;
            text-align: center; }}
  h1 {{ margin: 0 0 12px; font-size: 22px; color: #111; }}
  p  {{ color: #6b7280; font-size: 15px; line-height: 1.6; margin: 0; }}
  .dot {{ width: 48px; height: 48px; border-radius: 50%; background: #f5a623;
           margin: 0 auto 20px; display: flex; align-items: center;
           justify-content: center; font-size: 22px; }}
</style></head><body>
<div class="card">
  <div class="dot">✓</div>
  <h1>Unsubscribed</h1>
  <p>You've been removed from the Roleprint weekly digest.<br>
     You won't receive any further emails.</p>
</div></body></html>
"""

_UNSUBSCRIBE_NOT_FOUND = """
<!doctype html><html lang="en"><head><meta charset="UTF-8">
<title>Invalid Link — Roleprint</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #f4f4f7;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; margin: 0; }}
  .card {{ background: #fff; border-radius: 10px; padding: 40px 48px;
            box-shadow: 0 2px 16px rgba(0,0,0,.08); max-width: 420px;
            text-align: center; }}
  h1 {{ margin: 0 0 12px; font-size: 22px; color: #111; }}
  p  {{ color: #6b7280; font-size: 15px; line-height: 1.6; margin: 0; }}
  .dot {{ width: 48px; height: 48px; border-radius: 50%; background: #e5e7eb;
           margin: 0 auto 20px; font-size: 22px; display: flex;
           align-items: center; justify-content: center; }}
</style></head><body>
<div class="card">
  <div class="dot">?</div>
  <h1>Link Not Found</h1>
  <p>This unsubscribe link is invalid or has already been used.<br>
     If you're still receiving emails, please contact us.</p>
</div></body></html>
"""


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=True)
def unsubscribe(
    token: str = Query(..., description="Opaque unsubscribe token from the email"),
    session: Session = Depends(get_session),
):
    """One-click unsubscribe.

    Looks up the subscriber by their opaque token, sets ``is_active=False``,
    and returns a minimal HTML confirmation page.  Returns a 200 HTML page even
    when the token is not found (to avoid leaking subscriber info).
    """
    sub = session.scalar(
        select(Subscriber).where(Subscriber.unsubscribe_token == token)
    )

    if not sub:
        log.warning("unsubscribe.token_not_found", token=token[:8] + "…")
        return HTMLResponse(content=_UNSUBSCRIBE_NOT_FOUND, status_code=200)

    if sub.is_active:
        sub.is_active = False
        session.flush()
        log.info("unsubscribe.success", email=sub.email)

    return HTMLResponse(content=_UNSUBSCRIBE_SUCCESS, status_code=200)
