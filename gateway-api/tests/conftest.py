"""Test fixtures for gateway-api.

Two things have to happen before ``main`` can be imported at all:

1. DB_URL, ADMIN_USERNAME, ADMIN_PASSWORD and FRONTEND_URL are read at module
   level and raise ValueError when missing, so they are set here at the top of
   conftest -- before pytest collects any test module.
2. The app's lifespan opens a real asyncpg pool. Tests therefore drive the app
   through ``httpx.ASGITransport``, which does *not* run lifespan, and install a
   fake pool instead.
"""

import os

os.environ.setdefault("DB_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("ADMIN_API_KEY", "test-api-key")
os.environ.setdefault("AGENT_LLM_API_KEY", "test-agent-key")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import main  # noqa: E402

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
ADMIN_API_KEY = os.environ["ADMIN_API_KEY"]

class FakeConnection:
    """Records the SQL it was handed and replays canned results."""

    def __init__(self, fetch_result=None, execute_result="UPDATE 1", error=None):
        self._fetch_result = fetch_result if fetch_result is not None else []
        self._execute_result = execute_result
        self._error = error
        self.queries: list[tuple[str, tuple]] = []

    async def fetch(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return self._fetch_result

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return self._fetch_result[0] if self._fetch_result else None

    async def fetchval(self, query, *args):
        row = await self.fetchrow(query, *args)
        return next(iter(row.values())) if row else None

    async def execute(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return self._execute_result


class FakePool:
    def __init__(self, connection: FakeConnection):
        self.connection = connection

    def acquire(self):
        pool = self

        class _Acquire:
            async def __aenter__(self):
                return pool.connection

            async def __aexit__(self, *exc_info):
                return False

        return _Acquire()

    async def close(self):
        return None


@pytest.fixture
def fake_conn():
    return FakeConnection()


@pytest.fixture
def db(monkeypatch, fake_conn):
    """Installs a fake pool and hands the connection back for assertions."""
    monkeypatch.setattr(main, "db_pool", FakePool(fake_conn))
    return fake_conn


@pytest.fixture
def no_db(monkeypatch):
    """Simulates the window before (or after) the pool is available."""
    monkeypatch.setattr(main, "db_pool", None)


@pytest.fixture(autouse=True)
def clear_sessions():
    main.active_sessions.clear()
    yield
    main.active_sessions.clear()


@pytest.fixture
async def client():
    # https, not http: the admin session cookie is set with secure=True, and a
    # client on a plain-http base URL would silently never send it back.
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


@pytest.fixture
def admin_headers():
    return {"X-API-Key": ADMIN_API_KEY}
