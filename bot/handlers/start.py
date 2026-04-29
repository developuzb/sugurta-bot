from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from keyboards.inline import start_menu_inline

router = Router()

@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message):

    caption = (
        "<b>🚗 Sug‘urtani 1 daqiqada hal qilamiz</b>\n\n"

        "<blockquote>"
        "💰 <b>Narxni hozir bilasiz</b>\n"
        "🎁 <i>Bonus qo‘shib beramiz</i>\n"
        "🚚 <b>Uyingizgacha yetkazamiz</b>"
        "</blockquote>\n\n"

        "🔥 <b>Atigi 10 soniyada hisoblang</b>\n\n"
        "👇 <i>Boshlash uchun tugmani bosing</i>"
    )

    photo = FSInputFile("bot/images/start_banner.jpg")

    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )