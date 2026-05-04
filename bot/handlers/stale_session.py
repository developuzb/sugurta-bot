"""
Stale session uchun "trigger_start" callback handler.
Bu handler /start tugmasi bosilganda chaqiriladi va `start` funksiyasini chaqiradi.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

router = Router(name="stale_session")


@router.callback_query(F.data == "trigger_start")
async def trigger_start(callback: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchini /start ga olib boradi (state'ni tozalab)."""
    await state.clear()
    await callback.answer()

    # start handler'ni chaqirib bo'lmagani uchun, foydalanuvchiga
    # yo'l-yo'riq beramiz
    await callback.message.answer(
        "👇 Pastdagi <b>/start</b> tugmasini bosing yoki yozing",
        parse_mode="HTML"
    )