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

from aiogram.exceptions import TelegramForbiddenError

from database.db import get_due_reminders, mark_notified, get_stale_temp_orders, mark_reengaged
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
            # General yuborildi — qayta yubormaslik uchun darhol belgilab qo'yamiz
            await mark_notified(rem["id"], today)

            # Mijozning shaxsiy topic'iga ham nusxa (xatosi bo'lsa, qayta yubormaymiz)
            if rem.get("topic_id"):
                try:
                    await bot.send_message(
                        chat_id=GROUP_ID,
                        message_thread_id=rem["topic_id"],
                        text=(
                            f"📢 Eslatma kuni keldi!\n"
                            f"📅 Sug'urta tugaydi: {rem['expiry_date'].strftime('%d.%m.%Y')}\n"
                            f"#{rem['id']}"
                        )
                    )
                except Exception as e:
                    logger.error(f"Notify topic copy failed (rem={rem['id']}): {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Notify reminder {rem.get('id')} failed: {e}", exc_info=True)


_VEHICLE = {"yengil": "🚗 Yengil avto", "yuk": "🚚 Yuk avto", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}


async def check_reengagement(bot: Bot):
    """24 soat oldin narx ko'rib ketgan foydalanuvchilarga eslatma yuboradi."""
    stale = await get_stale_temp_orders()
    if not stale:
        return

    logger.info(f"Re-engagement: {len(stale)} users")
    for u in stale:
        try:
            v = _VEHICLE.get(u["vehicle"], u["vehicle"])
            text = (
                f"🔥 <b>Narxingiz hali ham saqlanib turibdi!</b>\n\n"
                f"<blockquote>"
                f"{v}\n"
                f"💰 {u['price']:,} so'm · 🎁 +{u['bonus']:,} bonus qaytadi\n\n"
                f"⏰ Bonus cheklangan vaqtda amal qiladi"
                f"</blockquote>\n\n"
                f"Hozir rasmiylashtiring — bonus oling 👇"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Davom etish", callback_data="start_insurance")],
                [InlineKeyboardButton(text="🔔 Keyinroq eslatib turing", callback_data="reminder_start")],
            ])
            await bot.send_message(chat_id=u["user_id"], text=text, reply_markup=kb, parse_mode="HTML")
            await mark_reengaged(u["user_id"])
        except TelegramForbiddenError:
            await mark_reengaged(u["user_id"])
        except Exception as e:
            logger.error(f"Re-engage user={u['user_id']} failed: {e}", exc_info=True)


async def reminder_scheduler(bot: Bot):
    """Background task — har soatda tekshiradi."""
    logger.info("Reminder scheduler started")
    while True:
        try:
            await check_and_notify(bot)
        except Exception:
            logger.error("Scheduler check_and_notify failed", exc_info=True)
        try:
            await check_reengagement(bot)
        except Exception:
            logger.error("Scheduler check_reengagement failed", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)