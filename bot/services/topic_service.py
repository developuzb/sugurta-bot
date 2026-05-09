"""
Topic helper — atomar get-or-create. PostgreSQL advisory lock orqali
bir foydalanuvchi uchun parallel chaqiriqlarda dublikat topic ochilishini
oldini oladi.
"""

from database.db import get_or_create_topic
from config import GROUP_ID


async def ensure_topic(user_id: int, full_name: str, bot) -> int | None:
    return await get_or_create_topic(user_id, full_name, bot, GROUP_ID)
