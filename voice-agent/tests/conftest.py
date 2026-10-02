"""Test fixtures for voice-agent.

worker.py raises at import time when AGENT_LLM_API_KEY is missing, so it
is seeded here before pytest collects any test module -- the same pattern
the other services use.
"""

import os

os.environ.setdefault("AGENT_LLM_API_KEY", "test-agent-key")
os.environ.setdefault("GATEWAY_INTERNAL_URL", "http://gateway-test:8000")
os.environ.setdefault("INGESTION_INTERNAL_URL", "http://ingestion-test:8001")

import json  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

import worker  # noqa: E402


class FakeRoom:
    """Captures what the worker publishes to the browser over the data channel."""

    def __init__(self):
        self.published = []
        self.local_participant = self

    async def publish_data(self, payload, reliable=True):
        self.published.append(json.loads(payload.decode()))

    @property
    def published_stop(self):
        return any(p.get("type") == "stop" for p in self.published)

    @property
    def charts(self):
        return [p for p in self.published if p.get("type") == "chart"]


class FakeCtx:
    """Stands in for the LiveKit RunContext the tools receive."""

    def __init__(self, room=None):
        self.userdata = worker.WorkerCtx(room=room)


@pytest.fixture
def room():
    return FakeRoom()


@pytest.fixture
def ctx(room):
    return FakeCtx(room=room)


def gateway_returns(payload, status_code=200):
    """Patch the gateway GET so a tool sees `payload` come back."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return patch("httpx.AsyncClient.get", AsyncMock(return_value=response))


def gateway_fails(error):
    """Patch the gateway GET so the call raises, as an outage would."""
    return patch("httpx.AsyncClient.get", AsyncMock(side_effect=error))
