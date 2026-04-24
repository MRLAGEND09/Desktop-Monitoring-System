# ============================================================================
# tests/test_auth.py — Authentication endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


pytestmark = pytest.mark.asyncio


class TestLogin:
    async def test_login_success(self, client: AsyncClient, admin_user: User):
        resp = await client.post("/auth/login", json={
            "username": "test_admin", "password": "AdminPass1!"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["username"] == "test_admin"
        assert data["user"]["role"] == "admin"

    async def test_login_wrong_password(self, client: AsyncClient, admin_user: User):
        resp = await client.post("/auth/login", json={
            "username": "test_admin", "password": "WrongPass!"
        })
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    async def test_login_unknown_user(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={
            "username": "no_such_user", "password": "SomePass1!"
        })
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db: AsyncSession):
        """Deactivated user cannot log in."""
        from tests.conftest import _make_user
        from app.models import UserRole
        user = await _make_user(db, username="inactive_user", role=UserRole.viewer)
        user.is_active = False
        await db.flush()

        resp = await client.post("/auth/login", json={
            "username": "inactive_user", "password": "TestPass1!"
        })
        assert resp.status_code == 401

    async def test_login_username_too_long(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={
            "username": "a" * 65, "password": "SomePass1!"
        })
        assert resp.status_code == 422  # Pydantic validation

    async def test_login_returns_audit_log(
        self, client: AsyncClient, admin_user: User, db: AsyncSession
    ):
        from sqlalchemy import select
        from app.models import AuditLog
        await client.post("/auth/login", json={
            "username": "test_admin", "password": "AdminPass1!"
        })
        result = await db.execute(
            select(AuditLog).where(AuditLog.user_id == admin_user.id)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.action == "login"

    async def test_failed_login_audit_log(
        self, client: AsyncClient, admin_user: User, db: AsyncSession
    ):
        from sqlalchemy import select
        from app.models import AuditLog
        await client.post("/auth/login", json={
            "username": "test_admin", "password": "WrongPass1!"
        })
        result = await db.execute(
            select(AuditLog).where(AuditLog.action == "login_failed")
        )
        log = result.scalar_one_or_none()
        assert log is not None


class TestDeviceToken:
    async def test_issue_device_token_admin_only(
        self, client: AsyncClient, admin_token: str, viewer_token: str
    ):
        body = {"device_id": "test-pc-01", "label": "Test PC"}

        # Admin can issue
        resp = await client.post(
            "/auth/device-token", json=body,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

        # Viewer cannot
        resp = await client.post(
            "/auth/device-token", json=body,
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 403

    async def test_device_token_rejected_as_user_auth(
        self, client: AsyncClient, admin_token: str
    ):
        """A device token must not work on user-only endpoints."""
        body = {"device_id": "test-pc-xx", "label": ""}
        token_resp = await client.post(
            "/auth/device-token", json=body,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        device_token = token_resp.json()["token"]

        # Try to call a user endpoint with the device token
        resp = await client.get(
            "/users/me", headers={"Authorization": f"Bearer {device_token}"}
        )
        assert resp.status_code == 401
