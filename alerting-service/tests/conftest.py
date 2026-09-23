"""Test fixtures for alerting-service.

config.py calls ``sys.exit(1)`` at import time when its required settings are
missing -- that would abort the whole pytest run, not just fail a test. The
values below are dummies seeded before collection; no real Telegram token is
ever used and nothing here talks to Telegram.
"""

import os
from datetime import datetime, timezone

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0000000000:TEST-TOKEN-NOT-REAL")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-1000000000000")
os.environ.setdefault("DB_URL", "postgresql://test:test@localhost:5432/test")

import pytest  # noqa: E402

RECORDED_AT = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)


class FakeConnection:
    def __init__(self, rows=None, error=None):
        self._rows = rows if rows is not None else []
        self._error = error
        self.queries: list[tuple[str, tuple]] = []

    async def fetch(self, query, *args):
        self.queries.append((query, args))
        if self._error:
            raise self._error
        return self._rows

    async def fetchrow(self, query, *args):
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None


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
def make_pool():
    def _make(rows=None, error=None):
        return FakePool(FakeConnection(rows=rows, error=error))

    return _make


@pytest.fixture
def full_report():
    """A DailyReport with every optional section populated."""
    return {
        "report_date": "2026-01-01",
        "window_label": "Last 1 days",
        "highest_ping": {
            "server_name": "CS2 DM #1",
            "server_id": "185.25.180.1:27015",
            "region": "Vienna",
            "max_ping_ms": 245.0,
            "recorded_at": RECORDED_AT,
        },
        "avg_pings": [
            {
                "server_name": "CS2 DM #1",
                "server_id": "185.25.180.1:27015",
                "region": "Vienna",
                "avg_ping_ms": 180.0,
            },
            {
                "server_name": "CS2 5v5 #2",
                "server_id": "91.211.118.96:27015",
                "region": "Warsaw",
                "avg_ping_ms": 95.0,
            },
            {
                "server_name": "CS2 Retake #3",
                "server_id": "91.211.118.96:27018",
                "region": "Warsaw",
                "avg_ping_ms": 22.0,
            },
        ],
        "top_crashers": [
            {
                "server_name": "CS2 DM #1",
                "server_id": "185.25.180.1:27015",
                "region": "Vienna",
                "crash_count": 4,
            },
            {
                "server_name": "CS2 5v5 #2",
                "server_id": "91.211.118.96:27015",
                "region": "Warsaw",
                "crash_count": 1,
            },
        ],
        "event_summary": {
            "crash": 3,
            "offline": 2,
            "high_ping": 7,
            "recovery": 5,
            "total": 17,
        },
        "server_statuses": {"total": 10, "online": 8, "offline": 2},
    }


@pytest.fixture
def empty_report():
    """A DailyReport for a quiet window -- every section empty."""
    return {
        "report_date": "2026-01-01",
        "window_label": "Last 5 minutes",
        "highest_ping": None,
        "avg_pings": [],
        "top_crashers": [],
        "event_summary": {
            "crash": 0,
            "offline": 0,
            "high_ping": 0,
            "recovery": 0,
            "total": 0,
        },
        "server_statuses": {"total": 10, "online": 10, "offline": 0},
    }
