from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.message(F.chat.type == "private", F.text == "🎁 Bonusni olish")
async def bonus_start(message: types.Message):

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Tekshirish", callback_data="check_bonus")]
        ]
    )

    await message.answer(
        "🎁 Sizga 30 000 so‘m bonus ajratildi!\n\n❗ Faqat avtomobil egalari uchun.\n\nTekshirib ko‘ramizmi?",
        reply_markup=kb
    )


@router.callback_query(F.data == "check_bonus")
async def check_bonus(callback: types.CallbackQuery):

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha bor", callback_data="car_yes"),
                InlineKeyboardButton(text="❌ Yo‘q", callback_data="car_no")
            ]
        ]
    )

    await callback.message.answer("🚗 Sizda avtomobil bormi?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "car_no")
async def no_car(callback: types.CallbackQuery):
    await callback.message.answer("Afsuski bonus faqat avtomobil egalari uchun 😔")
    await callback.answer()


@router.callback_query(F.data == "car_yes")
async def yes_car(callback: types.CallbackQuery):

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Raqamni yuborish", callback_data="send_contact")]
        ]
    )

    await callback.message.answer(
        "Ajoyib! 🎉\n\n📲 Raqamingizni yuboring:",
        reply_markup=kb
    )

    await callback.answer()