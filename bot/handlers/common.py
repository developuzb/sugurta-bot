import logging

logger = logging.getLogger(__name__)

from aiogram import Router, F, types, Bot

from config import GROUP_ID
from database.db import get_topic, get_user, save_user

router = Router()

@router.message(F.chat.type == "private")
async def user_to_group(message: types.Message, bot: Bot):
    try:
        if message.text and message.text.startswith("/"):
            return

        user_id = message.from_user.id
        topic_id = await get_topic(user_id)

        # topic yo‘q bo‘lsa yaratamiz
        if not topic_id:
            topic = await bot.create_forum_topic(
                chat_id=GROUP_ID,
                name=f"{message.from_user.full_name} | {user_id}"
            )
            topic_id = topic.message_thread_id
            await save_user(user_id, topic_id)

        await bot.copy_message(
            chat_id=GROUP_ID,
            from_chat_id=user_id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )

        logger.info(f"User → Topic: {user_id}")

    except Exception as e:
        logger.error(f"User→Topic error: {e}", exc_info=True)

# ---------------- GROUP → USER ----------------
@router.message(F.chat.id == GROUP_ID)
async def group_to_user(message: types.Message, bot: Bot):
    try:
        if message.from_user.is_bot:
            return

        if message.text and message.text.startswith("/"):
            return

        topic_id = message.message_thread_id
        if not topic_id:
            return

        user_id = await get_user(topic_id)
        if not user_id:
            return

        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=GROUP_ID,
            message_id=message.message_id
        )

        logger.info(f"Topic → User: {user_id}")

    except Exception as e:
        logger.error(f"Topic→User error: {e}", exc_info=True)