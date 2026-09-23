from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared_schemas.models import (
    AlertPayload,
    AnomalyPayload,
    EventPayload,
    MetricPayload,
    ServerMetric,
)

TIMESTAMP = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _metric(**overrides) -> ServerMetric:
    payload = {
        "id": "185.25.180.1:27015",
        "region": "Vienna",
        "player_count": 12,
        "timestamp": TIMESTAMP,
    }
    payload.update(overrides)
    return ServerMetric(**payload)


# --- ServerMetric ---------------------------------------------------------

def test_server_metric_applies_documented_defaults():
    metric = _metric()

    assert metric.game == "cs2"
    assert metric.max_players == 24
    assert metric.tick_rate == 128.0
    assert metric.map == "de_mirage"
    assert metric.ping_ms is None
    assert metric.match_duration_s is None


def test_server_metric_accepts_every_supported_game():
    for game in ("cs2", "dota2", "pubg"):
        assert _metric(game=game).game == game


def test_server_metric_rejects_unsupported_game():
    with pytest.raises(ValidationError) as exc_info:
        _metric(game="valorant")

    assert "game" in str(exc_info.value)


@pytest.mark.parametrize("missing_field", ["id", "region", "player_count", "timestamp"])
def test_server_metric_requires_core_fields(missing_field):
    payload = {
        "id": "185.25.180.1:27015",
        "region": "Vienna",
        "player_count": 12,
        "timestamp": TIMESTAMP,
    }
    del payload[missing_field]

    with pytest.raises(ValidationError) as exc_info:
        ServerMetric(**payload)

    assert missing_field in str(exc_info.value)


def test_server_metric_rejects_non_numeric_player_count():
    with pytest.raises(ValidationError):
        _metric(player_count="many")


def test_server_metric_parses_iso_timestamp_string():
    metric = _metric(timestamp="2026-01-01T12:00:00+00:00")

    assert metric.timestamp == TIMESTAMP


# --- MetricPayload --------------------------------------------------------

def test_metric_payload_requires_all_fields():
    payload = MetricPayload(
        server_id="185.25.180.1:27015",
        player_count=10,
        max_players=24,
        ping_ms=42.5,
    )

    assert payload.ping_ms == 42.5


def test_metric_payload_rejects_missing_ping():
    with pytest.raises(ValidationError):
        MetricPayload(server_id="a:1", player_count=1, max_players=2)


# --- EventPayload ---------------------------------------------------------

def test_event_payload_defaults_root_cause_to_normal():
    event = EventPayload(
        server_id="185.25.180.1:27015",
        event_type="RECOVERY",
        message="Server is back online",
    )

    assert event.root_cause == "NORMAL"


def test_event_payload_rejects_missing_message():
    with pytest.raises(ValidationError):
        EventPayload(server_id="a:1", event_type="CRASH")


# --- AnomalyPayload / AlertPayload ---------------------------------------

def test_anomaly_payload_nests_the_metric():
    anomaly = AnomalyPayload(metric=_metric(), anomaly_score=0.91, is_anomaly=True)

    assert anomaly.metric.id == "185.25.180.1:27015"
    assert anomaly.is_anomaly is True


def test_anomaly_payload_accepts_metric_as_dict():
    anomaly = AnomalyPayload(
        metric={
            "id": "185.25.180.1:27015",
            "region": "Warsaw",
            "player_count": 0,
            "timestamp": TIMESTAMP,
        },
        anomaly_score=1.0,
        is_anomaly=True,
    )

    assert anomaly.metric.region == "Warsaw"


def test_anomaly_payload_rejects_invalid_nested_metric():
    with pytest.raises(ValidationError):
        AnomalyPayload(
            metric={"id": "a:1", "region": "EU-East"},  # no player_count / timestamp
            anomaly_score=0.5,
            is_anomaly=False,
        )


def test_alert_payload_carries_root_cause():
    alert = AlertPayload(metric=_metric(), anomaly_score=0.95, root_cause="SERVER_CRASH")

    assert alert.root_cause == "SERVER_CRASH"


def test_alert_payload_requires_root_cause():
    with pytest.raises(ValidationError):
        AlertPayload(metric=_metric(), anomaly_score=0.95)
