"""
Eslatma scheduler.

Har soatda DB'dan due eslatmalarni oladi va general guruh chatiga
"📢 Bugun eslatish kerak" xabarini tugmalar bilan yuboradi.

Operator tugmani bosib mijozga eslatma yuboradi.
"""

import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.db import get_due_reminders, mark_notified
from config import GROUP_ID

logger = logging.getLogger(__name__)

# Har 1 soatda tekshiramiz
CHECK_INTERVAL_SECONDS = 60 * 60


async def check_and_notify(bot: Bot):
    """Bugun eslatish kerak bo'lgan reminderlarni topib generalga jo'natadi."""
    today = date.today()
    due = await get_due_reminders(today)

    if not due:
        return

    logger.info(f"Found {len(due)} due reminders for {today}")

    for rem in due:
        try:
            days_left = (rem["expiry_date"] - today).days

            text = (
                f"📢 <b>BUGUN ESLATISH KERAK</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"👤 User ID: <code>{rem['user_id']}</code>\n"
                f"📞 Telefon: <code>{rem['phone']}</code>\n"
                f"📅 Sug'urta tugaydi: <b>{rem['expiry_date'].strftime('%d.%m.%Y')}</b>\n"
                f"⏳ {days_left} kun qoldi\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"#{rem['id']}\n\n"
                f"👇 Mijozga avtomatik xabar yuborish:"
            )

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔔 Mijozga eslatma yuborish",
                        callback_data=f"notify_user_{rem['id']}"
                    )]
                ]
            )

            # GENERAL chat (topic'siz)
            await bot.send_message(
                chat_id=GROUP_ID,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )

            # Mijozning shaxsiy topic'iga ham nusxa
            if rem.get("topic_id"):
                await bot.send_message(
                    chat_id=GROUP_ID,
                    message_thread_id=rem["topic_id"],
                    text=(
                        f"📢 Eslatma kuni keldi!\n"
                        f"📅 Sug'urta tugaydi: {rem['expiry_date'].strftime('%d.%m.%Y')}\n"
                        f"#{rem['id']}"
                    )
                )

            await mark_notified(rem["id"], today)

        except Exception as e:
            logger.error(f"Notify reminder {rem.get('id')} failed: {e}", exc_info=True)


async def reminder_scheduler(bot: Bot):
    """Background task — har soatda tekshiradi."""
    logger.info("Reminder scheduler started")
    while True:
        try:
            await check_and_notify(bot)
        except Exception:
            logger.error("Scheduler iteration failed", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)