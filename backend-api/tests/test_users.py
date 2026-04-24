# ============================================================================
# tests/test_users.py — User management endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole


pytestmark = pytest.mark.asyncio


class TestGetMe:
    async def test_returns_own_profile(self, client: AsyncClient, viewer_token: str, viewer_user: User):
        resp = await client.get("/users/me", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test_viewer"
        assert data["role"] == "viewer"
        assert "password_hash" not in data

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/users/me")
        assert resp.status_code == 403


class TestListUsers:
    async def test_admin_can_list(self, client: AsyncClient, admin_token: str, admin_user: User):
        resp = await client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_viewer_cannot_list(self, client: AsyncClient, viewer_token: str):
        resp = await client.get("/users", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 403

    async def test_monitor_cannot_list(self, client: AsyncClient, monitor_token: str):
        resp = await client.get("/users", headers={"Authorization": f"Bearer {monitor_token}"})
        assert resp.status_code == 403


class TestCreateUser:
    async def test_admin_can_create(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/users",
            json={"username": "newuser", "password": "NewPass123!", "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert "password_hash" not in data

    async def test_duplicate_username_rejected(
        self, client: AsyncClient, admin_token: str, admin_user: User
    ):
        resp = await client.post(
            "/users",
            json={"username": "test_admin", "password": "SomePass123!", "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 409

    async def test_weak_password_rejected(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/users",
            json={"username": "weakpwuser", "password": "password", "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    async def test_password_missing_special_char(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/users",
            json={"username": "nospecial", "password": "Password123", "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    async def test_username_too_short(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/users",
            json={"username": "ab", "password": "ValidPass1!", "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    async def test_valid_roles(self, client: AsyncClient, admin_token: str):
        for i, role in enumerate(["viewer", "monitor", "admin"]):
            resp = await client.post(
                "/users",
                json={"username": f"role_user_{i}", "password": "ValidPass1!", "role": role},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 201


class TestPatchUser:
    async def test_admin_can_change_role(
        self, client: AsyncClient, admin_token: str, viewer_user: User
    ):
        resp = await client.patch(
            f"/users/{viewer_user.id}",
            json={"role": "monitor"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "monitor"

    async def test_admin_can_deactivate(
        self, client: AsyncClient, admin_token: str, viewer_user: User
    ):
        resp = await client.patch(
            f"/users/{viewer_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_cannot_deactivate_self(
        self, client: AsyncClient, admin_token: str, admin_user: User
    ):
        resp = await client.patch(
            f"/users/{admin_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    async def test_viewer_cannot_patch(
        self, client: AsyncClient, viewer_token: str, admin_user: User
    ):
        resp = await client.patch(
            f"/users/{admin_user.id}",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


class TestDeleteUser:
    async def test_admin_can_soft_delete(
        self, client: AsyncClient, admin_token: str, monitor_user: User
    ):
        resp = await client.delete(
            f"/users/{monitor_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        # Should not be able to log in anymore
        login = await client.post("/auth/login", json={
            "username": "test_monitor", "password": "MonitorPass1!"
        })
        assert login.status_code == 401

    async def test_cannot_delete_self(
        self, client: AsyncClient, admin_token: str, admin_user: User
    ):
        resp = await client.delete(
            f"/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
