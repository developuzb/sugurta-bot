"""
Activity Tracker Middleware

Mantiq:
- Har foydalanuvchining oxirgi faolligini DB'da saqlaydi
- Yangi xabar/callback kelganda tekshiradi
- 6 soatdan ko'p vaqt o'tgan bo'lsa — /start tavsiyasini ko'rsatadi
- /start chaqirilsa, tekshirishni o'tkazib yuboradi (yangi sessiya)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
    CallbackQuery,
)

logger = logging.getLogger(__name__)

# Eski sessiya chegarasi
STALE_THRESHOLD_HOURS = 6


class ActivityMiddleware(BaseMiddleware):
    """Foydalanuvchi faolligini kuzatadi va eski sessiyani aniqlaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Faqat private chat'larda ishlaydi
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id

        # /start command'ini o'tkazib yuboramiz — yangi sessiya
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            await update_last_activity(user_id)
            return await handler(event, data)

        # Group chatlardan kelgan event'larni o'tkazib yuboramiz
        chat = data.get("event_chat")
        if chat and chat.type != "private":
            return await handler(event, data)

        # Oxirgi faollikni tekshiramiz
        last_activity = await get_last_activity(user_id)

        if last_activity:
            now = datetime.now(timezone.utc)
            # last_activity timezone-aware bo'lishini ta'minlaymiz
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            hours_passed = (now - last_activity).total_seconds() / 3600

            if hours_passed >= STALE_THRESHOLD_HOURS:
                logger.info(
                    "stale_session user=%s hours=%.1f", user_id, hours_passed
                )
                await send_stale_notice(event, hours_passed)
                # Faollikni yangilaymiz (qayta ogohlantirish bo'lmasin)
                await update_last_activity(user_id)
                return  # ⚠️ Handler ishga tushirilmaydi

        # Hammasi joyida — faollikni yangilab, davom etamiz
        await update_last_activity(user_id)
        return await handler(event, data)


async def send_stale_notice(event: TelegramObject, hours_passed: float):
    """Eski sessiya haqida foydalanuvchiga xabar."""
    if hours_passed >= 24:
        time_str = f"{int(hours_passed / 24)} kun"
    else:
        time_str = f"{int(hours_passed)} soat"

    text = (
        "👋 <b>Qaytib kelganingizdan xursandmiz!</b>\n\n"
        f"<blockquote>Oxirgi faolligingizdan beri <b>{time_str}</b> o'tdi.</blockquote>\n\n"
        "🔄 Yangi sessiya boshlash uchun /start ni bosing 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 /start - Yangi sessiya", callback_data="trigger_start")]
        ]
    )

    try:
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await event.answer("Sessiya eskirgan", show_alert=False)
    except Exception:
        logger.error("send_stale_notice_failed", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════
# DB helpers — bu funksiyalarni database/db.py ga ko'chiring
# ═══════════════════════════════════════════════════════════════════════════

async def update_last_activity(user_id: int):
    """Foydalanuvchining oxirgi faolligini yangilaydi."""
    from database.db import pool
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_activity (user_id, last_activity)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                SET last_activity = EXCLUDED.last_activity
                """,
                user_id,
                datetime.now(timezone.utc),
            )
    except Exception:
        logger.error("update_last_activity_failed user=%s", user_id, exc_info=True)


async def get_last_activity(user_id: int):
    """Foydalanuvchining oxirgi faollik vaqtini qaytaradi."""
    from database.db import pool
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_activity FROM user_activity WHERE user_id=$1",
                user_id,
            )
            return row["last_activity"] if row else None
    except Exception:
        logger.error("get_last_activity_failed user=%s", user_id, exc_info=True)
        return None