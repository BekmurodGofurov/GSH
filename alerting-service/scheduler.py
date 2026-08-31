from __future__ import annotations

import asyncio
import logging

import asyncpg
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from reports import build_report
from templates import format_report

from html_generator import generate_daily_html_report
from aiogram.types import FSInputFile
from datetime import datetime, timezone
import os
import json
import logging

logger = logging.getLogger(__name__)

# Retry settings for sending messages
SEND_MAX_RETRIES = 3
SEND_RETRY_DELAY = 8   # seconds
SEND_TIMEOUT    = 30   # seconds

async def _send_with_retry(bot: Bot, chat_id: str, text: str, document_path: str = None) -> None:
    """
    Retries SEND_MAX_RETRIES times if there is a network error while sending to Telegram.
    If document_path is provided, it sends the message with a file.
    """
    for attempt in range(1, SEND_MAX_RETRIES + 1):
        try:
            if document_path:
                if len(text) > 1000:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="HTML",
                        request_timeout=SEND_TIMEOUT,
                    )
                    await bot.send_document(
                        chat_id=chat_id,
                        document=FSInputFile(document_path),
                        caption="📄 Attached Daily HTML Report",
                        request_timeout=SEND_TIMEOUT,
                    )
                else:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=FSInputFile(document_path),
                        caption=text,
                        parse_mode="HTML",
                        request_timeout=SEND_TIMEOUT,
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    request_timeout=SEND_TIMEOUT,
                )
            return  # Successfully sent
        except TelegramNetworkError as exc:
            if attempt == SEND_MAX_RETRIES:
                logger.error(
                    "❌ Failed to send to Telegram after %d attempts: %s",
                    SEND_MAX_RETRIES, exc,
                )
                raise
            logger.warning(
                "⚠️  Telegram timeout (attempt %d/%d) — retrying in %d seconds...",
                attempt, SEND_MAX_RETRIES, SEND_RETRY_DELAY,
            )
            await asyncio.sleep(SEND_RETRY_DELAY)


from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

async def send_report(bot: Bot, pool: asyncpg.Pool) -> None:
    """Builds a daily report, sends it to Telegram (with HTML), and caches it in the DB."""
    lookback_days = settings.lookback_days
    logger.info("📤 Daily report (last %d days)...", lookback_days)

    try:
        report = await build_report(pool, lookback_days=lookback_days)
        text = format_report(report)
        
        # Create HTML file and JSON
        html_content, json_data = await generate_daily_html_report(pool, lookback_days)
        
        now = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y_%m_%d')}_report.html"
        filepath = f"/tmp/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        text += f"\n\n📄 <i>Full server analytics (ping, players, with exact times) are attached in the HTML file below. Open the file to analyze! 👇</i>\n\n#daily_report"
        
        # Cache to daily_reports
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO daily_reports (report_date, report_text, html_content, json_data) VALUES ($1, $2, $3, $4) ON CONFLICT (report_date) DO UPDATE SET report_text=$2, html_content=$3, json_data=$4",
                    now.date(), text, html_content, json.dumps(json_data, cls=DecimalEncoder)
                )
        except Exception as e:
            logger.error(f"Error caching report: {e}")

        await _send_with_retry(bot, settings.telegram_chat_id, text, document_path=filepath)
        logger.info("✅ Report sent successfully.")
        
        if os.path.exists(filepath):
            os.remove(filepath)
            
    except TelegramNetworkError:
        logger.warning("⏭️  This send was skipped, will retry on next schedule.")
    except Exception:
        logger.exception("❌ Error building report")


async def poll_and_alert_new_events(bot: Bot, pool: asyncpg.Pool) -> None:
    """Polls for new, un-alerted root causes and sends alerts.

    Batch size is intentionally small (3 per cycle) to stay within
    Telegram's group rate limit (~20 msg/min). With a 15s interval
    and 1.5s inter-message delay, worst-case throughput is ~9 alerts/min.
    """
    query = """
        SELECT se.id, se.time, se.server_id, ms.server_name, ms.region,
               se.root_cause, se.diagnosis, se.ping_delta, se.player_delta
        FROM server_events se
        JOIN monitored_servers ms ON ms.server_id = se.server_id
        WHERE se.is_alerted = FALSE 
          AND se.root_cause IS NOT NULL 
          AND se.root_cause NOT IN ('UNKNOWN', 'NORMAL')
        ORDER BY se.id ASC LIMIT 3;
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            if not rows:
                return

            alerted_ids = []
            for i, row in enumerate(rows):
                diag = json.loads(row["diagnosis"]) if row["diagnosis"] else {}
                explanation = diag.get("explanation", "Anomaly cause detected.")
                recommendation = diag.get("recommendation", "")
                conf = diag.get("confidence", "UNKNOWN")

                text = (
                    f"🚨 <b>New Anomaly Detected</b> 🚨\n\n"
                    f"🖥 <b>Server:</b> {row['server_name']} ({row['region']})\n"
                    f"🌐 <b>IP/Port:</b> {row['server_id']}\n"
                    f"⏰ <b>Time:</b> {row['time'].strftime('%H:%M:%S UTC')}\n"
                    f"💥 <b>Issue:</b> {row['root_cause']} (Confidence: {conf})\n"
                    f"📉 <b>Status:</b> Ping Delta: {row['ping_delta']}ms | Player Delta: {row['player_delta']}\n\n"
                    f"💡 <b>Explanation:</b> {explanation}\n"
                    f"🛠 <b>Recommendation:</b> {recommendation}\n\n"
                    f"#event"
                )

                try:
                    await _send_with_retry(bot, settings.telegram_chat_id, text)
                    alerted_ids.append(row["id"])
                    # Telegram group rate limit: ~1 msg/sec — wait between messages
                    if i < len(rows) - 1:
                        await asyncio.sleep(1.5)
                except Exception as e:
                    logger.error(f"Alert yuborishda xatolik: {e}")

            if alerted_ids:
                await conn.execute("UPDATE server_events SET is_alerted = TRUE WHERE id = ANY($1)", alerted_ids)
                logger.info("✅ %d alert(s) marked as sent.", len(alerted_ids))

    except Exception as e:
        logger.error(f"Polling error: {e}")


def create_bot_with_timeout() -> Bot:
    """
    aiogram Bot ni uzaytirilgan timeout bilan yaratadi.
    Default aiogram timeout 5 soniya — biz 30 soniyaga oshiramiz.
    """
    session = AiohttpSession(timeout=SEND_TIMEOUT)
    return Bot(token=settings.telegram_bot_token, session=session)


def create_scheduler(bot: Bot, pool: asyncpg.Pool) -> AsyncIOScheduler:
    """
    Faqat Daily rejimi (CronTrigger har kuni HH:MM UTC da) ishlaydi.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    trigger = CronTrigger(
        hour=settings.report_hour_utc,
        minute=settings.report_minute_utc,
        timezone="UTC",
    )
    logger.info(
        "🕐 Scheduler: DAILY — har kuni %02d:%02d UTC da hisobot yuboriladi.",
        settings.report_hour_utc,
        settings.report_minute_utc,
    )

    # Kunlik Hisobot
    scheduler.add_job(
        send_report,
        trigger=trigger,
        kwargs={"bot": bot, "pool": pool},
        id="report_job",
        name="Server hisoboti",
        replace_existing=True,
        misfire_grace_time=60,
    )
    
    # Tezkor anomaliya alerting
    scheduler.add_job(
        poll_and_alert_new_events,
        trigger=IntervalTrigger(seconds=15),
        kwargs={"bot": bot, "pool": pool},
        id="alert_job",
        name="Anomaliya tekshiruvi",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler

