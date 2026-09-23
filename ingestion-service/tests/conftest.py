"""Test fixtures for ingestion-service.

``main`` imports ``db`` and ``poller``, and all three raise at module level when
DB_URL / REDIS_URL / FRONTEND_URL are missing -- so the environment is seeded at
the top of conftest, before pytest collects anything.

The app's lifespan connects to Postgres and Redis and starts the polling loop,
so tests drive it through ``httpx.ASGITransport``, which skips lifespan, and
install a fake pool in its place.
"""

import os

os.environ.setdefault("DB_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import db as db_module  # noqa: E402
import main  # noqa: E402


class FakeConnection:
    def __init__(self, error=None):
        self._error = error
        self.queries: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return "INSERT 0 1"

    async def fetch(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return []


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


@pytest.fixture
def db(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(db_module, "db_pool", FakePool(conn))
    return conn


@pytest.fixture
def failing_db(monkeypatch):
    conn = FakeConnection(error=ConnectionError("connection refused"))
    monkeypatch.setattr(db_module, "db_pool", FakePool(conn))
    return conn


@pytest.fixture
def no_db(monkeypatch):
    monkeypatch.setattr(db_module, "db_pool", None)


@pytest.fixture
async def client():
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
