import re
from datetime import datetime, timezone
import asyncpg
from aiogram import Router, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
import os

router = Router()
date_pattern = re.compile(r'(\d{4})\.(\d{2})\.(\d{2})')

@router.message()
async def handle_date_query(message: Message, bot: Bot, pool: asyncpg.Pool):
    # Faqat guruhdagi mention yoki reply larni tutish (yoki to'g'ridan to'g'ri)
    me = await bot.get_me()
    bot_mention = f"@{me.username}"
    
    if bot_mention not in message.text:
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
        await message.reply("The requested date is today or in the future. I can only provide reports for past days!")
        return

    # Check database
    query = "SELECT report_text, html_content FROM daily_reports WHERE report_date = $1"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, requested_date)
            
            if row:
                # Report found
                filename = f"{requested_date.strftime('%Y_%m_%d')}_report.html"
                filepath = f"/tmp/{filename}"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(row["html_content"])
                    
                await message.reply_document(
                    document=FSInputFile(filepath),
                    caption=row["report_text"],
                    parse_mode="HTML"
                )
                
                if os.path.exists(filepath):
                    os.remove(filepath)
            else:
                # Check oldest record
                oldest_query = "SELECT MIN(time) as oldest FROM server_metrics"
                oldest_record = await conn.fetchrow(oldest_query)
                
                if oldest_record and oldest_record["oldest"]:
                    oldest_date = oldest_record["oldest"].date()
                    if requested_date < oldest_date:
                        await message.reply(f"I don't have data for this date. The system started collecting metrics on {oldest_date.strftime('%Y.%m.%d')}.")
                    else:
                        await message.reply("Sorry, no saved report was found for this date (perhaps the bot was offline or the report wasn't generated).")
                else:
                    await message.reply("Sorry, there is no data in the database yet.")
                    
    except Exception as e:
        import logging
        logging.error(f"Error handling date query: {e}")
        await message.reply("An error occurred while searching for the report.")
        
