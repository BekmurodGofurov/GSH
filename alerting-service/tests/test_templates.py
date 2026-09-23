import re

import pytest

from templates import _ping_emoji, _short_name, format_report


# --- _ping_emoji ----------------------------------------------------------

@pytest.mark.parametrize(
    "ping,expected",
    [
        (0.0, "🟢"),
        (99.9, "🟢"),
        (100.0, "🟡"),  # boundary: >= 100 is amber
        (199.9, "🟡"),
        (200.0, "🔴"),  # boundary: >= 200 is red
        (5000.0, "🔴"),
    ],
)
def test_ping_emoji_thresholds(ping, expected):
    assert _ping_emoji(ping) == expected


# --- _short_name ----------------------------------------------------------

def test_short_name_leaves_a_short_name_alone():
    assert _short_name("CS2 DM #1") == "CS2 DM #1"


def test_short_name_keeps_a_name_at_the_limit_intact():
    name = "x" * 38

    assert _short_name(name) == name


def test_short_name_truncates_and_marks_an_overlong_name():
    name = "x" * 60

    result = _short_name(name)

    assert len(result) == 38
    assert result.endswith("…")


def test_short_name_honours_a_custom_limit():
    result = _short_name("y" * 60, max_len=10)

    assert len(result) == 10
    assert result.endswith("…")


# --- format_report: populated window --------------------------------------

def test_report_renders_the_header(full_report):
    text = format_report(full_report)

    assert "Server Monitoring Report" in text
    assert "2026-01-01" in text
    assert "Last 1 days" in text


def test_report_renders_the_peak_ping_with_its_region_and_time(full_report):
    text = format_report(full_report)

    assert "Peak Ping" in text
    assert "CS2 DM #1" in text
    assert "Vienna" in text
    assert "245 ms" in text
    assert "09:30 UTC" in text


def test_report_lists_the_top_three_average_pings(full_report):
    text = format_report(full_report)

    assert "Average Ping (TOP 3)" in text
    assert "180 ms" in text
    assert "95 ms" in text
    assert "22 ms" in text


def test_report_names_the_most_unstable_server(full_report):
    text = format_report(full_report)

    assert "Most Unstable Server" in text
    assert "4 times" in text


def test_report_lists_every_crashed_server_when_there_is_more_than_one(full_report):
    text = format_report(full_report)

    assert "All Crashed Servers" in text
    assert "CS2 5v5 #2" in text


def test_report_omits_the_full_crash_list_for_a_single_crasher(full_report):
    full_report["top_crashers"] = full_report["top_crashers"][:1]

    text = format_report(full_report)

    assert "Most Unstable Server" in text
    assert "All Crashed Servers" not in text


def test_report_merges_crash_and_offline_into_one_counter(full_report):
    text = format_report(full_report)

    # crash=3 + offline=2
    assert "CRASH/OFFLINE: <b>5</b>" in text
    assert "HIGH_PING: <b>7</b>" in text
    assert "RECOVERY: <b>5</b>" in text
    assert "Total Events: <b>17</b>" in text


def test_report_renders_the_current_server_status(full_report):
    text = format_report(full_report)

    assert "ONLINE: <b>8</b>" in text
    assert "OFFLINE: <b>2</b>" in text
    assert "Total: <b>10</b>" in text


# --- format_report: quiet window -----------------------------------------

def test_report_handles_a_window_with_no_data(empty_report):
    text = format_report(empty_report)

    assert "Peak Ping:</b> no data available" in text
    assert "0 issues found in this window" in text
    assert "No events recorded" in text


def test_report_does_not_crash_on_an_empty_average_ping_list(empty_report):
    text = format_report(empty_report)

    assert "Average Ping (TOP 3)" not in text


def test_report_shows_a_green_status_when_nothing_is_offline(empty_report):
    text = format_report(empty_report)

    assert "✅ ONLINE: <b>10</b>" in text


@pytest.mark.parametrize(
    "offline,expected",
    [(0, "✅"), (1, "🟡"), (2, "🟡"), (3, "🔴"), (9, "🔴")],
)
def test_status_emoji_reflects_how_many_servers_are_offline(
    empty_report, offline, expected
):
    empty_report["server_statuses"] = {
        "total": 10,
        "online": 10 - offline,
        "offline": offline,
    }

    text = format_report(empty_report)

    status_line = next(
        line for line in text.splitlines() if "ONLINE: <b>" in line
    )
    assert status_line.strip().startswith(f"└ {expected}")


# --- output contract ------------------------------------------------------

def test_report_is_a_plain_string_ready_for_telegram(full_report):
    text = format_report(full_report)

    assert isinstance(text, str)
    assert text.strip()


def test_report_uses_only_telegram_supported_html_tags(full_report):
    # Telegram's HTML parse mode rejects unknown tags and fails the send.
    allowed = {"b", "i", "u", "s", "code", "pre", "a", "tg-spoiler", "blockquote"}
    tags = {t.lower() for t in re.findall(r"</?([a-zA-Z-]+)", format_report(full_report))}

    assert tags <= allowed


def test_report_signs_off_with_the_system_name(full_report):
    assert format_report(full_report).rstrip().endswith("<i>GSH Monitoring System</i>")
