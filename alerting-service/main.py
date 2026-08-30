"""
main.py — Alerting Service kirish nuqtasi.

Barcha sozlamalar config.py → settings orqali olinadi.
os.getenv() bu faylda ISHLATILMAYDI.
"""

from __future__ import annotations

import asyncio
import logging
import signal

import asyncpg
from aiogram.exceptions import TelegramNetworkError

from config import settings
from scheduler import create_bot_with_timeout, create_scheduler, send_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Telegram ga ulanishda qayta urinish sozlamalari
BOT_CONNECT_MAX_RETRIES = 10
BOT_CONNECT_RETRY_DELAY = 5   # soniya


async def main() -> None:
    logger.info("🚀 Alerting Service starting...")
    logger.info("🔧 Mode: DAILY")

    # 1. Database pool
    pool = await asyncpg.create_pool(settings.db_url, min_size=1, max_size=5)
    logger.info("✅ Connected to TimescaleDB: %s", settings.db_url.split("@")[-1])

    # 2. Telegram bot — with 30s timeout and retries
    bot = create_bot_with_timeout()

    for attempt in range(1, BOT_CONNECT_MAX_RETRIES + 1):
        try:
            me = await bot.get_me()
            logger.info("✅ Telegram Bot connected: @%s (chat: %s)", me.username, settings.telegram_chat_id)
            break
        except TelegramNetworkError as exc:
            logger.warning(
                "⚠️  Failed to connect to Telegram API (attempt %d/%d): %s",
                attempt, BOT_CONNECT_MAX_RETRIES, exc,
            )
            if attempt == BOT_CONNECT_MAX_RETRIES:
                logger.error(
                    "❌ Attempted %d times — could not connect to Telegram API.\n"
                    "   ➜  Check internet, BOT_TOKEN, and firewall settings.",
                    BOT_CONNECT_MAX_RETRIES,
                )
                await bot.session.close()
                raise
            await asyncio.sleep(BOT_CONNECT_RETRY_DELAY)

    # 3. Scheduler
    scheduler = create_scheduler(bot, pool)
    scheduler.start()

    # 4. If SEND_ON_STARTUP=true — send immediately
    if settings.send_on_startup:
        logger.info("SEND_ON_STARTUP=true — sending immediate report...")
        await send_report(bot, pool)

    from aiogram import Dispatcher
    from handlers import router
    dp = Dispatcher()
    dp.include_router(router)
    
    logger.info("✅ Alerting Service ready. Scheduler running, bot is polling.")
    
    # 5. Start Polling
    await dp.start_polling(bot, pool=pool)

    # Cleanup
    logger.info("🛑 Shutting down...")
    scheduler.shutdown(wait=False)
    await pool.close()
    await bot.session.close()
    logger.info("👋 Alerting Service stopped.")


if __name__ == "__main__":
    asyncio.run(main())
