from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile

from keyboards.inline import start_menu_inline

# YANGI IMPORTLAR
from database.db import get_topic, save_user
from config import GROUP_ID

router = Router()


@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message):

    # =========================
    # DUPLICATE TOPIC PROTECTION
    # =========================
    existing_topic = await get_topic(
        message.from_user.id
    )

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

    photo = FSInputFile(
        "bot/images/start_banner.jpg"
    )


    # Agar user oldin bo‘lsa
    # yangi topic OCHILMAYDI
    if existing_topic:
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=start_menu_inline(),
            parse_mode="HTML"
        )
        return


    # =========================
    # FAQAT YANGI USER UCHUN
    # TOPIC YARATISH
    # =========================
    topic = await message.bot.create_forum_topic(
        chat_id=GROUP_ID,
        name=f"{message.from_user.full_name}"
    )


    # Darhol mapping save
    await save_user(
        message.from_user.id,
        topic.message_thread_id
    )


    # Welcome
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )
    
    
@router.message(F.photo)
async def get_file_id(message: types.Message):
    await message.answer(f"file_id: <code>{message.photo[-1].file_id}</code>", parse_mode="HTML")    