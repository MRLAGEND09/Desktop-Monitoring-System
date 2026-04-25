# ========================================================================

# routes/devices.py — FIXED VERSION (Production Ready)

# ========================================================================

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional

from ..db import get_db
from ..models import Device, DeviceStatus, User, UserRole
from ..middleware.auth import (
get_current_user,
get_device_id_from_token,
require_role,
)

router = APIRouter(prefix="/devices", tags=["devices"])

_HOSTNAME_MAX   = 128
_IP_MAX         = 45
_OS_INFO_MAX    = 256
_ACTIVE_APP_MAX = 128

# =========================

# SCHEMA

# =========================

class HeartbeatBody(BaseModel):
hostname:    Optional[str] = None
ip_address:  Optional[str] = None
os_info:     Optional[str] = None
active_app:  Optional[str] = None

```
# ⚠️ IMPORTANT: Remove status from client control
# status is controlled by backend logic only

@field_validator("hostname", "active_app", mode="before")
@classmethod
def _truncate_128(cls, v):
    return v[:_HOSTNAME_MAX] if isinstance(v, str) else v

@field_validator("ip_address", mode="before")
@classmethod
def _truncate_45(cls, v):
    return v[:_IP_MAX] if isinstance(v, str) else v

@field_validator("os_info", mode="before")
@classmethod
def _truncate_256(cls, v):
    return v[:_OS_INFO_MAX] if isinstance(v, str) else v
```

# =========================

# GET ALL DEVICES

# =========================

@router.get("")
async def list_devices(
db: AsyncSession = Depends(get_db),
_:  User         = Depends(get_current_user),
):
result = await db.execute(select(Device).order_by(Device.name))
devices = result.scalars().all()

```
return [
    {
        "id":         d.id,
        "name":       d.name,
        "hostname":   d.hostname,
        "ip_address": d.ip_address,
        "os_info":    d.os_info,
        "status":     d.status.value,
        "active_app": d.active_app,
        "last_seen":  d.last_seen.isoformat() if d.last_seen else None,
    }
    for d in devices
]
```

# =========================

# GET SINGLE DEVICE

# =========================

@router.get("/{device_id}")
async def get_device(
device_id: str,
db: AsyncSession = Depends(get_db),
_:  User         = Depends(get_current_user),
):
d = await db.get(Device, device_id)
if not d:
raise HTTPException(status_code=404, detail="Device not found")

```
return {
    "id":         d.id,
    "name":       d.name,
    "hostname":   d.hostname,
    "ip_address": d.ip_address,
    "os_info":    d.os_info,
    "status":     d.status.value,
    "active_app": d.active_app,
    "last_seen":  d.last_seen.isoformat() if d.last_seen else None,
    "created_at": d.created_at.isoformat(),
}
```

# =========================

# HEARTBEAT (FIXED)

# =========================

@router.patch("/{device_id}/heartbeat")
async def heartbeat(
device_id:       str,
body:            HeartbeatBody,
db:              AsyncSession = Depends(get_db),
token_device_id: str          = Depends(get_device_id_from_token),
):
# Security check
if token_device_id != device_id:
raise HTTPException(status_code=403, detail="Token device_id mismatch")

```
d = await db.get(Device, device_id)

# Auto create device
if not d:
    d = Device(id=device_id, name=device_id)
    db.add(d)

# Update last seen
d.last_seen = datetime.now(timezone.utc)

# ✅ FIXED LOGIC
# If active app exists → device is active (online)
# Otherwise → idle
if body.active_app:
    d.status = DeviceStatus.online
else:
    d.status = DeviceStatus.idle

# Optional fields
if body.hostname:
    d.hostname = body.hostname

if body.ip_address:
    d.ip_address = body.ip_address

if body.os_info:
    d.os_info = body.os_info

if body.active_app:
    d.active_app = body.active_app

await db.commit()

return {"ok": True}
```

# =========================

# DELETE DEVICE (FIXED)

# =========================

@router.delete("/{device_id}", dependencies=[Depends(require_role(UserRole.admin))])
async def delete_device(
device_id: str,
db: AsyncSession = Depends(get_db),
):
d = await db.get(Device, device_id)
if not d:
raise HTTPException(status_code=404, detail="Device not found")

```
await db.delete(d)
await db.commit()

return {"ok": True}
```

# =========================

# BULK STATUS

# =========================

class BulkStatusItem(BaseModel):
device_id: str
status:    DeviceStatus

@router.post("/bulk-status", dependencies=[Depends(require_role(UserRole.monitor))])
async def bulk_status(
items: list[BulkStatusItem],
db:    AsyncSession = Depends(get_db),
):
if len(items) > 200:
raise HTTPException(status_code=400, detail="Max 200 items per request")

```
ids = [i.device_id for i in items]
result = await db.execute(select(Device).where(Device.id.in_(ids)))
device_map = {d.id: d for d in result.scalars().all()}

updated = []

for item in items:
    d = device_map.get(item.device_id)
    if d:
        d.status    = item.status
        d.last_seen = datetime.now(timezone.utc)
        updated.append(item.device_id)

await db.commit()

return {
    "updated": updated,
    "not_found": [
        i.device_id for i in items if i.device_id not in device_map
    ],
}
```
