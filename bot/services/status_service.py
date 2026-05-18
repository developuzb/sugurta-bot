"""
Mijozning faoliyat tarixi — operator topic'da ko'rinadigan, tahrirlanadigan
bitta xabar. Har bir handler bosqichida `update_status` chaqirib, holatni
tarixga qo'shamiz. Operator butun timeline'ni real vaqtda ko'radi.
"""

import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from config import GROUP_ID
from database.db import (
    get_status_msg_id, set_status_msg_id,
    append_status_line, clear_status_history,
    reset_user_topic,
)
from services.topic_service import ensure_topic

logger = logging.getLogger(__name__)

MAX_HISTORY_CHARS = 3500  # Telegram message limit 4096; xavfsizlik zonasi


def _build_message(full_name: str, history: str, details: str | None) -> str:
    now = datetime.now().strftime("%H:%M")
    header = f"📊 <b>Mijoz holati</b> — {full_name}\n━━━━━━━━━━━━"
    body = f"\n📋 <b>Tarix:</b>\n{history}"
    footer = ""
    if details:
        footer = f"\n\n📌 <b>Joriy ma'lumotlar:</b>\n{details}"
    footer += f"\n━━━━━━━━━━━━\n🕒 Faol: {now}"
    return header + body + footer


async def update_status(
    bot: Bot,
    user_id: int,
    full_name: str,
    stage: str,
    details: str | None = None,
) -> None:
    """Yangi qatorni tarixga qo'shadi va xabarni tahrirlaydi (yoki yaratadi)."""
    try:
        topic_id = await ensure_topic(user_id, full_name, bot)
        if not topic_id:
            return

        now = datetime.now().strftime("%H:%M")
        line = f"🕒 {now} — {stage}"
        history = await append_status_line(user_id, line)

        # Tarix juda uzun bo'lib ketsa, eskilarni qisqartiramiz
        if len(history) > MAX_HISTORY_CHARS:
            lines = history.split("\n")
            while len("\n".join(lines)) > MAX_HISTORY_CHARS and len(lines) > 5:
                lines.pop(0)
            history = "… (eski qatorlar qisqartirildi)\n" + "\n".join(lines)

        text = _build_message(full_name, history, details)
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
            except TelegramBadRequest as e:
                if "message thread not found" in str(e):
                    # Topic o'chirilgan — tozalab qayta ochamiz
                    await _recover_topic(user_id, full_name, bot, text)
                    return
                # Boshqa xatolik (masalan xabar juda eski) — yangi xabar yuboramiz
                await set_status_msg_id(user_id, None)
            except Exception:
                await set_status_msg_id(user_id, None)

        await _send_to_topic(bot, user_id, full_name, topic_id, text)

    except Exception as e:
        logger.error(f"update_status error: {e}", exc_info=True)


async def _send_to_topic(
    bot: Bot, user_id: int, full_name: str, topic_id: int, text: str
) -> None:
    """Topicga xabar yuboradi. Thread not found bo'lsa — yangi topic ochadi."""
    try:
        sent = await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML",
        )
        await set_status_msg_id(user_id, sent.message_id)
    except TelegramBadRequest as e:
        if "message thread not found" in str(e):
            await _recover_topic(user_id, full_name, bot, text)
        else:
            logger.error(f"_send_to_topic error: {e}", exc_info=True)


async def _recover_topic(
    bot: Bot, user_id: int, full_name: str, text: str
) -> None:
    """DB dagi eskirgan topic_id ni tozalab yangi topic yaratadi."""
    logger.warning(
        "Topic not found for user=%s — resetting and creating new topic", user_id
    )
    await reset_user_topic(user_id)
    new_topic_id = await ensure_topic(user_id, full_name, bot)
    if not new_topic_id:
        return
    try:
        sent = await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=new_topic_id,
            text=text,
            parse_mode="HTML",
        )
        await set_status_msg_id(user_id, sent.message_id)
    except Exception as e:
        logger.error(f"_recover_topic send error: {e}", exc_info=True)


async def reset_status(user_id: int) -> None:
    """Sessiya tugagach status'ni reset qiladi (yangi sessiyada toza boshlanadi)."""
    await set_status_msg_id(user_id, None)
    await clear_status_history(user_id)
