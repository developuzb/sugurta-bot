from aiogram import Router, F, types
from aiogram.filters import Command

from keyboards.inline import start_menu_inline

router = Router()  # 👈 SHUNI QO‘SH


@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message):
    text = (
        "<b>🚗 Sug‘urtani 1 daqiqada hal qilamiz</b>\n\n"

        "<blockquote>"
        "💰 <b>Narxni hozir bilasiz</b>\n"
        "🎁 <i>Bonus qo‘shib beramiz</i>\n"
        "🚚 <b>Uyingizgacha yetkazamiz</b>"
        "</blockquote>\n\n"

        "🔥 <b>Atigi 10 soniya ichida hisoblab ko‘ring</b>\n\n"

        "👇 <i>Boshlash uchun tugmani bosing</i>"
    )

    await message.answer(
        text,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )