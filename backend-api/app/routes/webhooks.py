# ============================================================================
# routes/webhooks.py — CRUD for outbound webhook subscriptions
#
# Only admins can manage webhooks.
# POST   /webhooks           — register a webhook URL
# GET    /webhooks           — list all webhooks
# DELETE /webhooks/{id}      — remove a webhook
# PATCH  /webhooks/{id}      — update url / secret / filter / active flag
# POST   /webhooks/{id}/test — fire a test payload to verify the endpoint
# ============================================================================
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models import User, UserRole, Webhook
from ..middleware.auth import get_current_user, require_role
from ..services.webhook import _deliver

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_admin = Depends(require_role(UserRole.admin))


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url:             HttpUrl
    secret:          Optional[str] = None   # caller-supplied or auto-generated
    severity_filter: str           = ""     # "high,critical" or "" for all


class WebhookPatch(BaseModel):
    url:             Optional[HttpUrl] = None
    secret:          Optional[str]     = None
    severity_filter: Optional[str]     = None
    is_active:       Optional[bool]    = None


def _serialize(h: Webhook) -> dict:
    return {
        "id":              h.id,
        "url":             h.url,
        # Never expose the raw secret — return a SHA-256 fingerprint instead
        "secret_hint":     hashlib.sha256(h.secret.encode()).hexdigest()[:8] if h.secret else None,
        "severity_filter": h.severity_filter,
        "is_active":       h.is_active,
        "created_at":      h.created_at.isoformat(),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201, dependencies=[_admin])
async def create_webhook(
    body: WebhookCreate,
    db:   AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret = body.secret or secrets.token_hex(32)
    hook = Webhook(
        url             = str(body.url),
        secret          = secret,
        severity_filter = body.severity_filter,
        created_by      = current_user.id,
    )
    db.add(hook)
    await db.flush()
    # Return the secret once — it won't be shown again
    return {**_serialize(hook), "secret": secret}


@router.get("", dependencies=[_admin])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook).order_by(Webhook.created_at))
    return [_serialize(h) for h in result.scalars().all()]


@router.patch("/{hook_id}", dependencies=[_admin])
async def update_webhook(
    hook_id: int,
    body:    WebhookPatch,
    db:      AsyncSession = Depends(get_db),
):
    hook = await db.get(Webhook, hook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if body.url is not None:
        hook.url = str(body.url)
    if body.secret is not None:
        hook.secret = body.secret
    if body.severity_filter is not None:
        hook.severity_filter = body.severity_filter
    if body.is_active is not None:
        hook.is_active = body.is_active
    return _serialize(hook)


@router.delete("/{hook_id}", status_code=200, dependencies=[_admin])
async def delete_webhook(hook_id: int, db: AsyncSession = Depends(get_db)):
    hook = await db.get(Webhook, hook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(hook)
    return {"ok": True}


@router.post("/{hook_id}/test", dependencies=[_admin])
async def test_webhook(hook_id: int, db: AsyncSession = Depends(get_db)):
    hook = await db.get(Webhook, hook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    test_payload = {
        "event":    "test",
        "message":  "RDM webhook test",
        "severity": "low",
    }
    await _deliver(hook.url, hook.secret, test_payload)
    return {"ok": True}
