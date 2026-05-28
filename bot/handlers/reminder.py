"""
reminder.py — set/clear_user_state_time qo'shilgan versiya
"""

import logging
import re
from datetime import datetime, date, timedelta

from aiogram import Router, F, types, Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from keyboards.inline import phone_share_kb

from states.reminder import ReminderState
from database.db import (
    get_topic, get_user, save_reminder,
    attach_request_msg_id, confirm_reminder_by_msg, get_reminder,
    set_user_state_time, clear_user_state_time, get_config,
)
from services.topic_service import ensure_topic
from services.status_service import update_status, reset_status
from services.prompt_service import clear_prev_prompt, track_prompt
from utils.date_parser import parse_smart_date
from handlers.cancel import cancel_button
from config import GROUP_ID

logger = logging.getLogger(__name__)
router = Router(name="reminder")

REMINDER_PHOTO = "AgACAgIAAyEFAASY9hCdAAIE6mn4LOiLlUw2Ni_Cwp57GtmSDsnoAALyFWsb5lnAS1y4jwotS7uYAQADAgADeQADOwQ"


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


async def show_reminder_menu(message_or_callback, state: FSMContext):
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛡 Sug'urtam muddati hozircha tugamagan", callback_data="reminder_active", style="success")],
            [InlineKeyboardButton(text="📅 Yangi sug'urta uchun eslatma", callback_data="reminder_new", style="success")],
            cancel_button(),
        ]
    )
    caption = (
        "🔔 <b>Sug'urta tugashini esda saqlash qiyin</b>\n\n"
        "<blockquote>"
        "⚠️ Muddati o'tgan sug'urta = <b>jarima va xavf</b>\n"
        "✅ Biz <b>oldindan</b> eslatamiz\n"
        "📞 Operator yangi sug'urtani <b>tez</b> tayyorlaydi"
        "</blockquote>\n\n"
        "👇 Sizga qaysi variant mos?"
    )
    if isinstance(message_or_callback, types.CallbackQuery):
        sent = await message_or_callback.message.answer_photo(
            photo=REMINDER_PHOTO, caption=caption, reply_markup=kb, parse_mode="HTML"
        )
        await track_prompt(state, sent.message_id)
        await message_or_callback.answer()
    else:
        sent = await message_or_callback.answer_photo(
            photo=REMINDER_PHOTO, caption=caption, reply_markup=kb, parse_mode="HTML"
        )
        await track_prompt(state, sent.message_id)


@router.callback_query(F.data == "partner_info")
async def partner_info(callback: types.CallbackQuery, state: FSMContext):
    """Hamkorlik dasturi — banner rasm + caption + tugmalar."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌐 Ariza qoldirish — veb sayt",
            url="https://sugurta-bot-f2005e8f6915.herokuapp.com/#partner",
        )],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
    ])
    caption = (
        "🤝 <b>HAMKORLIK DASTURI</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Har bir jalb qilgan mijozingizdan <b>keshbek</b> oling:\n\n"
        "<blockquote>"
        "🌍 Viloyatlar — <b>27%</b> gacha keshbek\n"
        "🏙 Toshkent   — <b>7%</b> gacha keshbek"
        "</blockquote>\n\n"
        "⚡ Keshbek <b>10 daqiqada</b> kartangizga qaytadi\n"
        "📦 Reklama materiallari — pochta orqali (2 000 so'm)\n"
        "👤 Shaxsiy menejer — istalgan savolga tez javob\n\n"
        "💡 <i>Minimal 7% · Maksimal 27%</i>\n\n"
        "👇 Ariza qoldirish uchun:"
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    photo_id = await get_config("partner_photo")
    if photo_id:
        try:
            await callback.message.answer_photo(
                photo=photo_id,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
            await callback.answer()
            return
        except Exception as e:
            logger.warning(f"partner_info photo send failed: {e}")

    # Fallback — foto yo'q bo'lsa matn bilan
    await callback.message.answer(caption, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "reminder_start")
async def reminder_start(callback: types.CallbackQuery, state: FSMContext):
    await show_reminder_menu(callback, state)


@router.message(Command("eslatma"), F.chat.type == "private")
async def reminder_command(message: types.Message, state: FSMContext):
    await show_reminder_menu(message, state)


# ─── /start dan keladigan: "Ha, sug'urta bor" ───────────────────────────────
@router.callback_query(F.data == "has_insurance_yes")
async def has_insurance_yes(callback: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi 'Ha, sug'urta bor' dedi — sana so'raymiz."""
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(ReminderState.expiry_date)
    await state.update_data(mode="active")
    await set_user_state_time(callback.from_user.id)
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🔔 Eslatma — sug'urta tugash sanasi kutilmoqda",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    sent = await callback.message.answer(
        "📅 <b>Sug'urtangiz qachon tugaydi?</b>\n\n"
        "<blockquote>Istalgan formatda yozing:\n\n"
        "• <b>15.06.2026</b> — aniq sana\n"
        "• <b>15 iyun 2026</b>\n"
        "• <b>3 oy</b> — bugundan 3 oy keyin\n"
        "• <b>45 kun</b></blockquote>",
        reply_markup=kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)
    await callback.answer()


# ─── /start dan keladigan: "Yo'q, yangi kerak" ──────────────────────────────
@router.callback_query(F.data == "has_insurance_no")
async def has_insurance_no(callback: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi 'Yo'q, yangi sug'urta kerak' dedi — bosh menyuni ko'rsatamiz."""
    from keyboards.inline import start_menu_inline
    from services.status_service import update_status
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🟢 Bosh menyu — yangi sug'urta tanlandi",
    )
    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"
    caption = (
        "<b>🛡 Avtomobil sug'urta — bir necha tugmada tayyor</b>\n\n"
        "<blockquote>"
        "⚡ <b>10 soniyada</b> narxni biling\n"
        "🎁 <b>20% gacha</b> bonusni qaytaramiz\n"
        "💳 <b>Uzum Nasiya</b> — 30 kun foizsiz\n"
        "📦 Uygacha yetkazib beramiz (<b>2,000 so'm</b>)"
        "</blockquote>\n\n"
        "👇 Quyidagi tugmalardan birini tanlang:"
    )
    try:
        await callback.message.answer_photo(
            photo=photo, caption=caption,
            reply_markup=start_menu_inline(), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            caption, reply_markup=start_menu_inline(), parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "reminder_active")
async def reminder_active(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(ReminderState.expiry_date)
    await state.update_data(mode="active")
    await set_user_state_time(callback.from_user.id)
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🔔 Eslatma — sug'urta tugash sanasi kutilmoqda",
    )

    await clear_prev_prompt(callback.bot, callback.message.chat.id, state)
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    sent = await callback.message.answer(
        "📅 <b>Sug'urtangiz qachon tugaydi?</b>\n\n"
        "<blockquote>Istalgan formatda yozing:\n\n"
        "• <b>15.06.2026</b> — aniq sana\n"
        "• <b>15 iyun 2026</b>\n"
        "• <b>3 oy</b> — bugundan 3 oy keyin\n"
        "• <b>45 kun</b></blockquote>",
        reply_markup=kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)
    await callback.answer()


@router.callback_query(F.data == "reminder_new")
async def reminder_new(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(ReminderState.expiry_date)
    await state.update_data(mode="new")
    await set_user_state_time(callback.from_user.id)
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🔔 Eslatma — yangi sug'urta tugash sanasi kutilmoqda",
    )

    await clear_prev_prompt(callback.bot, callback.message.chat.id, state)
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    sent = await callback.message.answer(
        "📅 <b>Yangi sug'urta qachon tugashini bilasizmi?</b>\n\n"
        "<blockquote>Istalgan formatda yozing:\n\n"
        "• <b>15.05.2027</b>\n• <b>15 may 2027</b>\n• <b>6 oy</b> (bugundan)\n• <b>1 yil</b></blockquote>",
        reply_markup=kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)
    await callback.answer()


@router.message(ReminderState.expiry_date, F.text)
async def receive_expiry_date(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) > 200:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Iltimos, qisqaroq yozing", reply_markup=kb)
        return

    kind, value = parse_smart_date(text)

    if kind == "days":
        await state.update_data(parsed_text=text, parsed_days=value)
        future_date = date.today() + timedelta(days=value)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Ha, {value} kundan keyin", callback_data="confirm_smart", style="success")],
            [InlineKeyboardButton(text="🔄 Yo'q, qayta yozaman", callback_data="retry_date")],
            cancel_button(),
        ])
        await message.answer(
            f"🤔 <b>Tushundim:</b>\n\n<blockquote>⏳ <b>{value} kun</b> qoldi\n"
            f"📅 Taxminiy tugash sanasi: <b>{future_date.strftime('%d.%m.%Y')}</b></blockquote>\n\nTo'g'rimi?",
            reply_markup=kb, parse_mode="HTML"
        )
    elif kind == "date":
        await state.update_data(parsed_text=text, parsed_date=value.isoformat())
        days_left = (value - date.today()).days
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Ha, {value.strftime('%d.%m.%Y')}", callback_data="confirm_smart", style="success")],
            [InlineKeyboardButton(text="🔄 Yo'q, qayta yozaman", callback_data="retry_date")],
            cancel_button(),
        ])
        await message.answer(
            f"🤔 <b>Tushundim:</b>\n\n<blockquote>📅 Tugash sanasi: <b>{value.strftime('%d.%m.%Y')}</b>\n"
            f"⏳ Bugungacha: <b>{days_left} kun</b></blockquote>\n\nTo'g'rimi?",
            reply_markup=kb, parse_mode="HTML"
        )
    else:
        await state.update_data(parsed_text=text, parsed_unclear=True)
        await send_unclear_to_admin(message, state, bot)


async def send_unclear_to_admin(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    topic_id = await ensure_topic(user_id, full_name, bot)

    sent = await bot.send_message(
        chat_id=GROUP_ID, message_thread_id=topic_id,
        text=(
            f"❓ <b>Mijoz tushunarsiz javob yubordi</b>\n━━━━━━━━━━━━━━━━━\n"
            f"👤 {full_name}\n💬 Yozgani: <i>«{message.text}»</i>\n━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ Operator: shu xabarga <u>reply</u> qilib aniq sanani yozing:\n<code>15.05.2027</code>"
        ),
        parse_mode="HTML"
    )

    reminder_id = await save_reminder(
        user_id=user_id, topic_id=topic_id, phone=None,
        expiry_date_text=message.text, remind_days=7,
    )
    if reminder_id:
        await attach_request_msg_id(reminder_id, sent.message_id)

    await message.answer(
        "🤔 <b>Sizni to'liq tushunmadim</b>\n\n"
        "<blockquote>Operatorimiz so'rovingizni qabul qildi va\ntez orada siz bilan bog'lanadi 🛡</blockquote>",
        parse_mode="HTML"
    )
    await state.clear()
    await clear_user_state_time(user_id)


@router.callback_query(F.data == "confirm_smart")
async def confirm_smart(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(ReminderState.phone)
    await set_user_state_time(callback.from_user.id)
    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="🔔 Eslatma — telefon kutilmoqda",
    )

    await clear_prev_prompt(callback.bot, callback.message.chat.id, state)
    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    sent = await callback.message.answer(
        "✅ Yaxshi!\n\n📞 Endi telefon raqamingizni yuboring:\n"
        "👇 Pastdagi tugma orqali 1 ta bosish bilan yoki qo'lda kiriting",
        reply_markup=kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)
    await callback.message.answer(
        "📱 <i>Tugmadan foydalaning</i>",
        reply_markup=phone_share_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "retry_date")
async def retry_date(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(ReminderState.expiry_date)
    await set_user_state_time(callback.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📅 Iltimos, sanani qayta yozing.\n\nAniq sana ko'rinishida yaxshiroq:\n<code>15.05.2027</code>",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.message(ReminderState.phone)
async def receive_phone(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return

    raw = message.contact.phone_number if message.contact else (message.text.strip() if message.text else "")
    phone = normalize_phone(raw)
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Telefon noto'g'ri\n\n+998901234567 yoki 901234567", reply_markup=kb)
        return

    await state.update_data(phone=phone)
    await state.set_state(ReminderState.remind_days)
    await set_user_state_time(message.from_user.id)

    # Reply keyboard'ni olib tashlaymiz
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())

    await clear_prev_prompt(message.bot, message.chat.id, state)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="3 kun oldin", callback_data="rem_days_3", style="success"),
            InlineKeyboardButton(text="2 kun oldin", callback_data="rem_days_2", style="success"),
            InlineKeyboardButton(text="1 kun oldin", callback_data="rem_days_1", style="success"),
        ],
        cancel_button(),
    ])
    sent = await message.answer(
        "✅ Telefon qabul qilindi\n\n⏰ <b>Necha kun oldin eslatib turaylik?</b>",
        reply_markup=kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)


@router.callback_query(ReminderState.remind_days, F.data.startswith("rem_days_"))
async def receive_remind_days(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    days = int(callback.data.split("_")[-1])
    data = await state.get_data()
    user_id = callback.from_user.id
    full_name = callback.from_user.full_name
    phone = data.get("phone")
    parsed_text = data.get("parsed_text", "—")
    mode = data.get("mode", "new")

    if "parsed_date" in data:
        expiry_date = date.fromisoformat(data["parsed_date"])
    elif "parsed_days" in data:
        expiry_date = date.today() + timedelta(days=data["parsed_days"])
    else:
        await callback.message.answer("⚠️ Xatolik. /eslatma orqali qayta boshlang")
        await state.clear()
        await clear_user_state_time(user_id)
        return

    topic_id = await ensure_topic(user_id, full_name, bot)

    from database.db import pool
    reminder_id = None
    if pool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO reminders
                    (user_id, topic_id, phone, expiry_date_text, expiry_date, remind_days, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'confirmed')
                    RETURNING id
                """, user_id, topic_id, phone, parsed_text, expiry_date, days)
                reminder_id = row["id"]
        except Exception as e:
            logger.error(f"Save confirmed reminder failed: {e}", exc_info=True)

    mode_label = "🛡 Eski sug'urta" if mode == "active" else "📅 Yangi sug'urta"
    notify_date = expiry_date - timedelta(days=days)

    await bot.send_message(
        chat_id=GROUP_ID, message_thread_id=topic_id,
        text=(
            f"🔔 <b>YANGI ESLATMA</b>\n━━━━━━━━━━━━━━━━━\n"
            f"👤 {full_name}\n📞 <code>{phone}</code>\n{mode_label}\n"
            f"💬 Mijoz yozgani: <i>«{parsed_text}»</i>\n━━━━━━━━━━━━━━━━━\n"
            f"📅 Tugash sanasi: <b>{expiry_date.strftime('%d.%m.%Y')}</b>\n"
            f"🔔 Eslatish sanasi: <b>{notify_date.strftime('%d.%m.%Y')}</b> ({days} kun oldin)\n"
            f"━━━━━━━━━━━━━━━━━\n#{reminder_id or '?'} · ✅ avto-tasdiqlangan"
        ),
        parse_mode="HTML"
    )

    kb_done = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Hozir sug'urtalash", callback_data="start_insurance", style="success")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")],
    ])
    await callback.message.answer(
        f"✅ <b>Eslatma faollashtirildi!</b>\n\n"
        f"<blockquote>📅 Tugash: {expiry_date.strftime('%d.%m.%Y')}\n"
        f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}</blockquote>\n\n"
        "🎁 <i>Hozir rasmiylashtirsangiz — 20% gacha bonus oling</i>",
        reply_markup=kb_done, parse_mode="HTML"
    )
    await update_status(
        bot=bot, user_id=user_id, full_name=full_name,
        stage="✅ Eslatma faollashtirildi",
        details=(
            f"📞 {phone}\n"
            f"📅 Tugash: {expiry_date.strftime('%d.%m.%Y')}\n"
            f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}"
        ),
    )
    await reset_status(user_id)
    await state.clear()
    await clear_user_state_time(user_id)
    await callback.answer()


DATE_PATTERN = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b")


@router.message(
    F.chat.id == GROUP_ID,
    F.reply_to_message,
    F.text.regexp(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\b")
)
async def confirm_via_reply(message: types.Message, bot: Bot):
    if not message.text:
        return
    match = DATE_PATTERN.search(message.text)
    if not match:
        return
    day, month, year = map(int, match.groups())
    try:
        expiry_date = date(year, month, day)
    except ValueError:
        return
    reply_msg_id = message.reply_to_message.message_id
    confirmed = await confirm_reminder_by_msg(reply_msg_id, expiry_date) if expiry_date > date.today() else None

    if not confirmed:
        topic_id = message.message_thread_id
        if topic_id and not (message.from_user and message.from_user.is_bot):
            user_id = await get_user(topic_id)
            if user_id:
                try:
                    await message.bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=GROUP_ID,
                        message_id=message.message_id,
                    )
                except Exception as e:
                    logger.error(f"forward date reply failed: {e}", exc_info=True)
        if expiry_date <= date.today():
            await message.reply("❌ Sana o'tib ketgan")
        return

    days_until = (expiry_date - date.today()).days
    notify_days = confirmed["remind_days"] or 7
    notify_date = expiry_date - timedelta(days=notify_days)

    await message.reply(
        f"✅ <b>Tasdiqlandi</b>\n📅 {expiry_date.strftime('%d.%m.%Y')} · ⏳ {days_until} kun\n"
        f"🔔 {notify_date.strftime('%d.%m.%Y')} ({notify_days} kun oldin)",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            chat_id=confirmed["user_id"],
            text=(
                f"✅ <b>Eslatma faollashtirildi!</b>\n\n"
                f"<blockquote>📅 Tugash: {expiry_date.strftime('%d.%m.%Y')}\n"
                f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}</blockquote>\n\n"
                "Belgilangan kuni xabar yuboramiz 🛡"
            ),
            parse_mode="HTML"
        )
    except Exception:
        logger.error("notify_user_confirm_failed", exc_info=True)


@router.callback_query(F.data.startswith("notify_user_"))
async def notify_user_now(callback: types.CallbackQuery, bot: Bot):
    reminder_id = int(callback.data.split("_")[-1])
    rem = await get_reminder(reminder_id)
    if not rem:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return

    days_left = (rem["expiry_date"] - date.today()).days
    text = (
        f"🔔 <b>SUG'URTA ESLATMASI</b>\n\n"
        f"<blockquote>📅 Sug'urtangiz <b>{days_left} kundan keyin</b> tugaydi\n"
        f"🗓 Tugash sanasi: {rem['expiry_date'].strftime('%d.%m.%Y')}</blockquote>\n\n"
        f"⚠️ Muddati o'tib ketmasidan oldin yangilashni unutmang!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Sug'urtani yangilash", callback_data="start_insurance", style="success")]])

    try:
        await bot.send_message(chat_id=rem["user_id"], text=text, reply_markup=kb, parse_mode="HTML")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.reply(f"✅ Mijozga eslatma yuborildi · {datetime.now().strftime('%H:%M')}")
        await callback.answer("Yuborildi")
    except TelegramForbiddenError:
        if rem.get("topic_id"):
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=rem["topic_id"],
                text=(
                    "🚫 <b>Mijoz botni bloklagan!</b>\n"
                    "Bot unga xabar yubora olmaydi.\n"
                    "📞 Telefon raqami orqali bog'laning."
                ),
                parse_mode="HTML",
            )
        await callback.answer("🚫 Mijoz botni bloklagan", show_alert=True)
    except Exception as e:
        logger.error(f"notify_user_now failed: {e}", exc_info=True)
        await callback.answer("❌ Yuborib bo'lmadi", show_alert=True)