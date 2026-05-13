"""
FSM ko'p bosqichli jarayonlarda eski prompt tugmalarini avtomatik tozalash.

Har handler yangi savol yuborganda `track_prompt` chaqirib msg_id'ni
saqlaydi. Keyingi bosqichda `clear_prev_prompt` o'sha xabarning
klaviaturasini olib tashlaydi — natijada mijoz eski tugmalarni
bosib qaytib kira olmaydi.
"""

import logging
from aiogram import Bot
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def clear_prev_prompt(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Avvalgi bosqichdagi prompt xabarining inline tugmalarini o'chiradi."""
    data = await state.get_data()
    prev = data.get("prompt_msg_id")
    if not prev:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=prev, reply_markup=None
        )
    except Exception:
        pass
    await state.update_data(prompt_msg_id=None)


async def track_prompt(state: FSMContext, msg_id: int) -> None:
    """Yangi yuborilgan prompt msg_id'ni keyingi tozalash uchun saqlaydi."""
    await state.update_data(prompt_msg_id=msg_id)
