# ============================================================================
# routes/users.py — User management (admin only)
#
# GET    /users           — list all users
# POST   /users           — create user
# GET    /users/me        — current user profile
# PATCH  /users/{id}      — update role / active flag / password
# DELETE /users/{id}      — deactivate (soft delete — preserves audit trail)
# ============================================================================
from datetime import datetime
from typing import Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, constr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models import AuditLog, User, UserRole
from ..middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/users", tags=["users"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_admin = Depends(require_role(UserRole.admin))

_PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]).{10,128}$"
)


def _validate_password_complexity(v: str | None) -> str | None:
    if v is None:
        return v
    if not _PASSWORD_RE.match(v):
        raise ValueError(
            "Password must be 10-128 characters and contain at least one "
            "uppercase letter, one lowercase letter, one digit, and one "
            "special character (!@#$%^&*…)."
        )
    return v


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=64)
    password: constr(min_length=10, max_length=128)
    role:     UserRole = UserRole.viewer

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        return _validate_password_complexity(v)


class UserPatch(BaseModel):
    role:      Optional[UserRole] = None
    is_active: Optional[bool]     = None
    password:  Optional[constr(min_length=10, max_length=128)] = None

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        return _validate_password_complexity(v)


def _serialize(u: User) -> dict:
    return {
        "id":         u.id,
        "username":   u.username,
        "role":       u.role.value,
        "is_active":  u.is_active,
        "created_at": u.created_at.isoformat(),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return _serialize(current_user)


@router.get("", dependencies=[_admin])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at))
    return [_serialize(u) for u in result.scalars().all()]


@router.post("", status_code=201, dependencies=[_admin])
async def create_user(
    body:         UserCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username      = body.username,
        password_hash = pwd_ctx.hash(body.password),
        role          = body.role,
    )
    db.add(user)
    db.add(AuditLog(user_id=current_user.id,
                    action=f"create_user:{body.username}:{body.role.value}"))
    await db.flush()
    return _serialize(user)


@router.patch("/{user_id}", dependencies=[_admin])
async def update_user(
    user_id:      str,
    body:         UserPatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admins from demoting themselves
    if user.id == current_user.id and body.role and body.role != UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if user.id == current_user.id and body.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = pwd_ctx.hash(body.password)

    db.add(AuditLog(user_id=current_user.id,
                    action=f"update_user:{user_id}"))
    return _serialize(user)


@router.delete("/{user_id}", status_code=200, dependencies=[_admin])
async def deactivate_user(
    user_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.add(AuditLog(user_id=current_user.id,
                    action=f"deactivate_user:{user_id}"))
    return {"ok": True}
