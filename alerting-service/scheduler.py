from __future__ import annotations

import logging

import asyncpg
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from reports import build_report
from templates import format_report

logger = logging.getLogger(__name__)


async def send_report(bot: Bot, pool: asyncpg.Pool) -> None:
    """DB dan hisobot quradi va Telegram guruhiga yuboradi."""
    mode = settings.scheduler_mode

    if mode == "interval":
        lookback_minutes = settings.lookback_minutes
        lookback_days = None
        logger.info("📤 Interval hisoboti yuborilmoqda (so'nggi %d daqiqa)...", lookback_minutes)
    else:
        lookback_minutes = None
        lookback_days = settings.lookback_days
        logger.info("📤 Kunlik hisobot yuborilmoqda (so'nggi %d kun)...", lookback_days)

    try:
        report = await build_report(
            pool,
            lookback_minutes=lookback_minutes,
            lookback_days=lookback_days,
        )
        text = format_report(report)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="HTML",
        )
        logger.info("✅ Hisobot muvaffaqiyatli yuborildi.")
    except Exception:
        logger.exception("❌ Hisobot yuborishda xatolik yuz berdi")


def create_scheduler(bot: Bot, pool: asyncpg.Pool) -> AsyncIOScheduler:
    """
    Schedulerni yaratib, job ni ro'yxatdan o'tkazadi.

    scheduler_mode="interval" → IntervalTrigger (har N daqiqada)
    scheduler_mode="daily"    → CronTrigger (har kuni HH:MM UTC da)
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    if settings.scheduler_mode == "interval":
        trigger = IntervalTrigger(minutes=settings.report_interval_minutes)
        logger.info(
            "🕐 Scheduler: INTERVAL rejimi — har %d daqiqada hisobot yuboriladi.",
            settings.report_interval_minutes,
        )
    else:
        trigger = CronTrigger(
            hour=settings.report_hour_utc,
            minute=settings.report_minute_utc,
            timezone="UTC",
        )
        logger.info(
            "🕐 Scheduler: DAILY rejimi — har kuni %02d:%02d UTC da hisobot yuboriladi.",
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
