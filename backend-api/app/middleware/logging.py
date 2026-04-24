# ============================================================================
# middleware/logging.py — Structured JSON request logging with request IDs
#
# Every request gets a unique X-Request-ID header (generated if not supplied).
# Emits a single JSON log line per request containing:
#   method, path, status_code, duration_ms, request_id, client_ip
# ============================================================================
import time
import uuid
import logging
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("rdm.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _log(request, 500, duration_ms, request_id, error=str(exc))
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        _log(request, response.status_code, duration_ms, request_id)
        return response


def _log(request: Request, status: int, duration_ms: float,
         request_id: str, error: str | None = None) -> None:
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    record = {
        "request_id":  request_id,
        "method":      request.method,
        "path":        request.url.path,
        "status":      status,
        "duration_ms": duration_ms,
        "client_ip":   client_ip,
    }
    if error:
        record["error"] = error

    level = logging.WARNING if status >= 500 else (
            logging.INFO    if status < 400 else logging.WARNING)
    logger.log(level, json.dumps(record))
