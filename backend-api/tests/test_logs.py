# ============================================================================
# tests/test_logs.py — Activity log endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, User


pytestmark = pytest.mark.asyncio


async def _device_token(client: AsyncClient, admin_token: str, device_id: str) -> str:
    resp = await client.post(
        "/auth/device-token",
        json={"device_id": device_id, "label": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    return resp.json()["token"]


class TestIngestLog:
    async def test_requires_device_token(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        """A human user JWT must not be accepted."""
        resp = await client.post(
            "/logs",
            json={"device_id": device.id, "active_app": "Chrome"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 401

    async def test_ingest_success(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        dtoken = await _device_token(client, admin_token, device.id)
        resp = await client.post(
            "/logs",
            json={
                "device_id":    device.id,
                "active_app":   "Google Chrome",
                "window_title": "Facebook Ads Manager",
                "app_category": "work",
                "idle_seconds": 0,
                "is_idle":      False,
            },
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        assert resp.status_code == 201

    async def test_device_id_mismatch_rejected(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        dtoken = await _device_token(client, admin_token, device.id)
        resp = await client.post(
            "/logs",
            json={"device_id": "different-device", "active_app": "Chrome"},
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        assert resp.status_code == 403

    async def test_window_title_truncated(
        self, client: AsyncClient, admin_token: str, device: Device, db: AsyncSession
    ):
        dtoken = await _device_token(client, admin_token, device.id)
        resp = await client.post(
            "/logs",
            json={
                "device_id":    device.id,
                "window_title": "W" * 600,
            },
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        assert resp.status_code == 201

    async def test_idle_seconds_clamped(
        self, client: AsyncClient, admin_token: str, device: Device, db: AsyncSession
    ):
        from sqlalchemy import select
        from app.models import ActivityLog
        dtoken = await _device_token(client, admin_token, device.id)
        resp = await client.post(
            "/logs",
            json={"device_id": device.id, "idle_seconds": 999999},
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        assert resp.status_code == 201
        result = await db.execute(
            select(ActivityLog).order_by(ActivityLog.id.desc()).limit(1)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.idle_seconds <= 86_400


class TestGetLogs:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/logs")
        assert resp.status_code == 403

    async def test_viewer_can_list(
        self, client: AsyncClient, viewer_token: str, admin_token: str, device: Device
    ):
        dtoken = await _device_token(client, admin_token, device.id)
        await client.post(
            "/logs",
            json={"device_id": device.id, "active_app": "Slack"},
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        resp = await client.get("/logs", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_filter_by_device(
        self, client: AsyncClient, viewer_token: str, admin_token: str, device: Device
    ):
        dtoken = await _device_token(client, admin_token, device.id)
        await client.post(
            "/logs",
            json={"device_id": device.id, "active_app": "Excel"},
            headers={"Authorization": f"Bearer {dtoken}"},
        )
        resp = await client.get(
            f"/logs?device_id={device.id}",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 200
        for entry in resp.json():
            assert entry["device_id"] == device.id

    async def test_pagination(self, client: AsyncClient, viewer_token: str):
        resp = await client.get(
            "/logs?page=1&page_size=5",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    async def test_page_size_limit(self, client: AsyncClient, viewer_token: str):
        resp = await client.get(
            "/logs?page_size=999",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 422
