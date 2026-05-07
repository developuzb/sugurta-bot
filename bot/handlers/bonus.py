
import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router(name="bonus")


BONUS_TERMS_TEXT = (
    "🎁 <b>Bonus shartlari</b>\n\n"
    "<blockquote>"
    "♾ <b>Cheklanmagan</b>\n"
    "Har bir foydalanuvchi istalgancha avtomobilni\n"
    "sug'urtalab, bonus ishlab olishi mumkin\n\n"
    "✅ <b>Xizmat bajarilgandan keyin</b>\n"
    "Bonus sug'urta to'liq rasmiylashtirilgach beriladi\n\n"
    "⚡ <b>10 daqiqada</b>\n"
    "Mijoz hisobiga to'g'ridan-to'g'ri o'tkaziladi"
    "</blockquote>\n\n"
    "👇 Bonus ishlash uchun sug'urtani boshlang"
)


# ─────────────────────────────────────────────────────────────────────────────
# Bosh menyudagi inline "🎁 Bonus" tugmasi
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bonus")
async def show_bonus_terms(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    # Eski tugmalarni tozalash (bosh menyu xabarida)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Sug'urtani boshlash",
                callback_data="start_insurance"
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
                callback_data="start_insurance"
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