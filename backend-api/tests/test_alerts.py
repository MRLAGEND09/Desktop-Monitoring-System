# ============================================================================
# tests/test_alerts.py — Alert endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertSeverity, Device, User


pytestmark = pytest.mark.asyncio


async def _create_alert(client: AsyncClient, token: str, *,
                        severity: str = "low", message: str = "test alert",
                        device_id: str | None = None) -> dict:
    body = {"severity": severity, "message": message}
    if device_id:
        body["device_id"] = device_id
    resp = await client.post(
        "/alerts", json=body,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestListAlerts:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/alerts")
        assert resp.status_code == 403

    async def test_viewer_can_list(
        self, client: AsyncClient, viewer_token: str, admin_token: str
    ):
        await _create_alert(client, admin_token)
        resp = await client.get("/alerts", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestCreateAlert:
    async def test_monitor_can_create(self, client: AsyncClient, monitor_token: str):
        data = await _create_alert(client, monitor_token, severity="high", message="CPU spike")
        assert "id" in data

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        resp = await client.post(
            "/alerts",
            json={"severity": "low", "message": "test"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403

    async def test_invalid_severity_rejected(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/alerts",
            json={"severity": "extreme", "message": "test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    async def test_alert_with_device_id(
        self, client: AsyncClient, admin_token: str, device: Device
    ):
        data = await _create_alert(
            client, admin_token, severity="critical",
            message="device down", device_id=device.id
        )
        assert "id" in data

    async def test_all_severity_levels(self, client: AsyncClient, admin_token: str):
        for sev in ["low", "medium", "high", "critical"]:
            data = await _create_alert(client, admin_token, severity=sev)
            assert "id" in data


class TestResolveAlert:
    async def test_resolve(
        self, client: AsyncClient, admin_token: str, monitor_token: str
    ):
        data = await _create_alert(client, admin_token)
        alert_id = data["id"]

        resp = await client.patch(
            f"/alerts/{alert_id}/resolve",
            headers={"Authorization": f"Bearer {monitor_token}"}
        )
        assert resp.status_code == 200

    async def test_resolve_already_resolved(
        self, client: AsyncClient, admin_token: str
    ):
        data = await _create_alert(client, admin_token)
        alert_id = data["id"]

        await client.patch(
            f"/alerts/{alert_id}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Second resolve should be 409 or 400
        resp = await client.patch(
            f"/alerts/{alert_id}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code in (400, 409)

    async def test_viewer_cannot_resolve(
        self, client: AsyncClient, admin_token: str, viewer_token: str
    ):
        data = await _create_alert(client, admin_token)
        resp = await client.patch(
            f"/alerts/{data['id']}/resolve",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        assert resp.status_code == 403

    async def test_resolve_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.patch(
            "/alerts/99999999/resolve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 404
