"""
delivery.py — set/clear_user_state_time qo'shilgan versiya
"""

import logging
import re

from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_topic, get_user, save_user, set_user_state_time, clear_user_state_time
from handlers.cancel import cancel_button
from config import GROUP_ID

logger = logging.getLogger(__name__)
router = Router(name="delivery")


class DeliveryState(StatesGroup):
    full_name = State()
    address = State()
    index = State()
    phone = State()


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


@router.message(F.chat.id == GROUP_ID, F.text == "/pochta")
async def admin_pochta_command(message: types.Message, bot: Bot):
    thread_id = message.message_thread_id
    if not thread_id:
        await message.reply("❌ Bu buyruq faqat topic ichida ishlaydi")
        return

    user_id = await get_user(thread_id)
    if not user_id:
        await message.reply("❌ Mijoz topilmadi")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Foydalanish", callback_data="start_delivery")],
        [InlineKeyboardButton(text="❌ Kerak emas", callback_data="cancel_delivery")]
    ])
    await bot.send_photo(
        chat_id=user_id,
        photo="AgACAgIAAyEFAASY9hCdAAID62n3hXYlmg9gNC7Js07c_Jsbt4o7AAJcF2sb8a3AS6_KLsVXwhGEAQADAgADeQADOwQ",
        caption="<b>📦 Sug'urtani yetkazib berish xizmati</b>\n\nSug'urtangizni pochta orqali olishni xohlaysizmi?",
        reply_markup=kb, parse_mode="HTML"
    )
    await message.answer("📦 Pochta xizmati taklif qilindi")
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "start_delivery")
async def user_accept_delivery(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await clear_user_state_time(callback.from_user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text="📥 Mijoz yetkazib berishni tanladi")

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📦 <b>Polisni siz uchun tayyorlab, uyingizgacha yetkazib beramiz</b> 😊\n\n"
        "Agar ma'qul bo'lsa, <b>ismingizni</b> yozing 👇",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(DeliveryState.full_name)
    await set_user_state_time(user_id)
    await callback.answer()


@router.callback_query(F.data == "cancel_delivery")
async def user_cancel_delivery(callback: types.CallbackQuery, bot: Bot):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text="❌ Mijoz yetkazib berishni rad etdi")

    kb_done = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]])
    await callback.message.answer("❌ Bekor qilindi.\n\nBoshqa savollar bo'lsa, yozavering 👇", reply_markup=kb_done)
    await callback.answer()


@router.message(DeliveryState.full_name)
async def get_name(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return
    if not message.text or len(message.text.strip()) < 3:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Ism juda qisqa, qayta yozing", reply_markup=kb)
        return

    await state.update_data(full_name=message.text.strip())
    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text=f"👤 Ism: {message.text.strip()}")

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await message.answer(
        "📍 <b>Manzilingizni yozing:</b>\n\n<blockquote>Viloyat, tuman, ko'cha\n\nMisol: <i>Toshkent, Chilonzor, 12-mavze</i></blockquote>",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(DeliveryState.address)
    await set_user_state_time(message.from_user.id)


@router.message(DeliveryState.address)
async def get_address(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return
    if not message.text or len(message.text.strip()) < 5:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Manzil to'liq emas, qayta yozing", reply_markup=kb)
        return

    await state.update_data(address=message.text.strip())
    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text=f"📍 Manzil: {message.text.strip()}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Index yo'q", callback_data="skip_index")],
        cancel_button(),
    ])
    await message.answer(
        "📮 <b>Pochta indeksi (index)</b>\n\n<blockquote>Bilmasangiz \"⏭ Index yo'q\" tugmasini bosing</blockquote>",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(DeliveryState.index)
    await set_user_state_time(message.from_user.id)


@router.callback_query(DeliveryState.index, F.data == "skip_index")
async def skip_index(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.update_data(index="—")
    await ask_phone(callback.message, state)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


@router.message(DeliveryState.index)
async def get_index(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return
    if not message.text or not message.text.strip().isdigit():
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Index yo'q", callback_data="skip_index")],
            cancel_button(),
        ])
        await message.answer("❗ Faqat raqam yozing yoki \"Index yo'q\" tugmasini bosing", reply_markup=kb)
        return

    await state.update_data(index=message.text.strip())
    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text=f"📮 Index: {message.text.strip()}")
    await ask_phone(message, state)
    await set_user_state_time(message.from_user.id)


async def ask_phone(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await message.answer(
        "📞 <b>Telefon raqamingizni yozing:</b>\n\n<code>+998901234567</code>",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(DeliveryState.phone)


@router.message(DeliveryState.phone)
async def get_phone(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return

    phone = normalize_phone(message.text.strip() if message.text else "")
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Telefon noto'g'ri\n\n+998901234567 yoki 901234567", reply_markup=kb)
        return

    data = await state.get_data()
    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    summary = (
        f"📦 <b>YETKAZIB BERISH MA'LUMOTI</b>\n━━━━━━━━━━━━━━━━━\n"
        f"👤 Ism: {data.get('full_name')}\n📍 Manzil: {data.get('address')}\n"
        f"📮 Index: {data.get('index')}\n📞 Telefon: <code>{phone}</code>\n━━━━━━━━━━━━━━━━━"
    )
    if topic_id:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=topic_id, text=summary, parse_mode="HTML")

    kb_done = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]])
    await message.answer(
        "✅ <b>Ma'lumotlar qabul qilindi!</b>\n\n"
        "<blockquote>📦 Polis tayyorlanib, manzilingizga yetkaziladi.\nOperator tez orada qo'ng'iroq qiladi.</blockquote>",
        reply_markup=kb_done, parse_mode="HTML"
    )
    await state.clear()
    await clear_user_state_time(user_id)