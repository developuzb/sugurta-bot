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
        "<b>🚗 Sug'urtani 10 soniyada hal qilamiz</b>\n\n"
        "<blockquote>"
        "💰 <b>Narxni darhol bilib oling</b>\n"
        "🎁 <i>Bonus qo'shib beramiz</i>\n"
        "🚚 <b>Uyingizgacha yetkazib beramiz</b>"
        "</blockquote>\n\n"
        "👇 <i>Quyidagi tugmalardan birini tanlang</i>"
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