# ============================================================================
# main.py — FastAPI application factory
# ============================================================================
import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .db import create_tables
from .routes import auth, devices, logs, alerts, webhooks, users, stream, metrics
from .middleware.logging import RequestLoggingMiddleware
from .routes.metrics import record_request

import time

# ── Structured JSON logging ──────────────────────────────────────────────────
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "fmt": '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "uvicorn.access": {"level": "WARNING"},  # suppress per-request access log (we do our own)
        "sqlalchemy.engine": {"level": "WARNING" if not settings.debug else "INFO"},
    },
}
logging.config.dictConfig(LOGGING_CONFIG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="RDM Backend API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost = first to run) ─────────────────────
app.add_middleware(RequestLoggingMiddleware)   # adds X-Request-ID, structured log

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# ── Record timing into Prometheus counters ────────────────────────────────────
@app.middleware("http")
async def _metrics_recorder(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    # Normalise dynamic path segments to avoid high cardinality
    path = request.url.path
    record_request(request.method, path, response.status_code, duration)
    return response

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(logs.router)
app.include_router(alerts.router)
app.include_router(webhooks.router)
app.include_router(users.router)
app.include_router(stream.router)
app.include_router(metrics.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
