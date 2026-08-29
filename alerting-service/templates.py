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
    lines.append("📊 <b>Server Monitoring Hisoboti</b>")
    lines.append(f"🕐 <b>{report['report_date']}</b>")
    lines.append(f"🔍 Tahlil oynasi: <i>{report['window_label']}</i>\n")

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
        lines.append("🏓 <b>Peak Ping:</b> ma'lumot yo'q")

    lines.append("")

    # --- Avg Ping top 3 ---
    avg_pings = report.get("avg_pings", [])
    if avg_pings:
        lines.append("📶 <b>O'rtacha Ping (TOP 3):</b>")
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
        lines.append("💥 <b>Eng Ko'p Yongan Server:</b>")
        lines.append(
            f"  └ 🔴 <code>{_short_name(top['server_name'])}</code>\n"
            f"       📍 {top['region']} | <b>{top['crash_count']} marta</b> crash"
        )
        if len(crashers) > 1:
            lines.append("")
            lines.append("📋 <b>Barcha Yonganlar:</b>")
            for i, c in enumerate(crashers, 1):
                lines.append(
                    f"  {i}. <code>{_short_name(c['server_name'], 32)}</code>"
                    f" — {c['crash_count']}x"
                )
    else:
        lines.append("💥 <b>Crash / Offline:</b> bu oynada hech narsa yo'q ✅")

    lines.append("")

    # --- Event Summary ---
    ev = report["event_summary"]
    lines.append("⚠️ <b>Voqealar:</b>")
    if ev["total"] == 0:
        lines.append("  └ Hech qanday voqea qayd etilmagan ✅")
    else:
        if ev["crash"] + ev["offline"]:
            lines.append(f"  └ 🔴 CRASH/OFFLINE: <b>{ev['crash'] + ev['offline']} ta</b>")
        if ev["high_ping"]:
            lines.append(f"  └ 🟡 HIGH_PING: <b>{ev['high_ping']} ta</b>")
        if ev["recovery"]:
            lines.append(f"  └ 🟢 RECOVERY: <b>{ev['recovery']} ta</b>")
        lines.append(f"  └ 📌 Jami: <b>{ev['total']} ta</b>")

    lines.append("")

    # --- Server Statuses ---
    st = report["server_statuses"]
    status_emoji = "✅" if st["offline"] == 0 else ("🟡" if st["offline"] <= 2 else "🔴")
    lines.append("🖥️ <b>Server Holati (hozir):</b>")
    lines.append(
        f"  └ {status_emoji} ONLINE: <b>{st['online']}</b> | "
        f"OFFLINE: <b>{st['offline']}</b> | Jami: <b>{st['total']}</b>"
    )

    lines.append("")
    lines.append("─────────────────────")
    lines.append("<i>GSH Monitoring System</i>")

    return "\n".join(lines)
