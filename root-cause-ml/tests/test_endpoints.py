import pytest
from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)

VALID_INCIDENT = {
    "server_id": "51.77.47.223:27015",
    "region": "Warsaw",
    "player_count": 0,
    "max_players": 32,
    "ping_ms": 5.0,
    "anomaly_score": 0.95,
    "ping_delta": 0.0,
    "player_delta": -12,
    "servers_affected_same_region": 1,
}


def post_incident(**overrides):
    return client.post("/predict/root-cause", json={**VALID_INCIDENT, **overrides})


def test_health_reports_model_status():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "root-cause-ml"
    # A version-mismatched .pkl degrades the service instead of failing it.
    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["model_loaded"], bool)


def test_health_stays_up_when_the_model_cannot_be_loaded(monkeypatch):
    def boom():
        raise RuntimeError("unpickling failed")

    monkeypatch.setattr(main, "load_model", boom)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["model_loaded"] is False


def test_predict_returns_the_documented_response_shape():
    response = post_incident()

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == VALID_INCIDENT["server_id"]
    assert body["timestamp"]
    assert body["primary_cause"]
    assert body["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    assert body["explanation"]
    assert body["recommendation"]
    assert body["predictions"]
    assert body["predictions"][0]["rank"] == 1
    assert body["primary_cause"] == body["predictions"][0]["root_cause"]


def test_predict_applies_schema_defaults_for_optional_fields():
    response = client.post(
        "/predict/root-cause",
        json={"server_id": "51.77.47.223:27015", "player_count": 10},
    )

    assert response.status_code == 200
    assert response.json()["predictions"]


def test_predict_echoes_the_supplied_timestamp():
    response = post_incident(timestamp="2026-01-01T12:00:00+00:00")

    assert response.status_code == 200
    assert response.json()["timestamp"].startswith("2026-01-01T12:00:00")


@pytest.mark.parametrize(
    "field,value",
    [
        ("player_count", -1),
        ("max_players", -5),
        ("ping_ms", -1.0),
        ("anomaly_score", 1.5),
        ("anomaly_score", -0.1),
        ("servers_affected_same_region", 0),
        ("top_k", 0),
        ("top_k", 99),
        ("player_count", "lots"),
        ("timestamp", "yesterday"),
    ],
)
def test_predict_rejects_out_of_range_input(field, value):
    response = post_incident(**{field: value})

    assert response.status_code == 422
    assert field in response.text


def test_predict_rejects_a_missing_server_id():
    payload = {k: v for k, v in VALID_INCIDENT.items() if k != "server_id"}

    response = client.post("/predict/root-cause", json=payload)

    assert response.status_code == 422


def test_predict_returns_503_when_the_model_artifact_is_missing(monkeypatch):
    def missing(**kwargs):
        raise FileNotFoundError("root_cause_model.pkl")

    monkeypatch.setattr(main, "predict_root_cause", missing)

    response = post_incident()

    assert response.status_code == 503
    assert "not yet trained" in response.json()["detail"]


def test_predict_returns_500_on_an_unexpected_failure(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("feature matrix exploded")

    monkeypatch.setattr(main, "predict_root_cause", boom)

    response = post_incident()

    assert response.status_code == 500
    assert "Prediction error" in response.json()["detail"]
