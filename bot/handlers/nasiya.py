"""
nasiya.py — set_user_state_time qo'shilgan versiya
"""

import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.insurance import InsuranceState
from database.db import get_topic, set_user_state_time
from handlers.cancel import cancel_button
from config import GROUP_ID

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
    topic_id = await get_topic(user_id)
    await state.update_data(payment_type="nasiya")

    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID, message_thread_id=topic_id,
                text=(
                    f"💳 <b>NASIYA TANLANDI</b>\n━━━━━━━━━━━━━\n"
                    f"👤 {callback.from_user.full_name}\n📋 Mijoz nasiya orqali rasmiylashtirmoqchi"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"nasiya topic notify failed: {e}", exc_info=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📞 <b>Telefon raqamingizni kiriting</b>\n\n"
        "<blockquote>Nasiya rasmiylashtirish uchun operator\nsiz bilan bog'lanadi</blockquote>\n\n"
        "<code>+998XXXXXXXXX</code>",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(InsuranceState.phone)
    await set_user_state_time(user_id)
    await callback.answer()