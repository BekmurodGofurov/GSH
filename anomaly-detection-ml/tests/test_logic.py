import math
from datetime import datetime, timedelta, timezone

import pytest

from main import (
    ANOMALY_THRESHOLD,
    MINIMUM_BASELINE_SAMPLES,
    WINDOW_SIZE,
    ServerMetric,
    _analyse,
    _feature_score,
    _mean_and_std,
    histories,
)

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_metric(player_count=10, ping_ms=40.0, offset_s=0, **overrides) -> ServerMetric:
    payload = {
        "id": "185.25.180.1:27015",
        "region": "Vienna",
        "player_count": player_count,
        "ping_ms": ping_ms,
        "timestamp": BASE_TIME + timedelta(seconds=offset_s),
    }
    payload.update(overrides)
    return ServerMetric(**payload)


def seed_baseline(samples=MINIMUM_BASELINE_SAMPLES, player_count=10, ping_ms=40.0):
    """Feed enough steady observations for the service to form a baseline."""
    for i in range(samples):
        _analyse(make_metric(player_count=player_count, ping_ms=ping_ms, offset_s=i))


# --- _mean_and_std --------------------------------------------------------

def test_mean_and_std_of_constant_series_has_no_spread():
    assert _mean_and_std([5.0, 5.0, 5.0]) == (5.0, 0.0)


def test_mean_and_std_of_single_value_returns_zero_std():
    # With one sample there is nothing to measure spread against.
    assert _mean_and_std([7.5]) == (7.5, 0.0)


def test_mean_and_std_uses_population_variance():
    mean, std = _mean_and_std([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])

    assert mean == 5.0
    assert std == pytest.approx(2.0)  # population std, not the sample std (2.138)


def test_mean_and_std_handles_negative_values():
    mean, std = _mean_and_std([-10.0, 10.0])

    assert mean == 0.0
    assert std == pytest.approx(10.0)


# --- _feature_score -------------------------------------------------------

def test_feature_score_is_zero_when_value_matches_baseline():
    assert _feature_score(50.0, [50.0] * 10) == 0.0


def test_feature_score_is_capped_at_one():
    # A wildly out-of-range value must not push the score past 1.0, because the
    # response model declares anomaly_score as 0..1.
    assert _feature_score(100_000.0, [50.0] * 10) == 1.0


def test_feature_score_stays_low_for_floating_point_noise():
    # An almost-constant metric has a near-zero std; without the scale floor a
    # rounding wobble would produce a huge z-score.
    baseline = [128.0 + i * 1e-9 for i in range(10)]

    assert _feature_score(128.000001, baseline) < 0.01


def test_feature_score_grows_with_deviation():
    baseline = [40.0, 42.0, 38.0, 41.0, 39.0, 40.0]

    small = _feature_score(45.0, baseline)
    large = _feature_score(120.0, baseline)

    assert 0.0 < small < large <= 1.0


def test_feature_score_matches_the_documented_z_score_formula():
    baseline = [10.0, 20.0, 30.0, 40.0, 50.0]
    mean, std = _mean_and_std(baseline)
    scale = max(std, abs(mean) * 0.05, 1.0)
    expected = min((abs(100.0 - mean) / scale) / 6.0, 1.0)

    assert _feature_score(100.0, baseline) == pytest.approx(expected)


# --- _analyse -------------------------------------------------------------

def test_analyse_reports_no_anomaly_during_cold_start():
    response = _analyse(make_metric(player_count=9999, ping_ms=5000.0))

    assert response.baseline_samples == 0
    assert response.anomaly_score == 0.0
    assert response.is_anomaly is False
    assert response.reasons == []


def test_analyse_stays_quiet_until_the_minimum_baseline_is_reached():
    for i in range(MINIMUM_BASELINE_SAMPLES - 1):
        response = _analyse(make_metric(offset_s=i))
        assert response.is_anomaly is False
        assert response.anomaly_score == 0.0
        assert response.baseline_samples == i


def test_analyse_scores_a_steady_server_as_normal():
    seed_baseline(samples=10)

    response = _analyse(make_metric(player_count=10, ping_ms=40.0, offset_s=10))

    assert response.is_anomaly is False
    assert response.anomaly_score < ANOMALY_THRESHOLD


def test_analyse_flags_a_latency_spike():
    seed_baseline(samples=10, ping_ms=40.0)

    response = _analyse(make_metric(player_count=10, ping_ms=900.0, offset_s=10))

    assert response.is_anomaly is True
    assert response.anomaly_score >= ANOMALY_THRESHOLD
    assert any("ping_ms" in reason for reason in response.reasons)


def test_analyse_flags_players_dropping_to_zero():
    seed_baseline(samples=10, player_count=12)

    response = _analyse(make_metric(player_count=0, ping_ms=40.0, offset_s=10))

    assert response.is_anomaly is True
    assert response.anomaly_score == 1.0
    assert "player_count dropped to zero" in response.reasons


def test_analyse_ignores_zero_players_on_a_normally_empty_server():
    # Averaging under 3 players means an empty server is business as usual.
    seed_baseline(samples=10, player_count=1)

    response = _analyse(make_metric(player_count=0, ping_ms=40.0, offset_s=10))

    assert "player_count dropped to zero" not in response.reasons


def test_analyse_excludes_the_current_sample_from_its_own_baseline():
    seed_baseline(samples=6, ping_ms=40.0)

    first = _analyse(make_metric(ping_ms=900.0, offset_s=6))
    # Feeding the same spike again is now compared against a baseline that
    # contains it, so the second score must be lower than the first.
    second = _analyse(make_metric(ping_ms=900.0, offset_s=7))

    assert first.anomaly_score > second.anomaly_score


def test_analyse_keeps_baselines_separate_per_server_and_game():
    seed_baseline(samples=10, ping_ms=40.0)

    other_server = _analyse(
        make_metric(ping_ms=900.0, offset_s=10, id="10.0.0.1:27015")
    )
    other_game = _analyse(make_metric(ping_ms=900.0, offset_s=10, game="dota2"))

    assert other_server.baseline_samples == 0
    assert other_game.baseline_samples == 0
    assert other_server.is_anomaly is False
    assert other_game.is_anomaly is False


def test_analyse_caps_history_at_the_window_size():
    seed_baseline(samples=WINDOW_SIZE + 15)

    response = _analyse(make_metric(offset_s=999))

    assert response.baseline_samples == WINDOW_SIZE
    assert len(histories["cs2:185.25.180.1:27015"]) == WINDOW_SIZE


def test_analyse_skips_features_the_metric_omits():
    # ping_ms is optional; a metric without it must not blow up.
    for i in range(10):
        _analyse(make_metric(offset_s=i, ping_ms=None))

    response = _analyse(make_metric(offset_s=10, ping_ms=None))

    assert response.is_anomaly is False
    assert math.isfinite(response.anomaly_score)


def test_analyse_score_is_always_within_the_response_bounds():
    seed_baseline(samples=10)

    for players in (0, 5, 10, 50, 10_000):
        response = _analyse(make_metric(player_count=players, offset_s=20))
        assert 0.0 <= response.anomaly_score <= 1.0
