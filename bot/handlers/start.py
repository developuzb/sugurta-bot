from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile

from keyboards.inline import start_menu_inline

from services.topic_service import ensure_topic
from config import GROUP_ID

router = Router()


@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message):
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
    
    
    
@router.message(F.photo, F.chat.id == GROUP_ID, F.message_thread_id.is_(None))
async def get_file_id(message: types.Message):
    file_id = message.photo[-1].file_id
    await message.answer(f"<code>{file_id}</code>", parse_mode="HTML")