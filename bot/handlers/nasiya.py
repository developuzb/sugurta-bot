from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.insurance import InsuranceState
from database.db import get_topic
from config import GROUP_ID
router = Router()

# 🔴 SIZ BERGAN FILE_ID
PHOTO_FILE_ID = "AgACAgIAAyEFAASY9hCdAAID0Wn3eHR3ZY0bP80ZpWH7XYG7Tt0dAALnFmsb8a3ASxk702gSZrJfAQADAgADeQADOwQ"


@router.callback_query(F.data == "nasiya_info")
async def nasiya_info(callback: types.CallbackQuery):

    # 1️⃣ RASM yuboramiz
    await callback.bot.send_photo(
        chat_id=callback.from_user.id,
        photo=PHOTO_FILE_ID
    )

    # 2️⃣ MATN + CTA
    text = (
        "💳 30 kun 0% nasiya orqali sug‘urta\n\n"
        "Endi siz sug‘urtani hoziroq rasmiylashtirib,\n"
        "to‘lovni 30 kun ichida amalga oshirishingiz mumkin.\n\n"

        "✅ 0% — hech qanday foizsiz\n"
        "✅ Tez va qulay rasmiylashtirish\n\n"

        "📌 Xizmat Uzum Nasiya orqali amalga oshiriladi\n\n"

        "👇 Davom etish uchun tugmani bosing"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Nasiya orqali rasmiylashtirish",
                    callback_data="nasiya_checkout"
                )
            ]
        ]
    )

    await callback.message.answer(
        text,
        reply_markup=kb
    )

    await callback.answer()
    
@router.callback_query(F.data == "nasiya_checkout")
async def nasiya_checkout(callback: types.CallbackQuery, state: FSMContext):

    user_id = callback.from_user.id

    # 🔹 topic olish
    topic_id = await get_topic(user_id)

    # 🔹 statega belgilaymiz
    await state.update_data(payment_type="nasiya")

    # 🔥 GROUPGA YOZAMIZ
    if topic_id:
        await callback.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=f"💳 NASIYA TANLANDI\n👤 {callback.from_user.full_name}"
        )

    # 🔹 userdan telefon so‘raymiz
    await callback.message.answer(
        "📞 Telefon raqamingizni kiriting:\n\n+998XXXXXXXXX"
    )

    await state.set_state(InsuranceState.phone)

    await callback.answer()