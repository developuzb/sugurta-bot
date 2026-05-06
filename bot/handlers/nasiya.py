

import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.insurance import InsuranceState
from database.db import get_topic
from handlers.cancel import cancel_button
from config import GROUP_ID

logger = logging.getLogger(__name__)
router = Router(name="nasiya")

# 🖼 Rasm
PHOTO_FILE_ID = "AgACAgIAAyEFAASY9hCdAAID0Wn3eHR3ZY0bP80ZpWH7XYG7Tt0dAALnFmsb8a3ASxk702gSZrJfAQADAgADeQADOwQ"


# ─────────────────────────────────────────────────────────────────────────────
# 1. NASIYA INFO — rasm + matn + tugmalar BIR xabarda
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "nasiya_info")
async def nasiya_info(callback: types.CallbackQuery, state: FSMContext):
    # Eski tugmalarni tozalash
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    caption = (
        "💳 <b>30 kun 0% nasiya orqali sug'urta</b>\n\n"
        "<blockquote>"
        "Endi siz sug'urtani hoziroq rasmiylashtirib,\n"
        "to'lovni 30 kun ichida amalga oshirishingiz mumkin"
        "</blockquote>\n\n"
        "✅ <b>0%</b> — hech qanday foizsiz\n"
        "✅ <b>Tez</b> va qulay rasmiylashtirish\n"
        "✅ Xizmat <b>Uzum Nasiya</b> orqali\n\n"
        "👇 Davom etish uchun tugmani bosing"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Nasiya orqali rasmiylashtirish",
                callback_data="nasiya_checkout"
            )],
            cancel_button(),
        ]
    )

    # ✅ Rasm + matn + tugmalar BIR xabarda
    await callback.message.answer_photo(
        photo=PHOTO_FILE_ID,
        caption=caption,
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 2. NASIYA CHECKOUT — telefon so'rash
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "nasiya_checkout")
async def nasiya_checkout(callback: types.CallbackQuery, state: FSMContext):
    # Eski tugmalarni tozalash
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)

    # ✅ State'ga payment_type yozamiz — receive_phone shuni tekshiradi
    await state.update_data(payment_type="nasiya")

    # Operator topic'ga xabar
    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=(
                    f"💳 <b>NASIYA TANLANDI</b>\n"
                    f"━━━━━━━━━━━━━\n"
                    f"👤 {callback.from_user.full_name}\n"
                    f"📋 Mijoz nasiya orqali rasmiylashtirmoqchi"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"nasiya topic notify failed: {e}", exc_info=True)

    # Telefon so'rash + bekor qilish tugmasi
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])

    await callback.message.answer(
        "📞 <b>Telefon raqamingizni kiriting</b>\n\n"
        "<blockquote>"
        "Nasiya rasmiylashtirish uchun operator\n"
        "siz bilan bog'lanadi"
        "</blockquote>\n\n"
        "<code>+998XXXXXXXXX</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

    # ✅ State o'rnatish — receive_phone insurance.py da
    await state.set_state(InsuranceState.phone)
    await callback.answer()