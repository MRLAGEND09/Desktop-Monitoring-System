# ============================================================================
# tests/conftest.py — pytest fixtures for RDM backend API tests
#
# Uses an in-process SQLite (async) database — no PostgreSQL needed for tests.
# Each test gets a fresh DB via function-scoped transaction rollback.
# ============================================================================
import asyncio
from pathlib import Path
import sys
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Ensure the backend package is importable regardless of how pytest is invoked.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import Base, get_db
from app.main import app as fastapi_app
from app.models import User, UserRole, Device, DeviceStatus

# Must match the scheme used in app/routes/auth.py
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Use in-memory SQLite for speed ───────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_schema():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test DB session that rolls back after each test.
    Uses a savepoint so nested commits work inside the session.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()  # savepoint
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with the test DB injected."""
    fastapi_app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Seed helpers ──────────────────────────────────────────────────────────────

async def _make_user(db: AsyncSession, *, username: str,
                     password: str = "TestPass1!", role: UserRole = UserRole.viewer) -> User:
    user = User(
        id            = str(uuid.uuid4()),
        username      = username,
        password_hash = pwd_ctx.hash(password),
        role          = role,
        is_active     = True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_device(db: AsyncSession, *, name: str = "test-pc",
                       status: DeviceStatus = DeviceStatus.online) -> Device:
    device = Device(
        id       = str(uuid.uuid4()),
        name     = name,
        status   = status,
    )
    db.add(device)
    await db.flush()
    return device


async def _login(client: AsyncClient, username: str, password: str = "TestPass1!") -> str:
    """Return a bearer token."""
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest_asyncio.fixture()
async def admin_user(db: AsyncSession) -> User:
    return await _make_user(db, username="test_admin", password="AdminPass1!", role=UserRole.admin)


@pytest_asyncio.fixture()
async def monitor_user(db: AsyncSession) -> User:
    return await _make_user(db, username="test_monitor", password="MonitorPass1!", role=UserRole.monitor)


@pytest_asyncio.fixture()
async def viewer_user(db: AsyncSession) -> User:
    return await _make_user(db, username="test_viewer", password="ViewerPass1!", role=UserRole.viewer)


@pytest_asyncio.fixture()
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    return await _login(client, "test_admin", "AdminPass1!")


@pytest_asyncio.fixture()
async def monitor_token(client: AsyncClient, monitor_user: User) -> str:
    return await _login(client, "test_monitor", "MonitorPass1!")


@pytest_asyncio.fixture()
async def viewer_token(client: AsyncClient, viewer_user: User) -> str:
    return await _login(client, "test_viewer", "ViewerPass1!")


@pytest_asyncio.fixture()
async def device(db: AsyncSession) -> Device:
    return await _make_device(db)
