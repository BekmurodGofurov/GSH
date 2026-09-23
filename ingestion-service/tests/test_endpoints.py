import pytest

VALID_METRIC = {
    "server_id": "188.212.101.109:27015",
    "player_count": 14,
    "max_players": 24,
    "ping_ms": 38.5,
}

VALID_EVENT = {
    "server_id": "188.212.101.109:27015",
    "event_type": "CRASH",
    "root_cause": "SERVER_CRASH",
    "message": "Server stopped responding",
}


# --- health ---------------------------------------------------------------

async def test_health_reports_the_service_name(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ingestion-service"}


async def test_health_does_not_need_the_database(no_db, client):
    response = await client.get("/health")

    assert response.status_code == 200


# --- metric ingestion -----------------------------------------------------

async def test_ingest_metric_writes_the_row(db, client):
    response = await client.post("/api/v1/ingest/metric", json=VALID_METRIC)

    assert response.status_code == 200
    assert response.json() == {"status": "metric_inserted"}
    query, args = db.queries[-1]
    assert "INSERT INTO server_metrics" in query
    assert args == ("188.212.101.109:27015", 14, 24, 38.5)


@pytest.mark.parametrize("missing", ["server_id", "player_count", "max_players", "ping_ms"])
async def test_ingest_metric_rejects_a_missing_field(db, client, missing):
    payload = {k: v for k, v in VALID_METRIC.items() if k != missing}

    response = await client.post("/api/v1/ingest/metric", json=payload)

    assert response.status_code == 422
    assert db.queries == []  # nothing reached the database


@pytest.mark.parametrize(
    "field,value",
    [("player_count", "many"), ("ping_ms", "fast"), ("max_players", None)],
)
async def test_ingest_metric_rejects_a_wrongly_typed_field(db, client, field, value):
    response = await client.post(
        "/api/v1/ingest/metric", json={**VALID_METRIC, field: value}
    )

    assert response.status_code == 422
    assert db.queries == []


async def test_ingest_metric_rejects_a_non_json_body(db, client):
    response = await client.post("/api/v1/ingest/metric", content=b"not json")

    assert response.status_code == 422


# --- event ingestion ------------------------------------------------------

async def test_ingest_event_writes_the_row(db, client):
    response = await client.post("/api/v1/ingest/event", json=VALID_EVENT)

    assert response.status_code == 200
    assert response.json() == {"status": "event_inserted"}
    query, args = db.queries[-1]
    assert "INSERT INTO server_events" in query
    assert args == (
        "188.212.101.109:27015",
        "CRASH",
        "SERVER_CRASH",
        "Server stopped responding",
    )


async def test_ingest_event_stores_the_default_root_cause(db, client):
    payload = {k: v for k, v in VALID_EVENT.items() if k != "root_cause"}

    response = await client.post("/api/v1/ingest/event", json=payload)

    assert response.status_code == 200
    _, args = db.queries[-1]
    assert args[2] == "NORMAL"


@pytest.mark.parametrize("missing", ["server_id", "event_type", "message"])
async def test_ingest_event_rejects_a_missing_field(db, client, missing):
    payload = {k: v for k, v in VALID_EVENT.items() if k != missing}

    response = await client.post("/api/v1/ingest/event", json=payload)

    assert response.status_code == 422
    assert db.queries == []


# --- dependency failure ---------------------------------------------------

async def test_ingest_metric_surfaces_a_database_error(failing_db, client):
    # ASGITransport re-raises instead of turning this into a 500, so the test
    # asserts the error is not swallowed and no success body is returned.
    with pytest.raises(ConnectionError):
        await client.post("/api/v1/ingest/metric", json=VALID_METRIC)


async def test_ingest_metric_fails_loudly_when_the_pool_is_missing(no_db, client):
    # db.get_db_pool() raises RuntimeError rather than returning a 503 the way
    # gateway-api does. This pins the current behaviour so a change is visible.
    with pytest.raises(RuntimeError, match="not been initialized"):
        await client.post("/api/v1/ingest/metric", json=VALID_METRIC)
