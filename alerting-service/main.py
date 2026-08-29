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
    logger.info("🚀 Alerting Service ishga tushmoqda...")
    logger.info("🔧 Rejim: %s", settings.scheduler_mode.upper())

    # 1. Database pool
    pool = await asyncpg.create_pool(settings.db_url, min_size=1, max_size=5)
    logger.info("✅ TimescaleDB ga ulandi: %s", settings.db_url.split("@")[-1])

    # 2. Telegram bot — 30 soniya timeout bilan, xato bo'lsa qayta urinadi
    bot = create_bot_with_timeout()

    for attempt in range(1, BOT_CONNECT_MAX_RETRIES + 1):
        try:
            me = await bot.get_me()
            logger.info("✅ Telegram Bot ulandi: @%s (chat: %s)", me.username, settings.telegram_chat_id)
            break
        except TelegramNetworkError as exc:
            logger.warning(
                "⚠️  Telegram API ga ulanib bo'lmadi (urinish %d/%d): %s",
                attempt, BOT_CONNECT_MAX_RETRIES, exc,
            )
            if attempt == BOT_CONNECT_MAX_RETRIES:
                logger.error(
                    "❌ %d marta urinib ko'rildi — Telegram API ga ulanib bo'lmadi.\n"
                    "   ➜  Internetni, BOT_TOKEN ni va AWS Security Group (443/tcp outbound) ni tekshiring.",
                    BOT_CONNECT_MAX_RETRIES,
                )
                await bot.session.close()
                raise
            await asyncio.sleep(BOT_CONNECT_RETRY_DELAY)

    # 3. Scheduler
    scheduler = create_scheduler(bot, pool)
    scheduler.start()

    # 4. SEND_ON_STARTUP=true bo'lsa — darhol yuboradi
    if settings.send_on_startup:
        logger.info("SEND_ON_STARTUP=true — darhol hisobot yuborilmoqda...")
        await send_report(bot, pool)

    # 5. SIGINT / SIGTERM kelgunga qadar kutish
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info("✅ Alerting Service tayyor. Scheduler ishlayapti.")
    await stop_event.wait()

    # Cleanup
    logger.info("🛑 To'xtatilmoqda...")
    scheduler.shutdown(wait=False)
    await pool.close()
    await bot.session.close()
    logger.info("👋 Alerting Service to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
