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
import os
import json
import logging

logger = logging.getLogger(__name__)

# Xabar yuborishda qayta urinish sozlamalari
SEND_MAX_RETRIES = 3
SEND_RETRY_DELAY = 8   # soniya (har urinish orasida)
SEND_TIMEOUT    = 30   # soniya (Telegram so'rovi uchun)


async def _send_with_retry(bot: Bot, chat_id: str, text: str, document_path: str = None) -> None:
    """
    Telegram ga xabar yuborishda tarmoq xatosi bo'lsa SEND_MAX_RETRIES marta qayta urinadi.
    Agar document_path berilgan bo'lsa, fayl bilan yuboradi.
    """
    for attempt in range(1, SEND_MAX_RETRIES + 1):
        try:
            if document_path:
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
            return  # muvaffaqiyatli yuborildi
        except TelegramNetworkError as exc:
            if attempt == SEND_MAX_RETRIES:
                logger.error(
                    "❌ %d urinishdan keyin ham Telegram ga yuborib bo'lmadi: %s",
                    SEND_MAX_RETRIES, exc,
                )
                raise
            logger.warning(
                "⚠️  Telegram timeout (urinish %d/%d) — %d soniyadan so'ng qayta urinamiz...",
                attempt, SEND_MAX_RETRIES, SEND_RETRY_DELAY,
            )
            await asyncio.sleep(SEND_RETRY_DELAY)


async def send_report(bot: Bot, pool: asyncpg.Pool) -> None:
    """DB dan hisobot quradi va Telegram guruhiga yuboradi (HTML biriktirib)."""
    mode = settings.scheduler_mode

    if mode == "interval":
        lookback_minutes = settings.lookback_minutes
        lookback_days = None
        logger.info("📤 Interval hisoboti (so'nggi %d daqiqa)...", lookback_minutes)
    else:
        lookback_minutes = None
        lookback_days = settings.lookback_days
        logger.info("📤 Kunlik hisobot (so'nggi %d kun)...", lookback_days)

    try:
        report = await build_report(
            pool,
            lookback_minutes=lookback_minutes,
            lookback_days=lookback_days,
        )
        text = format_report(report)
        
        # HTML fayl yaratish
        html_content = await generate_daily_html_report(pool, lookback_days or 1)
        filepath = "/tmp/GSH_Daily_Diagnosis.html"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        text += "\n\n📄 <i>Barcha serverlarning to'liq analitikasi (ping, o'yinchilar, vaqtlari bilan) quyidagi HTML faylda ilova qilindi. Faylni ochib bemalol tahlil qilishingiz mumkin! 👇</i>"
        
        await _send_with_retry(bot, settings.telegram_chat_id, text, document_path=filepath)
        logger.info("✅ Hisobot muvaffaqiyatli yuborildi.")
        
        # O'chirish
        if os.path.exists(filepath):
            os.remove(filepath)
            
    except TelegramNetworkError:
        logger.warning("⏭️  Bu yuborish o'tkazib yuborildi, keyingisida yana urinamiz.")
    except Exception:
        logger.exception("❌ Hisobot qurishda xatolik yuz berdi")


async def poll_and_alert_new_events(bot: Bot, pool: asyncpg.Pool) -> None:
    """Yangi, hali Telegramga yuborilmagan root cause'larni qidiradi va alert qiladi."""
    query = """
        SELECT se.id, se.time, se.server_id, ms.server_name, ms.region,
               se.root_cause, se.diagnosis, se.ping_delta, se.player_delta
        FROM server_events se
        JOIN monitored_servers ms ON ms.server_id = se.server_id
        WHERE se.is_alerted = FALSE 
          AND se.root_cause IS NOT NULL 
          AND se.root_cause NOT IN ('UNKNOWN', 'NORMAL')
        ORDER BY se.id ASC LIMIT 10;
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            if not rows:
                return
                
            alerted_ids = []
            for row in rows:
                diag = json.loads(row["diagnosis"]) if row["diagnosis"] else {}
                explanation = diag.get("explanation", "Anomaliya sababi aniqlandi.")
                recommendation = diag.get("recommendation", "")
                conf = diag.get("confidence", "UNKNOWN")
                
                text = (
                    f"🚨 <b>Yangi Anomaliya Aniqlandi</b> 🚨\n\n"
                    f"🖥 <b>Server:</b> {row['server_name']} ({row['region']})\n"
                    f"⏰ <b>Vaqti:</b> {row['time'].strftime('%H:%M:%S UTC')}\n"
                    f"💥 <b>Muammo:</b> {row['root_cause']} (Ishonchlilik: {conf})\n"
                    f"📉 <b>Holat:</b> Ping o'zgarishi: {row['ping_delta']}ms | O'yinchilar o'zgarishi: {row['player_delta']}\n\n"
                    f"💡 <b>Tushuntirish:</b> {explanation}\n"
                    f"🛠 <b>Tavsiya:</b> {recommendation}"
                )
                
                try:
                    await _send_with_retry(bot, settings.telegram_chat_id, text)
                    alerted_ids.append(row["id"])
                except Exception as e:
                    logger.error(f"Alert yuborishda xatolik: {e}")
                    
            if alerted_ids:
                await conn.execute("UPDATE server_events SET is_alerted = TRUE WHERE id = ANY($1)", alerted_ids)
                
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
    scheduler_mode="interval" → IntervalTrigger (har N daqiqada)
    scheduler_mode="daily"    → CronTrigger (har kuni HH:MM UTC da)
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    if settings.scheduler_mode == "interval":
        trigger = IntervalTrigger(minutes=settings.report_interval_minutes)
        logger.info(
            "🕐 Scheduler: INTERVAL — har %d daqiqada hisobot yuboriladi.",
            settings.report_interval_minutes,
        )
    else:
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

    # Kunlik/Interval Hisobot
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

