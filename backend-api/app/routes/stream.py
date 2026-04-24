# ============================================================================
# routes/stream.py — Server-Sent Events (SSE) for real-time dashboard updates
#
# GET /stream/alerts   — push new alerts as they arrive (admin/monitor)
# GET /stream/devices  — push device status changes every N seconds
#
# Client usage:
#   const es = new EventSource('/api/stream/alerts', {
#     headers: { Authorization: `Bearer ${token}` }
#   });
#   es.addEventListener('alert', e => console.log(JSON.parse(e.data)));
# ============================================================================
import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError

from ..config import settings
from ..db import get_db
from ..models import Alert, Device, User, UserRole
from ..middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/stream", tags=["stream"])

# In-memory broadcast queue: alert dicts are pushed here by the alert route
# and consumed by all SSE subscribers.
_alert_queues: list[asyncio.Queue] = []


async def broadcast_alert(payload: dict) -> None:
    """Push an alert payload to all active SSE subscribers."""
    for q in _alert_queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # slow consumer — skip rather than block


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _alert_generator(request: Request) -> AsyncGenerator[str, None]:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _alert_queues.append(q)
    try:
        yield _sse("connected", {"ts": datetime.now(timezone.utc).isoformat()})
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(q.get(), timeout=15)
                yield _sse("alert", payload)
            except asyncio.TimeoutError:
                # Keepalive comment so proxies don't close idle connections
                yield ": keepalive\n\n"
    finally:
        _alert_queues.remove(q)


async def _device_generator(
    request: Request, db: AsyncSession
) -> AsyncGenerator[str, None]:
    yield _sse("connected", {"ts": datetime.now(timezone.utc).isoformat()})
    while True:
        if await request.is_disconnected():
            break
        result = await db.execute(
            select(Device).order_by(Device.last_seen.desc()).limit(200)
        )
        devices = result.scalars().all()
        data = [
            {
                "id":        d.id,
                "name":      d.name,
                "status":    d.status.value,
                "active_app": d.active_app,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            }
            for d in devices
        ]
        yield _sse("devices", {"devices": data, "ts": datetime.now(timezone.utc).isoformat()})
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            break


async def _require_sse_auth(
    request: Request,
    token: Optional[str] = Query(default=None),
) -> User:
    """
    SSE auth: EventSource can't set headers, so we accept JWT via ?token=
    as well as the standard Authorization: Bearer header.
    """
    from fastapi import HTTPException, status
    from sqlalchemy import select
    from ..db import AsyncSessionLocal

    raw = token
    if not raw:
        auth_header = request.headers.get("Authorization", "")
        raw = auth_header.removeprefix("Bearer ").strip() or None
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    try:
        payload = jwt.decode(raw, settings.jwt_secret,
                             algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token")

    async with AsyncSessionLocal() as db:
        user = await db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found")
    return user


@router.get("/alerts")
async def stream_alerts(
    request: Request,
    current_user: User = Depends(_require_sse_auth),
):
    if current_user.role not in (UserRole.admin, UserRole.monitor):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    return StreamingResponse(
        _alert_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/devices")
async def stream_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_sse_auth),
):
    return StreamingResponse(
        _device_generator(request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
