"""
middlewares/activity.py

ActivityMiddleware — ikki vazifa:
1. Har xabarda user faolligini DB ga yozadi (mavjud logika)
2. Bot restart bo'lganda "qotib qolgan" state'ni aniqlaydi va foydalanuvchini
   yangi sessiya boshlashga yo'naltiradi (yangi logika)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

logger = logging.getLogger(__name__)

# Bot ishga tushgan vaqt — modul import qilinganida bir marta o'rnatiladi
BOT_STARTED_AT: datetime = datetime.now(tz=timezone.utc)

# Bu callback'lar stale tekshiruvidan ozod
EXEMPT_CALLBACKS = {"trigger_start", "cancel_flow", "go_main_menu"}

# Bu commandlar ozod
EXEMPT_COMMANDS = {"/start", "/cancel", "/menu", "/eslatma"}

STALE_TEXT = (
    "⏳ <b>Sessiya tugadi</b>\n\n"
    "<blockquote>"
    "Bot yangilandi va oldingi jarayoningiz\n"
    "saqlanmadi. Hech narsa yo'qolmagan —\n"
    "faqat qaytadan boshlash kerak."
    "</blockquote>\n\n"
    "👇 Davom etish uchun tugmani bosing"
)


def _restart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Yangi sessiya boshlash", callback_data="trigger_start")
    ]])


class ActivityMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: FSMContext | None = data.get("state")

        if isinstance(event, Message) and event.chat.type == "private":
            await self._track(event.from_user.id)

            if state and not self._is_exempt_message(event):
                if await self._is_stale(event.from_user.id, state):
                    await state.clear()
                    await event.answer(STALE_TEXT, reply_markup=_restart_kb(), parse_mode="HTML")
                    logger.info(f"Stale state cleared: user={event.from_user.id}")
                    return

        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type == "private":
                await self._track(event.from_user.id)

                if state and event.data not in EXEMPT_CALLBACKS:
                    if await self._is_stale(event.from_user.id, state):
                        await state.clear()
                        try:
                            await event.message.edit_reply_markup(reply_markup=None)
                        except Exception:
                            pass
                        await event.message.answer(STALE_TEXT, reply_markup=_restart_kb(), parse_mode="HTML")
                        await event.answer()
                        logger.info(f"Stale callback cleared: user={event.from_user.id}")
                        return

        return await handler(event, data)

    async def _track(self, user_id: int) -> None:
        """Foydalanuvchi faolligini yozish."""
        try:
            from database.db import db
            await db.execute(
                """
                INSERT INTO user_sessions (user_id, last_seen)
                VALUES (?, ?)
                ON CONFLICT (user_id) DO UPDATE SET last_seen = excluded.last_seen
                """,
                (user_id, datetime.now(tz=timezone.utc).isoformat()),
            )
            await db.commit()
        except Exception as e:
            logger.debug(f"Activity track failed: {e}")

    async def _is_stale(self, user_id: int, state: FSMContext) -> bool:
        """State bot restart DAN OLDIN yozilganmi?"""
        current = await state.get_state()
        if current is None:
            return False

        try:
            from database.db import db
            row = await db.execute_fetchone(
                "SELECT state_set_at FROM user_sessions WHERE user_id = ?",
                (user_id,),
            )
            if not row or not row[0]:
                return False

            state_set_at = datetime.fromisoformat(row[0])
            if state_set_at.tzinfo is None:
                state_set_at = state_set_at.replace(tzinfo=timezone.utc)

            return state_set_at < BOT_STARTED_AT

        except Exception as e:
            logger.debug(f"Stale check failed: {e}")
            return False

    def _is_exempt_message(self, message: Message) -> bool:
        if not message.text:
            return False
        return any(message.text.startswith(cmd) for cmd in EXEMPT_COMMANDS)