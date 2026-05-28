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
from services.prompt_service import clear_prev_prompt

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
        "🎁 <b>20% gacha</b> bonus\n"
        "💳 <b>Uzum Nasiya</b> — 30 kun foizsiz\n"
        "📦 Uyga yetkazish (<b>2,000 so'm</b>)\n"
        "🔔 Sug'urta tugashidan eslatma"
        "</blockquote>\n\n"
        "👇 <i>Tanlang va tejang</i>"
    )
    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"
    await message.answer_photo(photo=photo, caption=caption, reply_markup=start_menu_inline(), parse_mode="HTML")


@router.callback_query(F.data == "cancel_flow")
async def cancel_flow(callback: types.CallbackQuery, state: FSMContext):
    current = await state.get_state()

    # Faol jarayon yo'q — tasdiq so'ramasdan menyuga qaytaramiz
    if not current:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ])
        await callback.message.answer("ℹ️ Hech qanday faol jarayon yo'q.", reply_markup=kb)
        await callback.answer()
        return

    # Tasdiqlash so'raymiz
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="↩️ Yo'q, davom etaman", callback_data="cancel_abort", style="success"),
            InlineKeyboardButton(text="✅ Ha, bekor qil", callback_data="cancel_confirm", style="danger"),
        ],
    ])
    await callback.message.answer(
        "❓ <b>Bekor qilishni xohlaysizmi?</b>\n\n"
        "<i>Boshlagan jarayoningiz yo'qoladi — qaytadan boshlashga to'g'ri keladi</i>",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_confirm")
async def cancel_confirm(callback: types.CallbackQuery, state: FSMContext):
    current = await state.get_state()
    await clear_prev_prompt(callback.bot, callback.message.chat.id, state)
    await state.clear()
    await clear_user_state_time(callback.from_user.id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    if current:
        await update_status(
            bot=callback.bot, user_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            stage="❌ Bekor qilindi — sabab so'ralmoqda",
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Narxi qimmat", callback_data="exit_price")],
            [InlineKeyboardButton(text="⏰ Hozir vaqtim yo'q", callback_data="exit_time")],
            [InlineKeyboardButton(text="🤔 Tushunmadim", callback_data="exit_confused")],
            [InlineKeyboardButton(text="➡️ Shunchaki chiqish", callback_data="exit_other")],
        ])
        await callback.message.answer(
            "😔 <b>Nima uchun to'xtatdingiz?</b>\n\n"
            "<i>Javobingiz xizmatimizni yaxshilashga yordam beradi</i>",
            reply_markup=kb, parse_mode="HTML",
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ])
        await callback.message.answer(
            "✅ Bekor qilindi. Boshqa amalni boshlash mumkin 👇",
            reply_markup=kb, parse_mode="HTML",
        )
    await callback.answer()


_PRICES = {
    "yengil": {"toshkent": {"limited": 192000, "unlimited": 384000},
               "viloyat":  {"limited": 160000, "unlimited": 320000}},
    "yuk":    {"toshkent": {"limited": 336000, "unlimited": 672000},
               "viloyat":  {"limited": 280000, "unlimited": 560000}},
    "bus":    {"toshkent": {"limited": 384000, "unlimited": 768000},
               "viloyat":  {"limited": 320000, "unlimited": 640000}},
    "other":  {"toshkent": {"limited": 72000,  "unlimited": 144000},
               "viloyat":  {"limited": 60000,  "unlimited": 120000}},
}
_V = {"yengil": "🚗 Yengil", "yuk": "🚚 Yuk", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}
_T = {"limited": "Oddiy", "unlimited": "👑 VIP"}


@router.callback_query(F.data == "exit_price")
async def exit_price(callback: types.CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    from database.db import get_temp_order
    temp = await get_temp_order(callback.from_user.id)

    if temp:
        vehicle = temp.get("vehicle")
        region = temp.get("region")   # "toshkent" yoki "viloyat" (price_region)
        itype = temp.get("insurance_type")
        try:
            base = _PRICES[vehicle][region][itype]
        except (KeyError, TypeError):
            base = None

        if base:
            price_6m  = int(base * 0.7)
            price_20d = int(base * 0.2)
            rate = 0.05 if region == "toshkent" else 0.25
            bonus_6m  = int(price_6m  * rate)
            bonus_20d = int(price_20d * rate)

            text = (
                f"💡 <b>Arzonroq variantlar:</b>\n\n"
                f"<blockquote>"
                f"📅 <b>6 oy</b>   →  <b>{price_6m:,} so'm</b>  🎁 +{bonus_6m:,}\n"
                f"⚡ <b>20 kun</b>  →  <b>{price_20d:,} so'm</b>  🎁 +{bonus_20d:,}\n\n"
                f"💳 Yoki <b>Uzum Nasiya</b> — 1 yillikni 30 kun foizsiz to'lang"
                f"</blockquote>\n\n"
                f"{_V.get(vehicle, vehicle)} · {_T.get(itype, itype)}"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="start_insurance")],
                [InlineKeyboardButton(text="💳 Uzum Nasiya (30 kun foizsiz)", callback_data="nasiya_info")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
            ])
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            return

    # Temp order yo'q yoki hisoblash muvaffaqiyatsiz — umumiy taklif
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="start_insurance")],
        [InlineKeyboardButton(text="💳 Uzum Nasiya — 30 kun foizsiz", callback_data="nasiya_info")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
    ])
    await callback.message.answer(
        "💡 <b>Narx haqida bir narsa!</b>\n\n"
        "<blockquote>"
        "📅 <b>6 oy variant</b> — 1 yil narxining 70%\n"
        "⚡ <b>20 kun</b> — eng arzon, qisqa muddatli\n"
        "💳 <b>Uzum Nasiya</b> — 30 kun foizsiz to'lov"
        "</blockquote>\n\n"
        "Qayta hisoblashni xohlaysizmi? 👇",
        reply_markup=kb, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "exit_time")
async def exit_time(callback: types.CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Ha, eslatib turing", callback_data="reminder_start")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
    ])
    await callback.message.answer(
        "⏰ <b>Hech gap yo'q!</b>\n\n"
        "<blockquote>"
        "📅 Sug'urta kerak bo'lganda eslatib qo'yaylik?\n"
        "Bot o'z vaqtida xabar yuboradi — siz faqat rozi bo'lsangiz yetarli 🛡"
        "</blockquote>",
        reply_markup=kb, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "exit_confused")
async def exit_confused(callback: types.CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Qayta boshlash", callback_data="start_insurance")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
    ])
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="❓ Tushunmadi — operator yordam kerak",
    )
    await callback.message.answer(
        "🤝 <b>Operator yordam beradi!</b>\n\n"
        "<blockquote>"
        "📞 Operator <b>5-10 daqiqa ichida</b> bog'lanadi\n"
        "Yoki qayta boshlasangiz — qadamma-qadam tushuntiramiz"
        "</blockquote>",
        reply_markup=kb, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "exit_other")
async def exit_other(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
    ])
    await callback.message.answer(
        "✅ Tushundik. Xizmatimizdan foydalanganingiz uchun rahmat!\n\n"
        "Kerak bo'lsa, biz doim shu yerdamiz 🛡",
        reply_markup=kb, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_abort")
async def cancel_abort(callback: types.CallbackQuery):
    # Tasdiqlash xabarini o'chiramiz, foydalanuvchi jarayonda qoladi
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Davom etyapsiz 👍")


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
        "🎁 <b>20% gacha</b> bonus\n"
        "💳 <b>Uzum Nasiya</b> — 30 kun foizsiz\n"
        "📦 Uyga yetkazish (<b>2,000 so'm</b>)\n"
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