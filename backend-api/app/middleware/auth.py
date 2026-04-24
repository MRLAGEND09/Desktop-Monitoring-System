# ============================================================================
# middleware/auth.py — JWT dependency + RBAC for FastAPI routes
# ============================================================================
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..config import settings
from ..db import get_db
from ..models import User, UserRole

bearer_scheme = HTTPBearer()

ROLE_LEVELS = {
    UserRole.viewer:  1,
    UserRole.monitor: 2,
    UserRole.admin:   3,
}

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticates a human user JWT. Explicitly rejects device tokens."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # Device tokens must never authenticate as human users
        if payload.get("type") == "device":
            raise _CREDENTIALS_EXC
        user_id: str = payload.get("sub")
        if not user_id:
            raise _CREDENTIALS_EXC
    except JWTError:
        raise _CREDENTIALS_EXC

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise _CREDENTIALS_EXC
    return user


async def get_device_id_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Authenticates a device token. Returns the device_id claim.
    Used for device-facing endpoints (heartbeat, log ingest).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "device":
            raise _CREDENTIALS_EXC
        device_id: str = payload.get("device_id")
        if not device_id:
            raise _CREDENTIALS_EXC
    except JWTError:
        raise _CREDENTIALS_EXC
    return device_id


def require_role(minimum_role: UserRole):
    """Factory: returns a dependency that enforces a minimum role level."""
    async def dep(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVELS.get(current_user.role, 0) < ROLE_LEVELS[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {minimum_role.value}",
            )
        return current_user
    return dep
