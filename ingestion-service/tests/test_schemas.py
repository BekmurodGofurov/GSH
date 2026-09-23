import pytest
from pydantic import ValidationError

from schemas import EventPayload, MetricPayload, ServerCreate, ServerMetric


# --- ServerCreate ---------------------------------------------------------

def test_server_create_accepts_a_registration_payload():
    server = ServerCreate(
        server_id="188.212.101.109:27015",
        server_name="CS2 DM #1",
        region="Vienna",
    )

    assert server.server_id == "188.212.101.109:27015"
    assert server.region == "Vienna"


@pytest.mark.parametrize("missing", ["server_id", "server_name", "region"])
def test_server_create_requires_every_field(missing):
    payload = {
        "server_id": "188.212.101.109:27015",
        "server_name": "CS2 DM #1",
        "region": "Vienna",
    }
    del payload[missing]

    with pytest.raises(ValidationError) as exc_info:
        ServerCreate(**payload)

    assert missing in str(exc_info.value)


def test_server_create_rejects_a_non_string_name():
    with pytest.raises(ValidationError):
        ServerCreate(server_id="a:1", server_name=["not", "a", "string"], region="EU")


# --- re-exported shared schemas ------------------------------------------

def test_shared_schemas_are_importable_from_the_service():
    # The service inserts the repo root on sys.path so it can share models with
    # the other services; if that wiring breaks, this import fails first.
    assert MetricPayload is not None
    assert EventPayload is not None
    assert ServerMetric is not None


def test_metric_payload_round_trips_an_ingest_body():
    payload = MetricPayload(
        server_id="188.212.101.109:27015",
        player_count=14,
        max_players=24,
        ping_ms=38.5,
    )

    assert payload.model_dump() == {
        "server_id": "188.212.101.109:27015",
        "player_count": 14,
        "max_players": 24,
        "ping_ms": 38.5,
    }


def test_metric_payload_coerces_a_numeric_string_ping():
    assert MetricPayload(
        server_id="a:1", player_count=1, max_players=2, ping_ms="38.5"
    ).ping_ms == 38.5


def test_metric_payload_rejects_a_non_numeric_ping():
    with pytest.raises(ValidationError):
        MetricPayload(server_id="a:1", player_count=1, max_players=2, ping_ms="fast")


def test_event_payload_defaults_root_cause():
    event = EventPayload(server_id="a:1", event_type="CRASH", message="down")

    assert event.root_cause == "NORMAL"
