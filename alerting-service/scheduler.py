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

logger = logging.getLogger(__name__)

# Xabar yuborishda qayta urinish sozlamalari
SEND_MAX_RETRIES = 3
SEND_RETRY_DELAY = 8   # soniya (har urinish orasida)
SEND_TIMEOUT    = 30   # soniya (Telegram so'rovi uchun)


async def _send_with_retry(bot: Bot, chat_id: str, text: str) -> None:
    """
    Telegram ga xabar yuborishda tarmoq xatosi bo'lsa SEND_MAX_RETRIES marta qayta urinadi.
    Har urinish orasida SEND_RETRY_DELAY soniya kutadi.
    """
    for attempt in range(1, SEND_MAX_RETRIES + 1):
        try:
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
    """DB dan hisobot quradi va Telegram guruhiga yuboradi."""
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
        await _send_with_retry(bot, settings.telegram_chat_id, text)
        logger.info("✅ Hisobot muvaffaqiyatli yuborildi.")
    except TelegramNetworkError:
        # _send_with_retry ichida allaqachon log qilindi
        logger.warning("⏭️  Bu yuborish o'tkazib yuborildi, keyingisida yana urinamiz.")
    except Exception:
        logger.exception("❌ Hisobot qurishda xatolik yuz berdi")


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

    scheduler.add_job(
        send_report,
        trigger=trigger,
        kwargs={"bot": bot, "pool": pool},
        id="report_job",
        name="Server hisoboti",
        replace_existing=True,
        misfire_grace_time=60,
    )

    return scheduler
