from __future__ import annotations

from datetime import timezone
from reports import DailyReport

def _ping_emoji(ping_ms: float) -> str:
    if ping_ms >= 200:
        return "🔴"
    if ping_ms >= 100:
        return "🟡"
    return "🟢"


def _short_name(server_name: str, max_len: int = 38) -> str:
    """Server nomini qisqartiradi."""
    return server_name if len(server_name) <= max_len else server_name[:max_len - 1] + "…"


def format_report(report: DailyReport) -> str:
    lines: list[str] = []

    # --- Header ---
    lines.append("📊 <b>Server Monitoring Report</b>")
    lines.append(f"🕐 <b>{report['report_date']}</b>")
    lines.append(f"🔍 Analysis Window: <i>{report['window_label']}</i>\n")

    # --- Highest Ping (1 ta — peak) ---
    hp = report["highest_ping"]
    if hp:
        ping_emoji = _ping_emoji(hp["max_ping_ms"])
        rec_time = hp["recorded_at"].astimezone(timezone.utc).strftime("%H:%M UTC")
        lines.append(f"🏓 <b>Peak Ping:</b>")
        lines.append(
            f"  └ {ping_emoji} <code>{_short_name(hp['server_name'])}</code>\n"
            f"       📍 {hp['region']} | <b>{hp['max_ping_ms']:.0f} ms</b> @ {rec_time}"
        )
    else:
        lines.append("🏓 <b>Peak Ping:</b> no data available")

    lines.append("")

    # --- Avg Ping top 3 ---
    avg_pings = report.get("avg_pings", [])
    if avg_pings:
        lines.append("📶 <b>Average Ping (TOP 3):</b>")
        for i, ap in enumerate(avg_pings, 1):
            emoji = _ping_emoji(ap["avg_ping_ms"])
            lines.append(
                f"  {i}. {emoji} <code>{_short_name(ap['server_name'], 30)}</code>"
                f" — <b>{ap['avg_ping_ms']:.0f} ms</b> avg"
            )
    lines.append("")

    # --- Top Crashers ---
    crashers = report["top_crashers"]
    if crashers:
        top = crashers[0]
        lines.append("💥 <b>Most Unstable Server:</b>")
        lines.append(
            f"  └ 🔴 <code>{_short_name(top['server_name'])}</code>\n"
            f"       📍 {top['region']} | <b>{top['crash_count']} times</b> crashed"
        )
        if len(crashers) > 1:
            lines.append("")
            lines.append("📋 <b>All Crashed Servers:</b>")
            for i, c in enumerate(crashers, 1):
                lines.append(
                    f"  {i}. <code>{_short_name(c['server_name'], 32)}</code>"
                    f" — {c['crash_count']}x"
                )
    else:
        lines.append("💥 <b>Crash / Offline:</b> 0 issues found in this window ✅")

    lines.append("")

    # --- Event Summary ---
    ev = report["event_summary"]
    lines.append("⚠️ <b>Event Summary:</b>")
    if ev["total"] == 0:
        lines.append("  └ No events recorded ✅")
    else:
        if ev["crash"] + ev["offline"]:
            lines.append(f"  └ 🔴 CRASH/OFFLINE: <b>{ev['crash'] + ev['offline']}</b>")
        if ev["high_ping"]:
            lines.append(f"  └ 🟡 HIGH_PING: <b>{ev['high_ping']}</b>")
        if ev["recovery"]:
            lines.append(f"  └ 🟢 RECOVERY: <b>{ev['recovery']}</b>")
        lines.append(f"  └ 📌 Total Events: <b>{ev['total']}</b>")

    lines.append("")

    # --- Server Statuses ---
    st = report["server_statuses"]
    status_emoji = "✅" if st["offline"] == 0 else ("🟡" if st["offline"] <= 2 else "🔴")
    lines.append("🖥️ <b>Current Server Status:</b>")
    lines.append(
        f"  └ {status_emoji} ONLINE: <b>{st['online']}</b> | "
        f"OFFLINE: <b>{st['offline']}</b> | Total: <b>{st['total']}</b>"
    )

    lines.append("")
    lines.append("─────────────────────")
    lines.append("<i>GSH Monitoring System</i>")

    return "\n".join(lines)
