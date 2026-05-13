"""
Mijozning faoliyat statusi — operator topic'da ko'rinadigan, tahrirlanadigan
bitta xabar. Har bir handler bosqichida `update_status` chaqirib, holatni
yangilab boriladi. Operator topic'da real vaqtda mijoz qaysi bosqichda
ekanligini ko'radi.
"""

import logging
from datetime import datetime

from aiogram import Bot

from config import GROUP_ID
from database.db import get_status_msg_id, set_status_msg_id
from services.topic_service import ensure_topic

logger = logging.getLogger(__name__)


def _format(stage: str, details: str | None = None) -> str:
    now = datetime.now().strftime("%H:%M")
    body = f"📊 <b>Mijoz holati</b>\n━━━━━━━━━━━━\n🔹 {stage}"
    if details:
        body += f"\n{details}"
    body += f"\n━━━━━━━━━━━━\n🕒 Oxirgi yangilanish: {now}"
    return body


async def update_status(
    bot: Bot,
    user_id: int,
    full_name: str,
    stage: str,
    details: str | None = None,
) -> None:
    """Mijozning status xabarini yangilaydi yoki yangi yaratadi."""
    try:
        topic_id = await ensure_topic(user_id, full_name, bot)
        if not topic_id:
            return

        text = _format(stage, details)
        msg_id = await get_status_msg_id(user_id)

        if msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=GROUP_ID,
                    message_id=msg_id,
                    text=text,
                    parse_mode="HTML",
                )
                return
            except Exception:
                # Xabar o'chirilgan yoki edit qilib bo'lmaydi — yangisini yuboramiz
                pass

        sent = await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML",
        )
        await set_status_msg_id(user_id, sent.message_id)
    except Exception as e:
        logger.error(f"update_status error: {e}", exc_info=True)
