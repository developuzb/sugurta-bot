"""
Global Cancel/Menu Handler.

3 ta universal usul:
1. ❌ Bekor qilish tugmasi (har sana/telefon so'rovida)
2. /cancel command — istalgan vaqtda
3. /menu command — to'g'ridan-to'g'ri bosh menyuga

Bu router boshqa router'lardan OLDIN qo'shilishi kerak (state'larni qamrab olishi uchun).
"""

import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.db import clear_user_state_time
from services.status_service import update_status

logger = logging.getLogger(__name__)
router = Router(name="cancel")


@router.message(Command("cancel"), F.chat.type == "private")
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    await state.clear()
    await clear_user_state_time(message.from_user.id)

    if current:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
            ]
        )
        await message.answer(
            "✅ <b>Bekor qilindi</b>\n\n"
            "Boshqa amalni boshlash uchun /start ni bosing yoki menyuga qayting 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "ℹ️ Hech qanday faol jarayon yo'q.\n\n"
            "/start orqali boshlang"
        )


@router.message(Command("menu"), F.chat.type == "private")
async def cmd_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await clear_user_state_time(message.from_user.id)
    from keyboards.inline import start_menu_inline

    caption = (
        "<b>🏠 Bosh menyu</b>\n\n"
        "<blockquote>"
        "⚡ <b>10 soniyada</b> narx\n"
        "🎁 <b>25% gacha</b> bonus\n"
        "💳 <b>30 kun 0%</b> nasiya\n"
        "📦 Uyga yetkazish (<b>5,000 so'm</b>)\n"
        "🔔 Sug'urta tugashidan eslatma"
        "</blockquote>\n\n"
        "👇 <i>Tanlang va tejang</i>"
    )
    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"
    await message.answer_photo(photo=photo, caption=caption, reply_markup=start_menu_inline(), parse_mode="HTML")


@router.callback_query(F.data == "cancel_flow")
async def cancel_flow(callback: types.CallbackQuery, state: FSMContext):
    current = await state.get_state()
    await state.clear()
    await clear_user_state_time(callback.from_user.id)

    if current:
        await update_status(
            bot=callback.bot, user_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            stage="❌ Jarayon bekor qilindi — bosh menyuda",
        )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ]
    )

    if current:
        await callback.message.answer(
            "✅ <b>Bekor qilindi</b>\n\nBoshqa amalni boshlash mumkin 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("ℹ️ Hech qanday faol jarayon yo'q.", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "go_main_menu")
async def go_main_menu(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"go_main_menu called by user={callback.from_user.id}")
    await state.clear()
    await clear_user_state_time(callback.from_user.id)

    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🏠 Bosh menyuga qaytdi",
    )

    try:
        from keyboards.inline import start_menu_inline
        kb = start_menu_inline()
    except Exception as e:
        logger.error(f"start_menu_inline failed: {e}", exc_info=True)
        await callback.answer("❌ Xatolik", show_alert=True)
        return

    caption = (
        "<b>🏠 Bosh menyu</b>\n\n"
        "<blockquote>"
        "⚡ <b>10 soniyada</b> narx\n"
        "🎁 <b>25% gacha</b> bonus\n"
        "💳 <b>30 kun 0%</b> nasiya\n"
        "📦 Uyga yetkazish (<b>5,000 so'm</b>)\n"
        "🔔 Sug'urta tugashidan eslatma"
        "</blockquote>"
    )
    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"

    try:
        await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=kb, parse_mode="HTML")
        logger.info("go_main_menu: photo sent ✅")
    except Exception as e:
        logger.error(f"go_main_menu photo failed: {e}", exc_info=True)
        try:
            await callback.message.answer(caption, reply_markup=kb, parse_mode="HTML")
        except Exception as e2:
            logger.error(f"go_main_menu text fallback failed: {e2}", exc_info=True)

    await callback.answer()


def cancel_button() -> list[InlineKeyboardButton]:
    """Bir qatorli "Bekor qilish" tugmasi."""
    return [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_flow", style="danger")]