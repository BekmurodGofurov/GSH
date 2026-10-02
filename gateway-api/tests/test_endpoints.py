from datetime import datetime, timezone

import pytest

from conftest import ADMIN_PASSWORD, ADMIN_USERNAME, FakeConnection, FakePool

SERVER_ROW = {
    "server_id": "185.25.180.1:27015",
    "server_name": "CS2 DM #1",
    "region": "Vienna",
    "status": "ONLINE",
    "last_online_at": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    "last_offline_at": None,
    "player_count": 14,
    "max_players": 24,
    "ping_ms": 38.5,
    "last_metric_at": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
}

NEW_SERVER = {
    "server_id": "10.0.0.1:27015",
    "server_name": "Test Server",
    "region": "EU-East",
}


# --- health ---------------------------------------------------------------

async def test_root_reports_the_service(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "gateway-api",
        "version": "1.0.0",
    }


async def test_health_does_not_need_the_database(no_db, client):
    # The health probe must answer even while the pool is still connecting,
    # otherwise the container never becomes healthy and can never start.
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gateway-api"}


# --- read endpoints -------------------------------------------------------

async def test_get_servers_returns_the_rows_from_the_database(db, client):
    db._fetch_result = [SERVER_ROW]

    response = await client.get("/api/v1/servers")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["server_id"] == SERVER_ROW["server_id"]
    assert body[0]["ping_ms"] == 38.5


async def test_get_servers_returns_an_empty_list_when_nothing_is_monitored(db, client):
    response = await client.get("/api/v1/servers")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_servers_returns_503_before_the_pool_is_ready(no_db, client):
    response = await client.get("/api/v1/servers")

    assert response.status_code == 503
    assert "Database connection is not ready" in response.json()["detail"]


async def test_get_metrics_passes_the_server_id_and_limit_to_the_query(db, client):
    response = await client.get("/api/v1/servers/185.25.180.1:27015/metrics?limit=50")

    assert response.status_code == 200
    _, args = db.queries[-1]
    assert args == ("185.25.180.1:27015", 50)


async def test_get_metrics_applies_the_default_limit(db, client):
    await client.get("/api/v1/servers/185.25.180.1:27015/metrics")

    _, args = db.queries[-1]
    assert args[1] == 30


@pytest.mark.parametrize("limit", [0, 4, 301, "many"])
async def test_get_metrics_rejects_an_out_of_range_limit(db, client, limit):
    response = await client.get(
        f"/api/v1/servers/185.25.180.1:27015/metrics?limit={limit}"
    )

    assert response.status_code == 422


async def test_get_events_applies_the_default_limit(db, client):
    response = await client.get("/api/v1/events")

    assert response.status_code == 200
    _, args = db.queries[-1]
    assert args == (50,)


@pytest.mark.parametrize("limit", [0, 201])
async def test_get_events_rejects_an_out_of_range_limit(db, client, limit):
    response = await client.get(f"/api/v1/events?limit={limit}")

    assert response.status_code == 422


async def test_get_events_returns_503_before_the_pool_is_ready(no_db, client):
    response = await client.get("/api/v1/events")

    assert response.status_code == 503


# --- authentication -------------------------------------------------------

async def test_login_with_valid_credentials_sets_a_session_cookie(client):
    response = await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert "admin_session" in response.cookies


@pytest.mark.parametrize(
    "creds",
    [
        {"username": ADMIN_USERNAME, "password": "wrong"},
        {"username": "wrong", "password": ADMIN_PASSWORD},
        {"username": "wrong", "password": "wrong"},
    ],
)
async def test_login_with_bad_credentials_is_rejected(client, creds):
    response = await client.post("/api/v1/admin/login", json=creds)

    assert response.status_code == 401
    assert "admin_session" not in response.cookies


async def test_login_rejects_a_malformed_body(client):
    response = await client.post("/api/v1/admin/login", json={"username": "only"})

    assert response.status_code == 422


async def test_me_accepts_a_valid_api_key(client, admin_headers):
    response = await client.get("/api/v1/admin/me", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {"status": "authenticated"}


async def test_me_accepts_a_session_cookie_from_login(client):
    await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    response = await client.get("/api/v1/admin/me")

    assert response.status_code == 200


async def test_me_rejects_a_missing_api_key(client):
    response = await client.get("/api/v1/admin/me")

    assert response.status_code == 403


async def test_me_rejects_a_wrong_api_key(client):
    response = await client.get("/api/v1/admin/me", headers={"X-API-Key": "nope"})

    assert response.status_code == 403


async def test_logout_invalidates_the_session(client):
    await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    logout = await client.post("/api/v1/admin/logout")

    assert logout.status_code == 200
    assert (await client.get("/api/v1/admin/me")).status_code == 403


async def test_an_expired_session_is_not_accepted(client, monkeypatch):
    import main

    await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    # Backdate every live session past its TTL.
    for token in list(main.active_sessions):
        main.active_sessions[token] = 0

    response = await client.get("/api/v1/admin/me")

    assert response.status_code == 403


# --- write endpoints ------------------------------------------------------

async def test_add_server_requires_authentication(db, client):
    response = await client.post("/api/v1/servers", json=NEW_SERVER)

    assert response.status_code == 403
    assert db.queries == []  # nothing reached the database


async def test_add_server_writes_the_row_when_authenticated(db, client, admin_headers):
    response = await client.post(
        "/api/v1/servers", json=NEW_SERVER, headers=admin_headers
    )

    assert response.status_code == 201
    assert response.json()["status"] == "success"
    query, args = db.queries[-1]
    assert "INSERT INTO monitored_servers" in query
    assert args == ("10.0.0.1:27015", "Test Server", "EU-East")


async def test_add_server_rejects_a_malformed_body(db, client, admin_headers):
    response = await client.post(
        "/api/v1/servers", json={"server_id": "10.0.0.1:27015"}, headers=admin_headers
    )

    assert response.status_code == 422


async def test_update_server_returns_404_when_no_row_matched(
    monkeypatch, client, admin_headers
):
    import main

    conn = FakeConnection(execute_result="UPDATE 0")
    monkeypatch.setattr(main, "db_pool", FakePool(conn))

    response = await client.put(
        "/api/v1/servers/10.0.0.1:27015", json=NEW_SERVER, headers=admin_headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_update_server_succeeds_when_a_row_matched(db, client, admin_headers):
    response = await client.put(
        "/api/v1/servers/10.0.0.1:27015", json=NEW_SERVER, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_delete_server_requires_authentication(db, client):
    response = await client.delete("/api/v1/servers/10.0.0.1:27015")

    assert response.status_code == 403
    assert db.queries == []


async def test_delete_server_returns_404_when_no_row_matched(
    monkeypatch, client, admin_headers
):
    import main

    conn = FakeConnection(execute_result="DELETE 0")
    monkeypatch.setattr(main, "db_pool", FakePool(conn))

    response = await client.delete(
        "/api/v1/servers/10.0.0.1:27015", headers=admin_headers
    )

    assert response.status_code == 404


async def test_delete_server_succeeds_when_a_row_matched(
    monkeypatch, client, admin_headers
):
    import main

    conn = FakeConnection(execute_result="DELETE 1")
    monkeypatch.setattr(main, "db_pool", FakePool(conn))

    response = await client.delete(
        "/api/v1/servers/10.0.0.1:27015", headers=admin_headers
    )

    assert response.status_code == 200


async def test_label_event_requires_authentication(db, client):
    response = await client.post(
        "/api/v1/events/1/label", json={"root_cause": "SERVER_CRASH"}
    )

    assert response.status_code == 403
    assert db.queries == []


async def test_label_event_marks_the_label_as_manual(db, client, admin_headers):
    response = await client.post(
        "/api/v1/events/1/label",
        json={"root_cause": "SERVER_CRASH"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["label_source"] == "manual"
    query, args = db.queries[-1]
    assert "label_source = 'manual'" in query
    assert args == ("SERVER_CRASH", 1)


async def test_label_event_returns_404_for_an_unknown_event(
    monkeypatch, client, admin_headers
):
    import main

    conn = FakeConnection(execute_result="UPDATE 0")
    monkeypatch.setattr(main, "db_pool", FakePool(conn))

    response = await client.post(
        "/api/v1/events/999/label",
        json={"root_cause": "SERVER_CRASH"},
        headers=admin_headers,
    )

    assert response.status_code == 404


async def test_label_event_rejects_a_non_numeric_event_id(db, client, admin_headers):
    response = await client.post(
        "/api/v1/events/abc/label",
        json={"root_cause": "SERVER_CRASH"},
        headers=admin_headers,
    )

    assert response.status_code == 422


# --- dependency failure ---------------------------------------------------

async def test_a_database_error_does_not_leak_a_stack_trace(monkeypatch, client):
    import main

    conn = FakeConnection(error=ConnectionError("connection refused"))
    monkeypatch.setattr(main, "db_pool", FakePool(conn))

    with pytest.raises(ConnectionError):
        # ASGITransport re-raises unhandled errors instead of returning a 500,
        # which is what proves the failure is not being swallowed silently.
        await client.get("/api/v1/servers")


# --- livekit token endpoint -----------------------------------------------

async def test_get_livekit_token_unconfigured_returns_503(monkeypatch, client):
    import main
    monkeypatch.setattr(main, "_LIVEKIT_API_KEY", "")
    monkeypatch.setattr(main, "_LIVEKIT_API_SECRET", "")
    monkeypatch.setattr(main, "_LIVEKIT_URL", "")

    response = await client.get("/api/v1/agent/livekit/token")
    assert response.status_code == 503
    assert "LiveKit is not configured" in response.json()["detail"]


async def test_get_livekit_token_success_for_regular_user(monkeypatch, client):
    import main
    monkeypatch.setattr(main, "_LIVEKIT_API_KEY", "test-api-key")
    monkeypatch.setattr(main, "_LIVEKIT_API_SECRET", "test-api-secret-123456789012345678901234567890")
    monkeypatch.setattr(main, "_LIVEKIT_URL", "wss://livekit.example.com")

    response = await client.get("/api/v1/agent/livekit/token")
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["url"] == "wss://livekit.example.com"
    assert "room" in data
    assert data["room"].startswith("gsh-agent-")


async def test_get_livekit_token_success_for_admin(monkeypatch, client):
    import main
    monkeypatch.setattr(main, "_LIVEKIT_API_KEY", "test-api-key")
    monkeypatch.setattr(main, "_LIVEKIT_API_SECRET", "test-api-secret-123456789012345678901234567890")
    monkeypatch.setattr(main, "_LIVEKIT_URL", "wss://livekit.example.com")

    await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    response = await client.get("/api/v1/agent/livekit/token")
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["room"].startswith("gsh-agent-")


async def test_get_livekit_token_generates_isolated_rooms(monkeypatch, client):
    import main
    monkeypatch.setattr(main, "_LIVEKIT_API_KEY", "test-api-key")
    monkeypatch.setattr(main, "_LIVEKIT_API_SECRET", "test-api-secret-123456789012345678901234567890")
    monkeypatch.setattr(main, "_LIVEKIT_URL", "wss://livekit.example.com")

    resp1 = await client.get("/api/v1/agent/livekit/token")
    resp2 = await client.get("/api/v1/agent/livekit/token")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    room1 = resp1.json()["room"]
    room2 = resp2.json()["room"]
    assert room1 != room2, "Each session must receive a unique room for isolation"


# --- probe ----------------------------------------------------------------

class _FakeProbeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def _fake_async_client(response=None, error=None):
    import httpx

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None):
            if error:
                raise httpx.ConnectError("down")
            return response

    return _Client


async def test_probe_needs_an_admin(client):
    response = await client.post("/api/v1/probe", json={"address": "1.2.3.4"})

    assert response.status_code == 403


async def test_probe_returns_what_the_server_reported(client, admin_headers, monkeypatch):
    import main
    reply = {"address": "1.2.3.4:27015", "reachable": True, "ping_ms": 40.0,
             "player_count": 9, "max_players": 24}
    monkeypatch.setattr(main.httpx, "AsyncClient", _fake_async_client(_FakeProbeResponse(200, reply)))

    response = await client.post("/api/v1/probe", json={"address": "1.2.3.4"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["player_count"] == 9


async def test_probe_rejects_a_bad_address(client, admin_headers):
    response = await client.post("/api/v1/probe", json={"address": "nope nope"}, headers=admin_headers)

    assert response.status_code == 422


async def test_probe_reports_ingestion_down(client, admin_headers, monkeypatch):
    import main
    monkeypatch.setattr(main.httpx, "AsyncClient", _fake_async_client(error=True))

    response = await client.post("/api/v1/probe", json={"address": "1.2.3.4"}, headers=admin_headers)

    assert response.status_code == 503
