# ============================================================================
# routes/devices.py — GET /devices  GET /devices/:id  PATCH heartbeat  DELETE
# ============================================================================
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..middleware.auth import get_current_user, get_device_id_from_token, require_role
from ..models import Device, DeviceStatus, User, UserRole

router = APIRouter(prefix="/devices", tags=["devices"])

_HOSTNAME_MAX = 128
_IP_MAX = 45
_OS_INFO_MAX = 256


class HeartbeatBody(BaseModel):
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    os_info: Optional[str] = None
    active_app: Optional[str] = None
    status: DeviceStatus = DeviceStatus.idle

    @field_validator("hostname", "active_app", mode="before")
    @classmethod
    def _truncate_128(cls, value):
        return value[:_HOSTNAME_MAX] if isinstance(value, str) else value

    @field_validator("ip_address", mode="before")
    @classmethod
    def _truncate_45(cls, value):
        return value[:_IP_MAX] if isinstance(value, str) else value

    @field_validator("os_info", mode="before")
    @classmethod
    def _truncate_256(cls, value):
        return value[:_OS_INFO_MAX] if isinstance(value, str) else value


@router.get("")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Device).order_by(Device.name))
    devices = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "hostname": d.hostname,
            "ip_address": d.ip_address,
            "os_info": d.os_info,
            "status": d.status.value,
            "active_app": d.active_app,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in devices
    ]


@router.get("/{device_id}")
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "id": device.id,
        "name": device.name,
        "hostname": device.hostname,
        "ip_address": device.ip_address,
        "os_info": device.os_info,
        "status": device.status.value,
        "active_app": device.active_app,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "created_at": device.created_at.isoformat(),
    }


@router.patch("/{device_id}/heartbeat")
async def heartbeat(
    device_id: str,
    body: HeartbeatBody,
    db: AsyncSession = Depends(get_db),
    token_device_id: str = Depends(get_device_id_from_token),
):
    if token_device_id != device_id:
        raise HTTPException(status_code=403, detail="Token device_id mismatch")

    device = await db.get(Device, device_id)
    if not device:
        device = Device(id=device_id, name=device_id)
        db.add(device)

    device.last_seen = datetime.now(timezone.utc)
    device.status = body.status
    if body.hostname:
        device.hostname = body.hostname
    if body.ip_address:
        device.ip_address = body.ip_address
    if body.os_info:
        device.os_info = body.os_info
    if body.active_app:
        device.active_app = body.active_app
    return {"ok": True}


@router.delete("/{device_id}", dependencies=[Depends(require_role(UserRole.admin))])
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    return {"ok": True}


class BulkStatusItem(BaseModel):
    device_id: str
    status: DeviceStatus


@router.post("/bulk-status", dependencies=[Depends(require_role(UserRole.monitor))])
async def bulk_status(
    items: list[BulkStatusItem],
    db: AsyncSession = Depends(get_db),
):
    if len(items) > 200:
        raise HTTPException(status_code=400, detail="Max 200 items per request")

    ids = [item.device_id for item in items]
    result = await db.execute(select(Device).where(Device.id.in_(ids)))
    device_map = {device.id: device for device in result.scalars().all()}

    updated = []
    for item in items:
        device = device_map.get(item.device_id)
        if device:
            device.status = item.status
            device.last_seen = datetime.now(timezone.utc)
            updated.append(item.device_id)

    return {
        "updated": updated,
        "not_found": [item.device_id for item in items if item.device_id not in device_map],
    }
