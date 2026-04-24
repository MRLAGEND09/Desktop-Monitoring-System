# ============================================================================
# routes/alerts.py — GET /alerts  POST /alerts  PATCH /alerts/:id/resolve
# ============================================================================
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from ..db import get_db
from ..models import Alert, AlertSeverity, User, UserRole
from ..middleware.auth import get_current_user, require_role
from ..services.webhook import fire_alert_webhooks
from ..routes.stream import broadcast_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertBody(BaseModel):
    device_id: Optional[str] = None
    severity:  AlertSeverity
    message:   str


@router.get("")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(500)
    )
    alerts = result.scalars().all()
    return [
        {
            "id":          a.id,
            "device_id":   a.device_id,
            "severity":    a.severity.value,
            "message":     a.message,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "created_at":  a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("", status_code=201,
             dependencies=[Depends(require_role(UserRole.monitor))])
async def create_alert(
    body:       AlertBody,
    background: BackgroundTasks,
    db:         AsyncSession = Depends(get_db),
):
    alert = Alert(
        device_id = body.device_id,
        severity  = body.severity,
        message   = body.message,
    )
    db.add(alert)
    await db.flush()  # get alert.id before background task runs

    payload = {
        "event":      "alert.created",
        "id":         alert.id,
        "device_id":  alert.device_id,
        "severity":   alert.severity.value,
        "message":    alert.message,
        "created_at": alert.created_at.isoformat(),
    }
    background.add_task(fire_alert_webhooks, db, payload)
    background.add_task(broadcast_alert, payload)
    return {"ok": True, "id": alert.id}


@router.patch("/{alert_id}/resolve",
              dependencies=[Depends(require_role(UserRole.monitor))])
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.resolved_at:
        raise HTTPException(status_code=409, detail="Already resolved")
    alert.resolved_at = datetime.now(timezone.utc)
    return {"ok": True}
