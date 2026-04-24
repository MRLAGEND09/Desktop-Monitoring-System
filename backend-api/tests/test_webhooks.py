# ============================================================================
# tests/test_webhooks.py — Webhook endpoint tests
# ============================================================================
import pytest
from httpx import AsyncClient

from app.models import User


pytestmark = pytest.mark.asyncio


async def _create_webhook(client: AsyncClient, token: str, url: str = "https://hooks.example.com/rdm") -> dict:
    resp = await client.post(
        "/webhooks",
        json={"url": url, "severity_filter": "critical,high"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCreateWebhook:
    async def test_admin_can_create(self, client: AsyncClient, admin_token: str):
        data = await _create_webhook(client, admin_token)
        assert "id" in data
        # Secret shown once on creation
        assert "secret" in data
        assert len(data["secret"]) == 64  # 32-byte hex

    async def test_auto_generates_secret(self, client: AsyncClient, admin_token: str):
        data = await _create_webhook(client, admin_token, url="https://example.com/wh2")
        assert data["secret"] is not None

    async def test_custom_secret_accepted(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/webhooks",
            json={"url": "https://example.com/wh3", "secret": "mysecret123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        resp = await client.post(
            "/webhooks",
            json={"url": "https://example.com/wh4"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


class TestListWebhooks:
    async def test_admin_can_list(self, client: AsyncClient, admin_token: str):
        await _create_webhook(client, admin_token)
        resp = await client.get("/webhooks", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        # Secret must NOT be fully exposed in list
        for wh in resp.json():
            assert "secret_hint" in wh
            assert len(wh.get("secret_hint", "")) <= 10  # only a fingerprint

    async def test_viewer_cannot_list(self, client: AsyncClient, viewer_token: str):
        resp = await client.get("/webhooks", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 403


class TestPatchWebhook:
    async def test_can_disable(self, client: AsyncClient, admin_token: str):
        wh = await _create_webhook(client, admin_token, url="https://example.com/wh5")
        resp = await client.patch(
            f"/webhooks/{wh['id']}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_can_update_url(self, client: AsyncClient, admin_token: str):
        wh = await _create_webhook(client, admin_token, url="https://example.com/wh6")
        resp = await client.patch(
            f"/webhooks/{wh['id']}",
            json={"url": "https://new-endpoint.example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestDeleteWebhook:
    async def test_admin_can_delete(self, client: AsyncClient, admin_token: str):
        wh = await _create_webhook(client, admin_token, url="https://example.com/wh7")
        resp = await client.delete(
            f"/webhooks/{wh['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestMetricsEndpoint:
    async def test_metrics_accessible_internally(self, client: AsyncClient):
        """The test client is effectively internal (no X-Forwarded-For)."""
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "rdm_http_requests_total" in resp.text
        assert "rdm_active_devices_total" in resp.text
