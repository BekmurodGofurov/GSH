from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import MINIMUM_BASELINE_SAMPLES, app, histories

client = TestClient(app)

VALID_METRIC = {
    "id": "185.25.180.1:27015",
    "region": "Vienna",
    "player_count": 10,
    "ping_ms": 40.0,
    "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
}


def post_metric(**overrides):
    metric = {**VALID_METRIC, **overrides}
    return client.post("/predict/anomaly", json={"metric": metric})


def test_health_reports_the_service_name():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "anomaly-detection-ml"}


def test_predict_returns_the_full_response_shape():
    response = post_metric()

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == VALID_METRIC["id"]
    assert 0.0 <= body["anomaly_score"] <= 1.0
    assert isinstance(body["is_anomaly"], bool)
    assert isinstance(body["reasons"], list)
    assert body["baseline_samples"] == 0


def test_predict_applies_the_default_game():
    response = post_metric()

    assert response.status_code == 200
    assert "cs2:185.25.180.1:27015" in histories


def test_predict_detects_an_anomaly_over_http():
    for _ in range(MINIMUM_BASELINE_SAMPLES * 2):
        post_metric(ping_ms=40.0)

    response = post_metric(ping_ms=900.0)

    assert response.status_code == 200
    assert response.json()["is_anomaly"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("player_count", -1),
        ("ping_ms", -5.0),
        ("tick_rate", -1.0),
        ("match_duration_s", -10),
        ("player_count", "many"),
        ("game", "valorant"),
        ("timestamp", "not-a-date"),
    ],
)
def test_predict_rejects_invalid_metric_fields(field, value):
    response = post_metric(**{field: value})

    assert response.status_code == 422
    assert field in response.text


def test_predict_rejects_a_missing_metric_envelope():
    response = client.post("/predict/anomaly", json={})

    assert response.status_code == 422


@pytest.mark.parametrize("missing", ["id", "region", "player_count", "timestamp"])
def test_predict_rejects_a_metric_missing_required_fields(missing):
    metric = {k: v for k, v in VALID_METRIC.items() if k != missing}

    response = client.post("/predict/anomaly", json={"metric": metric})

    assert response.status_code == 422


def test_clear_baseline_resets_the_history():
    for _ in range(MINIMUM_BASELINE_SAMPLES * 2):
        post_metric()

    response = client.delete("/baseline/cs2/185.25.180.1:27015")

    assert response.status_code == 200
    assert response.json()["status"] == "baseline_cleared"
    assert "cs2:185.25.180.1:27015" not in histories
    assert post_metric().json()["baseline_samples"] == 0


def test_clear_baseline_is_idempotent_for_an_unknown_server():
    response = client.delete("/baseline/cs2/10.0.0.1:27015")

    assert response.status_code == 200
    assert response.json()["server_id"] == "10.0.0.1:27015"
