"""
nasiya.py — set_user_state_time qo'shilgan versiya
"""

import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.insurance import InsuranceState
from database.db import set_user_state_time
from services.status_service import update_status
from keyboards.inline import phone_share_kb
from handlers.cancel import cancel_button

logger = logging.getLogger(__name__)
router = Router(name="nasiya")

PHOTO_FILE_ID = "AgACAgIAAyEFAASY9hCdAAID0Wn3eHR3ZY0bP80ZpWH7XYG7Tt0dAALnFmsb8a3ASxk702gSZrJfAQADAgADeQADOwQ"


@router.callback_query(F.data == "nasiya_info")
async def nasiya_info(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    caption = (
        "💳 <b>Bugun pulingiz yo'qmi? Muammo emas!</b>\n\n"
        "<blockquote>"
        "📌 <b>Sug'urtani bugun</b> rasmiylashtiring\n"
        "📌 <b>30 kundan keyin</b> to'lang\n"
        "📌 <b>0% foiz</b> — qo'shimcha tiyin yo'q\n"
        "📌 <b>Uzum Nasiya</b> — ishonchli, tez"
        "</blockquote>\n\n"
        "🔥 <i>Mijozlarimizning ko'pchiligi shu variantni tanlaydi</i>\n\n"
        "👇 Hozir rasmiylashtiring"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Hozir rasmiylashtirish", callback_data="nasiya_checkout", style="success")],
        cancel_button(),
    ])
    await callback.message.answer_photo(photo=PHOTO_FILE_ID, caption=caption, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "nasiya_checkout")
async def nasiya_checkout(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    await state.update_data(payment_type="nasiya")

    await update_status(
        bot=callback.bot, user_id=user_id, full_name=callback.from_user.full_name,
        stage="💳 NASIYA tanladi — telefon kutilmoqda",
        details="📋 Mijoz 30 kun 0% nasiya orqali rasmiylashtirmoqchi",
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📞 <b>Telefon raqamingizni yuboring</b>\n\n"
        "<blockquote>Nasiya rasmiylashtirish uchun operator\nsiz bilan bog'lanadi</blockquote>\n\n"
        "👇 Pastdagi tugma orqali 1 ta bosish bilan yuboring\n"
        "yoki qo'lda kiriting: <code>+998901234567</code>",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.message.answer(
        "📱 <i>Tugmadan foydalaning</i>",
        reply_markup=phone_share_kb(),
    )
    await state.set_state(InsuranceState.phone)
    await set_user_state_time(user_id)
    await callback.answer()