# ============================================================================
# tests/test_devices.py — Device endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceStatus, User


pytestmark = pytest.mark.asyncio


class TestListDevices:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/devices")
        assert resp.status_code == 403

    async def test_viewer_can_list(self, client: AsyncClient, viewer_token: str, device: Device):
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert device.id in ids

    async def test_response_shape(self, client: AsyncClient, admin_token: str, device: Device):
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {admin_token}"})
        d = next(x for x in resp.json() if x["id"] == device.id)
        assert "name" in d
        assert "status" in d
        assert "last_seen" in d


class TestGetDevice:
    async def test_get_existing(self, client: AsyncClient, viewer_token: str, device: Device):
        resp = await client.get(
            f"/devices/{device.id}", headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == device.id

    async def test_get_not_found(self, client: AsyncClient, viewer_token: str):
        resp = await client.get(
            "/devices/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 404


class TestHeartbeat:
    async def test_heartbeat_requires_device_token(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        """User tokens must NOT be accepted on the heartbeat endpoint."""
        resp = await client.patch(
            f"/devices/{device.id}/heartbeat",
            json={"status": "online"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 401

    async def test_heartbeat_device_id_mismatch(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        """Device token for device-A cannot heartbeat on behalf of device-B."""
        token_resp = await client.post(
            "/auth/device-token",
            json={"device_id": device.id, "label": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        device_token = token_resp.json()["token"]

        resp = await client.patch(
            "/devices/different-device-id/heartbeat",
            json={"status": "online"},
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert resp.status_code == 403

    async def test_heartbeat_updates_status(
        self, client: AsyncClient, admin_token: str, device: Device, db: AsyncSession
    ):
        token_resp = await client.post(
            "/auth/device-token",
            json={"device_id": device.id, "label": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        device_token = token_resp.json()["token"]

        resp = await client.patch(
            f"/devices/{device.id}/heartbeat",
            json={"status": "idle", "active_app": "Slack"},
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert resp.status_code == 200

        await db.refresh(device)
        assert device.status == DeviceStatus.idle
        assert device.active_app == "Slack"
        assert device.last_seen is not None

    async def test_heartbeat_defaults_to_idle_when_status_missing(
        self, client: AsyncClient, admin_token: str, device: Device, db: AsyncSession
    ):
        token_resp = await client.post(
            "/auth/device-token",
            json={"device_id": device.id, "label": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        device_token = token_resp.json()["token"]

        resp = await client.patch(
            f"/devices/{device.id}/heartbeat",
            json={"active_app": "Slack"},
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert resp.status_code == 200

        await db.refresh(device)
        assert device.status == DeviceStatus.idle
        assert device.active_app == "Slack"

    async def test_heartbeat_long_hostname_truncated(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        token_resp = await client.post(
            "/auth/device-token",
            json={"device_id": device.id, "label": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        device_token = token_resp.json()["token"]

        resp = await client.patch(
            f"/devices/{device.id}/heartbeat",
            json={"hostname": "h" * 200, "status": "online"},
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert resp.status_code == 200


class TestDeleteDevice:
    async def test_admin_can_delete(
        self, client: AsyncClient, admin_token: str, db: AsyncSession
    ):
        from tests.conftest import _make_device
        d = await _make_device(db, name="to-delete")

        resp = await client.delete(
            f"/devices/{d.id}", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200

    async def test_viewer_cannot_delete(
        self, client: AsyncClient, viewer_token: str, device: Device
    ):
        resp = await client.delete(
            f"/devices/{device.id}",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 403


class TestBulkStatus:
    async def test_monitor_can_bulk_update(
        self, client: AsyncClient, monitor_token: str, device: Device, db: AsyncSession
    ):
        resp = await client.post(
            "/devices/bulk-status",
            json=[{"device_id": device.id, "status": "offline"}],
            headers={"Authorization": f"Bearer {monitor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert device.id in data["updated"]

    async def test_viewer_cannot_bulk_update(
        self, client: AsyncClient, viewer_token: str, device: Device
    ):
        resp = await client.post(
            "/devices/bulk-status",
            json=[{"device_id": device.id, "status": "offline"}],
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403

    async def test_bulk_limit_enforced(
        self, client: AsyncClient, monitor_token: str
    ):
        items = [{"device_id": f"fake-{i}", "status": "offline"} for i in range(201)]
        resp = await client.post(
            "/devices/bulk-status",
            json=items,
            headers={"Authorization": f"Bearer {monitor_token}"},
        )
        assert resp.status_code == 400
