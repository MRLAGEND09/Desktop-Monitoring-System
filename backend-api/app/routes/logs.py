# ============================================================================
# routes/logs.py — GET /logs (paginated)  +  POST /logs (device ingestion)
# ============================================================================
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, field_validator
from typing import Optional
from ..db import get_db
from ..models import ActivityLog, AppCategory, Device, User
from ..middleware.auth import get_current_user, get_device_id_from_token

router = APIRouter(prefix="/logs", tags=["logs"])

_APP_MAX   = 128
_TITLE_MAX = 512


class LogBody(BaseModel):
    device_id:    str
    active_app:   Optional[str] = None
    window_title: Optional[str] = None
    app_category: AppCategory   = AppCategory.unknown
    idle_seconds: int           = 0
    is_idle:      bool          = False

    @field_validator("device_id", mode="before")
    @classmethod
    def _validate_device_id(cls, v):
        if not isinstance(v, str) or len(v) > 64:
            raise ValueError("device_id must be a string ≤ 64 chars")
        return v

    @field_validator("active_app", mode="before")
    @classmethod
    def _truncate_app(cls, v):
        return v[:_APP_MAX] if isinstance(v, str) else v

    @field_validator("window_title", mode="before")
    @classmethod
    def _truncate_title(cls, v):
        return v[:_TITLE_MAX] if isinstance(v, str) else v

    @field_validator("idle_seconds", mode="before")
    @classmethod
    def _clamp_idle(cls, v):
        return max(0, min(int(v), 86_400))  # cap at 24h


@router.get("")
async def get_logs(
    device_id: Optional[str] = Query(None),
    from_ts:   Optional[datetime] = Query(None, alias="from"),
    to_ts:     Optional[datetime] = Query(None, alias="to"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db:        AsyncSession = Depends(get_db),
    _:         User         = Depends(get_current_user),
):
    filters = []
    if device_id: filters.append(ActivityLog.device_id == device_id)
    if from_ts:   filters.append(ActivityLog.created_at >= from_ts)
    if to_ts:     filters.append(ActivityLog.created_at <= to_ts)

    stmt = (
        select(ActivityLog)
        .where(and_(*filters))
        .order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    logs   = result.scalars().all()

    return [
        {
            "id":           l.id,
            "device_id":    l.device_id,
            "active_app":   l.active_app,
            "window_title": l.window_title,
            "app_category": l.app_category.value,
            "idle_seconds": l.idle_seconds,
            "is_idle":      l.is_idle,
            "created_at":   l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.post("", status_code=201)
async def ingest_log(
    body:            LogBody,
    db:              AsyncSession  = Depends(get_db),
    token_device_id: str           = Depends(get_device_id_from_token),
):
    # Ensure the token's device matches the body's device_id
    if token_device_id != body.device_id:
        raise HTTPException(status_code=403, detail="Token device_id mismatch")

    # Auto-provision device if missing.
    d = await db.get(Device, body.device_id)
    if not d:
        d = Device(id=body.device_id, name=body.device_id)
        db.add(d)

    log = ActivityLog(
        device_id    = body.device_id,
        active_app   = body.active_app,
        window_title = body.window_title,
        app_category = body.app_category,
        idle_seconds = body.idle_seconds,
        is_idle      = body.is_idle,
    )
    db.add(log)
    return {"ok": True}
