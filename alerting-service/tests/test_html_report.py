from datetime import datetime, timezone

import pytest

from html_generator import generate_daily_html_report

MAX_PING_AT = datetime(2026, 1, 1, 14, 5, tzinfo=timezone.utc)
MAX_PLAYERS_AT = datetime(2026, 1, 1, 20, 40, tzinfo=timezone.utc)


def server_row(**overrides):
    row = {
        "server_id": "185.25.180.1:27015",
        "server_name": "CS2 DM #1",
        "region": "Vienna",
        "max_ping": 245.0,
        "max_ping_time": MAX_PING_AT,
        "min_ping": 18.0,
        "max_players": 24,
        "max_players_time": MAX_PLAYERS_AT,
        "offline_count": 2,
    }
    row.update(overrides)
    return row


async def test_report_renders_a_server_card(make_pool):
    html, data = await generate_daily_html_report(make_pool([server_row()]))

    assert "CS2 DM #1" in html
    assert "185.25.180.1:27015" in html
    assert "Vienna" in html
    assert "245.0" in html
    assert "14:05" in html
    assert "20:40" in html


async def test_report_leaves_no_unsubstituted_placeholders(make_pool):
    html, _ = await generate_daily_html_report(make_pool([server_row()]))

    for placeholder in (
        "{server_name}",
        "{server_id}",
        "{region}",
        "{max_ping}",
        "{min_ping}",
        "{max_players}",
        "{offline_count}",
        "{total_servers}",
        "{uptime_percent}",
        "{total_crashes}",
        "{active_regions}",
        "{server_cards}",
        "{region_options}",
        "{report_date}",
    ):
        assert placeholder not in html


async def test_report_returns_well_formed_json_alongside_the_html(make_pool):
    _, data = await generate_daily_html_report(make_pool([server_row()]))

    assert data["total_servers"] == 1
    assert data["total_crashes"] == 2
    assert data["active_regions"] == 1
    assert len(data["servers"]) == 1
    assert data["servers"][0]["server_id"] == "185.25.180.1:27015"


async def test_json_timestamps_are_serialisable_strings(make_pool):
    _, data = await generate_daily_html_report(make_pool([server_row()]))

    server = data["servers"][0]
    assert server["max_ping_time"] == "14:05"
    assert server["max_players_time"] == "20:40"


async def test_counts_aggregate_across_servers_and_regions(make_pool):
    rows = [
        server_row(offline_count=2),
        server_row(server_id="91.211.118.96:27015", region="Warsaw", offline_count=3),
        server_row(server_id="91.211.118.96:27018", region="Warsaw", offline_count=0),
    ]

    _, data = await generate_daily_html_report(make_pool(rows))

    assert data["total_servers"] == 3
    assert data["total_crashes"] == 5
    assert data["active_regions"] == 2


async def test_region_filter_lists_each_region_once_and_sorted(make_pool):
    rows = [
        server_row(region="Warsaw"),
        server_row(server_id="b:1", region="Vienna"),
        server_row(server_id="c:1", region="Warsaw"),
    ]

    html, _ = await generate_daily_html_report(make_pool(rows))

    assert html.count('<option value="Vienna">') == 1
    assert html.count('<option value="Warsaw">') == 1
    assert html.index('value="Vienna"') < html.index('value="Warsaw"')


async def test_an_empty_window_reports_full_uptime(make_pool):
    html, data = await generate_daily_html_report(make_pool([]))

    assert data["total_servers"] == 0
    assert data["uptime_percent"] == 100.0
    assert data["total_crashes"] == 0
    assert data["servers"] == []
    assert html.strip()


async def test_uptime_drops_half_a_point_per_crash(make_pool):
    _, data = await generate_daily_html_report(make_pool([server_row(offline_count=4)]))

    assert data["uptime_percent"] == 98.0


async def test_uptime_never_goes_negative(make_pool):
    _, data = await generate_daily_html_report(
        make_pool([server_row(offline_count=1000)])
    )

    assert data["uptime_percent"] == 0.0


async def test_missing_timestamps_render_as_not_available(make_pool):
    row = server_row(max_ping_time=None, max_players_time=None)

    html, data = await generate_daily_html_report(make_pool([row]))

    assert "N/A" in html
    assert data["servers"][0]["max_ping_time"] is None


async def test_the_query_window_matches_the_requested_lookback(make_pool):
    pool = make_pool([server_row()])

    await generate_daily_html_report(pool, lookback_days=7)

    _, args = pool.connection.queries[-1]
    start, end = args
    assert (end - start).days == 7


async def test_a_database_error_is_not_swallowed(make_pool):
    pool = make_pool(error=ConnectionError("connection refused"))

    with pytest.raises(ConnectionError):
        await generate_daily_html_report(pool)
