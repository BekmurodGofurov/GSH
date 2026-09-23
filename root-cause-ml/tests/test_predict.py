from datetime import datetime, timezone

import pytest

import predict as predict_module
from predict import (
    generate_real_world_narrative,
    predict_root_cause,
    rule_based_labeler,
)

KNOWN_CAUSES = {
    "REGIONAL_OUTAGE",
    "SERVER_CRASH",
    "DDOS_ATTACK",
    "HIGH_LATENCY",
    "PLAYER_DROP",
    "MAINTENANCE",
    "NETWORK_ISSUE",
    "UNKNOWN_ANOMALY",
}


def label(**overrides):
    kwargs = {
        "player_count": 10,
        "ping_ms": 40.0,
        "anomaly_score": 0.8,
        "ping_delta": 0.0,
        "player_delta": 0,
        "servers_affected_same_region": 1,
    }
    kwargs.update(overrides)
    return rule_based_labeler(**kwargs)


# --- rule_based_labeler ---------------------------------------------------

def test_regional_outage_wins_when_several_servers_degrade_together():
    assert label(servers_affected_same_region=3)[0]["root_cause"] == "REGIONAL_OUTAGE"


def test_regional_outage_takes_priority_over_a_latency_spike():
    # Two rules match; the region-wide signal is the more specific diagnosis.
    result = label(servers_affected_same_region=2, ping_ms=400.0, ping_delta=300.0)

    assert result[0]["root_cause"] == "REGIONAL_OUTAGE"


def test_server_crash_when_every_player_disconnects_at_once():
    assert label(player_count=0, player_delta=-12)[0]["root_cause"] == "SERVER_CRASH"


def test_empty_server_without_a_sudden_drop_is_not_a_crash():
    # An already-empty server that simply stays empty has not crashed.
    assert label(player_count=0, player_delta=0)[0]["root_cause"] != "SERVER_CRASH"


def test_ddos_when_latency_explodes_and_players_drop():
    assert label(ping_delta=200.0, player_delta=-5)[0]["root_cause"] == "DDOS_ATTACK"


def test_high_latency_when_ping_is_elevated_but_players_stay():
    assert label(ping_ms=250.0)[0]["root_cause"] == "HIGH_LATENCY"


def test_high_latency_also_triggers_on_a_moderate_ping_delta():
    assert label(ping_delta=100.0)[0]["root_cause"] == "HIGH_LATENCY"


def test_player_drop_for_a_normal_match_ending():
    assert label(player_delta=-8, ping_ms=45.0)[0]["root_cause"] == "PLAYER_DROP"


def test_unknown_anomaly_is_the_fallback():
    assert label()[0]["root_cause"] == "UNKNOWN_ANOMALY"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"servers_affected_same_region": 2},
        {"player_count": 0, "player_delta": -10},
        {"ping_delta": 200.0, "player_delta": -5},
        {"ping_ms": 300.0},
        {"player_delta": -8, "ping_ms": 40.0},
        {},
    ],
)
def test_every_rule_branch_returns_a_well_formed_ranking(kwargs):
    results = label(**kwargs)

    assert len(results) == 3
    assert [item["rank"] for item in results] == [1, 2, 3]
    assert all(item["root_cause"] in KNOWN_CAUSES for item in results)
    assert all(0.0 <= item["probability"] <= 1.0 for item in results)
    assert all(item["confidence"] in {"HIGH", "MEDIUM", "LOW"} for item in results)
    # Probabilities are ranked, so they must not increase down the list.
    probabilities = [item["probability"] for item in results]
    assert probabilities == sorted(probabilities, reverse=True)
    assert sum(probabilities) == pytest.approx(1.0, abs=0.01)


# --- predict_root_cause ---------------------------------------------------

def test_predict_returns_the_documented_diagnosis_shape():
    result = predict_root_cause(player_count=0, player_delta=-10, ping_ms=30.0)

    assert set(result) == {
        "primary_cause",
        "confidence",
        "explanation",
        "recommendation",
        "predictions",
    }
    assert result["primary_cause"] in KNOWN_CAUSES
    assert result["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    assert result["explanation"]
    assert result["recommendation"]
    assert result["predictions"]


def test_predict_primary_cause_matches_the_top_prediction():
    result = predict_root_cause(player_count=5, ping_ms=300.0, anomaly_score=0.9)

    assert result["primary_cause"] == result["predictions"][0]["root_cause"]
    assert result["confidence"] == result["predictions"][0]["confidence"]


def test_predict_falls_back_to_rules_when_no_model_is_available(monkeypatch):
    # The .pkl is committed, but a version-mismatched artifact makes load_model()
    # return None in production too — the service must still answer.
    monkeypatch.setattr(predict_module, "load_model", lambda: None)

    result = predict_root_cause(
        player_count=0, player_delta=-10, servers_affected_same_region=4
    )

    assert result["primary_cause"] == "REGIONAL_OUTAGE"


def test_predict_falls_back_to_rules_when_the_model_raises(monkeypatch):
    class ExplodingModel:
        def predict_proba(self, X):
            raise RuntimeError("corrupted estimator")

    monkeypatch.setattr(
        predict_module,
        "load_model",
        lambda: {
            "model": ExplodingModel(),
            "scaler": object(),
            "encoder": object(),
            "classes": [],
        },
    )

    result = predict_root_cause(player_count=0, player_delta=-10, ping_ms=30.0)

    assert result["primary_cause"] == "SERVER_CRASH"


def test_predict_accepts_an_explicit_timestamp():
    result = predict_root_cause(
        player_count=10,
        timestamp=datetime(2026, 1, 1, 3, 30, tzinfo=timezone.utc),
    )

    assert result["primary_cause"] in KNOWN_CAUSES


def test_predict_survives_a_zero_max_players():
    # Guards the divide-by-zero in the player_ratio feature.
    result = predict_root_cause(player_count=0, max_players=0)

    assert result["primary_cause"] in KNOWN_CAUSES


# --- generate_real_world_narrative ---------------------------------------

@pytest.mark.parametrize("cause", sorted(KNOWN_CAUSES))
def test_every_known_cause_gets_a_narrative(cause):
    narrative = generate_real_world_narrative(
        root_cause=cause,
        region="Warsaw",
        ping_ms=120.0,
        ping_delta=60.0,
        player_count=4,
        player_delta=-6,
        servers_affected_same_region=2,
    )

    assert narrative["explanation"].strip()
    assert narrative["recommendation"].strip()


def test_narrative_handles_an_unrecognised_cause():
    narrative = generate_real_world_narrative(
        root_cause="SOMETHING_NEW",
        region="Vienna",
        ping_ms=50.0,
        ping_delta=0.0,
        player_count=10,
        player_delta=0,
        servers_affected_same_region=1,
    )

    assert narrative["explanation"].strip()
    assert narrative["recommendation"].strip()


def test_regional_outage_narrative_names_the_region():
    narrative = generate_real_world_narrative(
        root_cause="REGIONAL_OUTAGE",
        region="Warsaw",
        ping_ms=300.0,
        ping_delta=250.0,
        player_count=0,
        player_delta=-20,
        servers_affected_same_region=5,
    )

    assert "Warsaw" in narrative["explanation"]
    assert "5" in narrative["explanation"]
