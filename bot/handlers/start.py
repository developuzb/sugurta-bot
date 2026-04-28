from aiogram import Router, F, types
from aiogram.filters import Command

from keyboards.inline import start_menu_inline

router = Router()

@router.message(F.photo)
async def get_photo_id(message: types.Message):
    await message.answer(
        message.photo[-1].file_id
    )
    
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

    await message.answer_photo(
        photo="AgACAgIAAxkBAAIBy2nwx4MT55UBvU5OHJP5zp3hC8tvAAIEF2sbraiAS4m4bzYh9qGlAQADAgADeQADOwQ",  # file_id
        caption=caption,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )