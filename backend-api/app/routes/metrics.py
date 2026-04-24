# ============================================================================
# routes/metrics.py — Prometheus-compatible /metrics endpoint
#
# Exposes four metric families:
#   rdm_http_requests_total{method,path,status}   counter
#   rdm_http_duration_seconds{method,path}         histogram (10 buckets)
#   rdm_active_devices_total                        gauge (polled from DB)
#   rdm_active_alerts_total                         gauge (polled from DB)
#
# Access is restricted to requests from localhost / internal Docker network,
# OR via an optional METRICS_TOKEN bearer token for external scrapers.
#
# Prometheus scrape config example:
#   - job_name: rdm-backend
#     bearer_token: <METRICS_TOKEN>
#     static_configs:
#       - targets: ['backend-api:8000']
#     metrics_path: /metrics
# ============================================================================
import os
import time
from typing import Callable

from fastapi import APIRouter, Request, Response, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import AsyncSessionLocal
from ..models import Device, Alert, DeviceStatus

router = APIRouter(tags=["metrics"])

METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")

# ── In-process metric stores ─────────────────────────────────────────────────

# counters[method][path][status] = count
_counters: dict = {}

# histograms[method][path] = list[float]  (duration seconds)
_histograms: dict = {}

BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]


def record_request(method: str, path: str, status: int, duration: float) -> None:
    """Called by RequestLoggingMiddleware after each response."""
    _counters.setdefault(method, {}).setdefault(path, {})
    _counters[method][path][status] = _counters[method][path].get(status, 0) + 1
    _histograms.setdefault(method, {}).setdefault(path, []).append(duration)


def _render_counters() -> list[str]:
    lines = [
        "# HELP rdm_http_requests_total Total HTTP requests",
        "# TYPE rdm_http_requests_total counter",
    ]
    for method, paths in _counters.items():
        for path, statuses in paths.items():
            for status, count in statuses.items():
                lines.append(
                    f'rdm_http_requests_total{{method="{method}",'
                    f'path="{path}",status="{status}"}} {count}'
                )
    return lines


def _render_histograms() -> list[str]:
    lines = [
        "# HELP rdm_http_duration_seconds HTTP request duration",
        "# TYPE rdm_http_duration_seconds histogram",
    ]
    for method, paths in _histograms.items():
        for path, durations in paths.items():
            label = f'method="{method}",path="{path}"'
            total = sum(durations)
            count = len(durations)
            for b in BUCKETS:
                le_count = sum(1 for d in durations if d <= b)
                lines.append(f'rdm_http_duration_seconds_bucket{{{label},le="{b}"}} {le_count}')
            lines.append(f'rdm_http_duration_seconds_bucket{{{label},le="+Inf"}} {count}')
            lines.append(f'rdm_http_duration_seconds_sum{{{label}}} {total:.6f}')
            lines.append(f'rdm_http_duration_seconds_count{{{label}}} {count}')
    return lines


async def _render_gauges() -> list[str]:
    async with AsyncSessionLocal() as db:
        online_count = await db.scalar(
            select(func.count()).select_from(Device).where(
                Device.status.in_([DeviceStatus.online, DeviceStatus.streaming])
            )
        )
        alert_count = await db.scalar(
            select(func.count()).select_from(Alert).where(Alert.resolved_at == None)
        )
    return [
        "# HELP rdm_active_devices_total Devices currently online or streaming",
        "# TYPE rdm_active_devices_total gauge",
        f"rdm_active_devices_total {online_count or 0}",
        "# HELP rdm_active_alerts_total Unresolved alerts",
        "# TYPE rdm_active_alerts_total gauge",
        f"rdm_active_alerts_total {alert_count or 0}",
    ]


def _check_auth(request: Request) -> None:
    """Allow loopback IPs or valid bearer token."""
    client_host = ""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        client_host = xff.split(",")[0].strip()
    elif request.client:
        client_host = request.client.host

    is_internal = client_host in ("127.0.0.1", "::1", "") or client_host.startswith(
        ("10.", "172.", "192.168.")
    )

    if is_internal:
        return  # no token required from internal network

    if not METRICS_TOKEN:
        raise HTTPException(status_code=403, detail="Metrics not available externally")

    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {METRICS_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid metrics token")


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    _check_auth(request)
    lines = (
        _render_counters()
        + _render_histograms()
        + await _render_gauges()
    )
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
