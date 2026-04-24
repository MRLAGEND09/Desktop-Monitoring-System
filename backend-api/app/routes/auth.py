# ============================================================================
# routes/auth.py — POST /login  +  POST /auth/device-token
# ============================================================================
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, constr
from ..config import settings
from ..db import get_db
from ..models import AuditLog, User, UserRole
from ..middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    # Enforce bounds to prevent oversized inputs reaching bcrypt
    username: constr(min_length=1, max_length=64)
    password: constr(min_length=1, max_length=128)

class LoginResponse(BaseModel):
    token: str
    user:  dict

class DeviceTokenRequest(BaseModel):
    device_id: constr(min_length=1, max_length=64)
    label:     constr(max_length=128) = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_token(data: dict, expire_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == body.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing attacks
    valid = user and pwd_ctx.verify(body.password, user.password_hash)
    if not valid:
        # Audit failed attempt — store None for user_id when user not found
        db.add(AuditLog(
            user_id=user.id if user else None,
            action="login_failed",
            detail=f"username={body.username[:64]}",
        ))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid credentials")

    token = create_token(
        {"sub": user.id, "role": user.role.value, "username": user.username},
        settings.jwt_expire_minutes,
    )
    db.add(AuditLog(user_id=user.id, action="login"))
    return LoginResponse(
        token=token,
        user={"id": user.id, "username": user.username, "role": user.role.value},
    )


@router.post("/device-token", dependencies=[Depends(require_role(UserRole.admin))])
async def issue_device_token(
    body: DeviceTokenRequest,
    db:   AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = create_token(
        {"sub": body.device_id, "type": "device", "device_id": body.device_id},
        expire_minutes=525_600,  # 1 year
    )
    db.add(AuditLog(
        user_id=current_user.id,
        action="issue_device_token",
        detail=f"device={body.device_id} label={body.label}",
    ))
    return {"token": token, "device_id": body.device_id}
