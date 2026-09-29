import re
from datetime import datetime, timezone, timedelta
import asyncpg
from aiogram import Router, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
import os

from config import settings
from scheduler import send_report

router = Router()
date_pattern = re.compile(r'(\d{4})\.(\d{2})\.(\d{2})')


# ---------------------------------------------------------------------------
# /ack <event_id>  — acknowledge an alert
# ---------------------------------------------------------------------------

@router.message(Command("ack"))
async def handle_ack(message: Message, bot: Bot, pool: asyncpg.Pool):
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Usage: /ack <event_id>")
        return

    event_id = int(parts[1])
    acked_by = message.from_user.username or str(message.from_user.id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE server_events
            SET is_acknowledged = TRUE,
                acknowledged_by = $1,
                acknowledged_at = NOW()
            WHERE id = $2;
            """,
            acked_by,
            event_id,
        )

    if result == "UPDATE 0":
        await message.reply(f"Event #{event_id} not found.")
    else:
        await message.reply(f"Event #{event_id} acknowledged by @{acked_by}.")


# ---------------------------------------------------------------------------
# /mute <server_id> <minutes> [reason]  — silence alerts for a server
# ---------------------------------------------------------------------------

@router.message(Command("mute"))
async def handle_mute(message: Message, bot: Bot, pool: asyncpg.Pool):
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3 or not parts[2].isdigit():
        await message.reply("Usage: /mute <server_id> <minutes> [reason]")
        return

    server_id = parts[1]
    minutes = int(parts[2])
    reason = parts[3] if len(parts) > 3 else None
    muted_by = message.from_user.username or str(message.from_user.id)
    muted_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM monitored_servers WHERE server_id = $1;", server_id
        )
        if not exists:
            await message.reply(f"Server '{server_id}' not found.")
            return

        await conn.execute(
            """
            INSERT INTO alert_silences (server_id, muted_until, muted_by, reason)
            VALUES ($1, $2, $3, $4);
            """,
            server_id,
            muted_until,
            muted_by,
            reason,
        )

    until_str = muted_until.strftime("%H:%M UTC")
    await message.reply(
        f"Alerts for <code>{server_id}</code> muted for {minutes} min (until {until_str}).",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /unmute <server_id>  — cancel an active mute immediately
# ---------------------------------------------------------------------------

@router.message(Command("unmute"))
async def handle_unmute(message: Message, bot: Bot, pool: asyncpg.Pool):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply("Usage: /unmute <server_id>")
        return

    server_id = parts[1]
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE alert_silences SET muted_until = NOW() WHERE server_id = $1 AND muted_until > NOW();",
            server_id,
        )

    if result == "UPDATE 0":
        await message.reply(f"No active mute found for '{server_id}'.")
    else:
        await message.reply(f"Mute lifted for <code>{server_id}</code>.", parse_mode="HTML")


# ---------------------------------------------------------------------------
# /report  — send today's daily report on demand
# ---------------------------------------------------------------------------

@router.message(Command("report"))
async def handle_report_now(message: Message, bot: Bot, pool: asyncpg.Pool):
    await message.reply("Generating today's report, please wait...")
    await send_report(bot, pool)


# ---------------------------------------------------------------------------
# Date-based historical report  (@bot YYYY.MM.DD)
# ---------------------------------------------------------------------------

@router.message()
async def handle_date_query(message: Message, bot: Bot, pool: asyncpg.Pool):
    me = await bot.get_me()
    bot_mention = f"@{me.username}"

    if not message.text or bot_mention not in message.text:
        return

    match = date_pattern.search(message.text)
    if not match:
        return

    year, month, day = map(int, match.groups())

    try:
        requested_date = datetime(year, month, day).date()
    except ValueError:
        await message.reply("Invalid date format. Please use YYYY.MM.DD.")
        return

    today = datetime.now(timezone.utc).date()
    if requested_date >= today:
        await message.reply("The requested date is today or in the future. I can only provide reports for past days.")
        return

    query = "SELECT report_text, html_content FROM daily_reports WHERE report_date = $1"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, requested_date)

            if row:
                filename = f"{requested_date.strftime('%Y_%m_%d')}_report.html"
                filepath = f"/tmp/{filename}"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(row["html_content"])

                await message.reply_document(
                    document=FSInputFile(filepath),
                    caption=row["report_text"],
                    parse_mode="HTML",
                )

                if os.path.exists(filepath):
                    os.remove(filepath)
            else:
                oldest_query = "SELECT MIN(time) as oldest FROM server_metrics"
                oldest_record = await conn.fetchrow(oldest_query)

                if oldest_record and oldest_record["oldest"]:
                    oldest_date = oldest_record["oldest"].date()
                    if requested_date < oldest_date:
                        await message.reply(
                            f"No data for this date. Metrics start from {oldest_date.strftime('%Y.%m.%d')}."
                        )
                    else:
                        await message.reply("No saved report found for this date.")
                else:
                    await message.reply("No data in the database yet.")

    except Exception as e:
        import logging
        logging.error(f"Error handling date query: {e}")
        await message.reply("An error occurred while searching for the report.")
