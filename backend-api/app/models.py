# ============================================================================
# models.py — SQLAlchemy ORM models
# ============================================================================
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin   = "admin"
    monitor = "monitor"
    viewer  = "viewer"


class DeviceStatus(str, enum.Enum):
    online    = "online"
    offline   = "offline"
    idle      = "idle"
    streaming = "streaming"


class AppCategory(str, enum.Enum):
    work     = "work"
    non_work = "non-work"
    unknown  = "unknown"


class AlertSeverity(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:           Mapped[str]           = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    username:     Mapped[str]           = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str]          = mapped_column(String(256), nullable=False)
    role:         Mapped[UserRole]      = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.viewer)
    is_active:    Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime, default=utc_now)

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id:           Mapped[str]           = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name:         Mapped[str]           = mapped_column(String(128), nullable=False)
    hostname:     Mapped[Optional[str]] = mapped_column(String(128))
    ip_address:   Mapped[Optional[str]] = mapped_column(String(45))
    os_info:      Mapped[Optional[str]] = mapped_column(String(256))
    status:       Mapped[DeviceStatus]  = mapped_column(SAEnum(DeviceStatus), default=DeviceStatus.offline)
    active_app:   Mapped[Optional[str]] = mapped_column(String(128))
    last_seen:    Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at:   Mapped[datetime]      = mapped_column(DateTime, default=utc_now)

    logs:   Mapped[list["ActivityLog"]] = relationship(back_populates="device")
    alerts: Mapped[list["Alert"]]       = relationship(back_populates="device")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id:             Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id:      Mapped[str]              = mapped_column(Uuid(as_uuid=False), ForeignKey("devices.id"), nullable=False)
    active_app:     Mapped[Optional[str]]    = mapped_column(String(128))
    window_title:   Mapped[Optional[str]]    = mapped_column(Text)
    app_category:   Mapped[AppCategory]      = mapped_column(SAEnum(AppCategory), default=AppCategory.unknown)
    idle_seconds:   Mapped[int]              = mapped_column(Integer, default=0)
    is_idle:        Mapped[bool]             = mapped_column(Boolean, default=False)
    created_at:     Mapped[datetime]         = mapped_column(DateTime, default=utc_now)

    device: Mapped["Device"] = relationship(back_populates="logs")


class Alert(Base):
    __tablename__ = "alerts"

    id:          Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id:   Mapped[Optional[str]]     = mapped_column(Uuid(as_uuid=False), ForeignKey("devices.id"))
    severity:    Mapped[AlertSeverity]     = mapped_column(SAEnum(AlertSeverity), nullable=False)
    message:     Mapped[str]               = mapped_column(Text, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at:  Mapped[datetime]           = mapped_column(DateTime, default=utc_now)

    device: Mapped[Optional["Device"]] = relationship(back_populates="alerts")


class Webhook(Base):
    """Outbound webhook subscription — fired when an alert is created."""
    __tablename__ = "webhooks"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    url:        Mapped[str]           = mapped_column(String(512), nullable=False)
    secret:     Mapped[Optional[str]] = mapped_column(String(128))  # HMAC-SHA256 signing key
    # Comma-separated severities to filter on, e.g. "high,critical". Empty = all.
    severity_filter: Mapped[str]      = mapped_column(String(64), default="")
    is_active:  Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=utc_now)
    created_by: Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id:         Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:    Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    action:     Mapped[str]          = mapped_column(String(128), nullable=False)
    detail:     Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime]     = mapped_column(DateTime, default=utc_now)

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
