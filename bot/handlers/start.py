from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from keyboards.inline import start_menu_inline

from services.topic_service import ensure_topic
from database.db import clear_user_state_time

router = Router()


@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await clear_user_state_time(message.from_user.id)

    caption = (
        "<b>🛡 Avtosug'urta — bir necha tugmada tayyor</b>\n\n"
        "<blockquote>"
        "⚡ <b>10 soniyada</b> narxni biling\n"
        "🎁 <b>25% gacha</b> bonusni qaytaramiz\n"
        "💳 <b>30 kun 0%</b> nasiya — bugun pul shart emas\n"
        "📦 <b>Bepul</b> uygacha yetkazib beramiz"
        "</blockquote>\n\n"
        "🔥 <i>Hoziroq boshlang — atigi 1 daqiqa vaqtingizni oladi</i> 👇"
    )

    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"

    await ensure_topic(
        message.from_user.id,
        message.from_user.full_name,
        message.bot
    )

    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )
