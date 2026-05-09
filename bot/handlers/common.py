import logging

logger = logging.getLogger(__name__)

from aiogram import Router, F, types, Bot
from aiogram.filters import StateFilter

from config import GROUP_ID
from database.db import get_user
from services.topic_service import ensure_topic

router = Router()


# ─────────────────────────────────────────────────────────────────────────────
# USER → GROUP
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", StateFilter(None))
async def user_to_group(message: types.Message, bot: Bot):
    try:
        if message.text and message.text.startswith("/"):
            return

        user_id = message.from_user.id
        topic_id = await ensure_topic(user_id, message.from_user.full_name, bot)

        await bot.copy_message(
            chat_id=GROUP_ID,
            from_chat_id=user_id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        logger.info(f"User → Topic: {user_id}")

    except Exception as e:
        logger.error(f"User→Topic error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP → USER (debug logging bilan)
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.chat.id == GROUP_ID)
async def group_to_user(message: types.Message, bot: Bot):
    try:
        # 🔍 DEBUG — har bir guruh xabarining holatini logga yozamiz
        logger.info(
            f"GROUP MSG: thread={message.message_thread_id}, "
            f"from_bot={message.from_user.is_bot if message.from_user else 'NO_USER'}, "
            f"text={(message.text or '')[:30]}"
        )

        if message.from_user and message.from_user.is_bot:
            logger.info("→ Skip: from_bot")
            return

        if message.text and message.text.startswith("/"):
            logger.info("→ Skip: command")
            return

        topic_id = message.message_thread_id
        if not topic_id:
            logger.info("→ Skip: no topic_id")
            return

        user_id = await get_user(topic_id)
        if not user_id:
            logger.info(f"→ Skip: no user for topic {topic_id}")
            return

        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=GROUP_ID,
            message_id=message.message_id
        )
        logger.info(f"Topic → User: {user_id} ✅")

    except Exception as e:
        logger.error(f"Topic→User error: {e}", exc_info=True)