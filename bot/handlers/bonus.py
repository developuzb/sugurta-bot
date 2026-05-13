
import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from services.status_service import update_status

logger = logging.getLogger(__name__)
router = Router(name="bonus")


BONUS_TERMS_TEXT = (
    "🎁 <b>Sug'urta uchun pulingizning bir qismini qaytarib olamiz</b>\n\n"
    "<blockquote>"
    "💰 <b>Toshkent</b> — 5% bonus\n"
    "💰 <b>Viloyat</b> — 25% bonus 🔥"
    "</blockquote>\n\n"
    "♾ <b>Cheksiz:</b> nechta avto sug'urtalasangiz, har biriga bonus\n"
    "⚡ <b>10 daqiqada</b> kartangizga o'tkaziladi\n"
    "🛡 Sug'urta rasmiylashgach <b>avtomatik</b> to'lanadi\n\n"
    "🚀 <i>Bonusni qo'lingizdan boy bermang!</i>"
)


# ─────────────────────────────────────────────────────────────────────────────
# Bosh menyudagi inline "🎁 Bonus" tugmasi
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bonus")
async def show_bonus_terms(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🎁 Bonus shartlarini ko'rmoqda",
    )

    # Eski tugmalarni tozalash (bosh menyu xabarida)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Sug'urtani boshlash",
                callback_data="start_insurance",
                style="success"
            )],
            [InlineKeyboardButton(
                text="🏠 Bosh menyu",
                callback_data="go_main_menu"
            )],
        ]
    )

    await callback.message.answer(
        BONUS_TERMS_TEXT,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Eski reply tugma (agar reply keyboard'da hali ishlatilsa)
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text == "🎁 Bonusni olish")
async def show_bonus_terms_text(message: types.Message, state: FSMContext):
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Sug'urtani boshlash",
                callback_data="start_insurance",
                style="success"
            )],
            [InlineKeyboardButton(
                text="🏠 Bosh menyu",
                callback_data="go_main_menu"
            )],
        ]
    )

    await message.answer(
        BONUS_TERMS_TEXT,
        reply_markup=kb,
        parse_mode="HTML",
    )