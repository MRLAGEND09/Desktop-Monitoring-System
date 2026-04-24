# ============================================================================
# services/webhook.py — Async webhook delivery with HMAC-SHA256 signing
#
# Called fire-and-forget from alert creation so the request isn't blocked.
# Signature header: X-RDM-Signature: sha256=<hex>
# Payload is the JSON-serialised alert dict.
# ============================================================================
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Webhook, AlertSeverity

logger = logging.getLogger("rdm.webhook")


def _sign(secret: str, body: bytes) -> str:
    """Return HMAC-SHA256 hex digest of body using secret."""
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


async def _deliver(url: str, secret: str | None, payload: dict) -> None:
    body = json.dumps(payload, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RDM-Webhook/1.0",
    }
    if secret:
        headers["X-RDM-Signature"] = _sign(secret, body)

    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout_secs) as client:
            resp = await client.post(url, content=body, headers=headers)
            if resp.status_code >= 400:
                logger.warning("Webhook %s returned %d", url, resp.status_code)
            else:
                logger.debug("Webhook %s delivered (%d)", url, resp.status_code)
    except Exception as exc:
        logger.error("Webhook delivery failed %s: %s", url, exc)


async def fire_alert_webhooks(db: AsyncSession, alert_payload: dict) -> None:
    """
    Load active webhook subscriptions and fire them concurrently.
    Filters by severity_filter if set.
    Runs as a background task — does not raise.
    """
    severity = alert_payload.get("severity", "")
    result = await db.execute(
        select(Webhook).where(Webhook.is_active == True)
    )
    hooks = result.scalars().all()
    if not hooks:
        return

    tasks = []
    for hook in hooks:
        # Skip if severity filter is set and doesn't match
        if hook.severity_filter:
            allowed = {s.strip() for s in hook.severity_filter.split(",")}
            if severity not in allowed:
                continue
        tasks.append(_deliver(hook.url, hook.secret, alert_payload))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
