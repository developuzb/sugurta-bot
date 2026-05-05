"""
Eslatma servisi (Smart parsing + Cancel everywhere).

Flow:
1. Eslatma menyu (rasm + 2 variant)
2. Sana so'rash (smart parser)
3. Tasdiqlash (✅ Ha / 🔄 Yo'q)
4. Telefon
5. Eslatish kunlari (3/2/1)
6. Topic'ga yuborish

Har bosqichda ❌ Bekor qilish tugmasi mavjud.
"""

import logging
import re
from datetime import datetime, date, timedelta

from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.reminder import ReminderState
from database.db import (
    get_topic,
    save_user,
    save_reminder,
    attach_request_msg_id,
    confirm_reminder_by_msg,
    get_reminder,
)
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


# ─────────────────────────────────────────────────────────────────────────────
# 1. ESLATMA MENYU
# ─────────────────────────────────────────────────────────────────────────────

async def show_reminder_menu(message_or_callback, state: FSMContext):
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🛡 Sug'urtam muddati hozircha tugamagan",
                callback_data="reminder_active"
            )],
            [InlineKeyboardButton(
                text="📅 Yangi sug'urta uchun eslatma",
                callback_data="reminder_new"
            )],
            cancel_button(),
        ]
    )

    caption = (
        "🔔 <b>Sug'urta tugashidan oldin eslatib turaylik</b>\n\n"
        "<blockquote>Sizga qaysi variant mos keladi?</blockquote>"
    )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer_photo(
            photo=REMINDER_PHOTO, caption=caption, reply_markup=kb, parse_mode="HTML"
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer_photo(
            photo=REMINDER_PHOTO, caption=caption, reply_markup=kb, parse_mode="HTML"
        )


@router.callback_query(F.data == "reminder_start")
async def reminder_start(callback: types.CallbackQuery, state: FSMContext):
    await show_reminder_menu(callback, state)


@router.message(Command("eslatma"), F.chat.type == "private")
async def reminder_command(message: types.Message, state: FSMContext):
    await show_reminder_menu(message, state)


# ─────────────────────────────────────────────────────────────────────────────
# 2. VARIANT TANLASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reminder_active")
async def reminder_active(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.set_state(ReminderState.expiry_date)
    await state.update_data(mode="active")

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])

    await callback.message.answer(
        "⏳ <b>Eski sug'urtangizdan necha kun qoldi?</b>\n\n"
        "<blockquote>"
        "Istalgan formatda yozing:\n\n"
        "• <b>20</b> yoki <b>20 kun</b>\n"
        "• <b>2 hafta</b>\n"
        "• <b>1 oy</b>\n"
        "• <b>15.05.2027</b>\n"
        "• <b>15 may 2027</b>"
        "</blockquote>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "reminder_new")
async def reminder_new(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.set_state(ReminderState.expiry_date)
    await state.update_data(mode="new")

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])

    await callback.message.answer(
        "📅 <b>Sug'urtangiz qachon tugashini bilasizmi?</b>\n\n"
        "<blockquote>"
        "Istalgan formatda yozing:\n\n"
        "• <b>15.05.2027</b>\n"
        "• <b>15 may 2027</b>\n"
        "• <b>6 oy</b> (bugundan)\n"
        "• <b>1 yil</b>"
        "</blockquote>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 3. SANA QABUL QILISH — SMART PARSING
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ReminderState.expiry_date, F.text)
async def receive_expiry_date(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    if text.startswith("/"):
        return  # /cancel /menu kabi command'larni boshqa router qabul qiladi

    if len(text) > 200:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer("❗ Iltimos, qisqaroq yozing", reply_markup=kb)
        return

    kind, value = parse_smart_date(text)

    if kind == "days":
        await state.update_data(parsed_text=text, parsed_days=value)
        future_date = date.today() + timedelta(days=value)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ Ha, {value} kundan keyin",
                    callback_data="confirm_smart"
                )],
                [InlineKeyboardButton(
                    text="🔄 Yo'q, qayta yozaman",
                    callback_data="retry_date"
                )],
                cancel_button(),
            ]
        )
        await message.answer(
            f"🤔 <b>Tushundim:</b>\n\n"
            f"<blockquote>"
            f"⏳ <b>{value} kun</b> qoldi\n"
            f"📅 Taxminiy tugash sanasi: <b>{future_date.strftime('%d.%m.%Y')}</b>"
            f"</blockquote>\n\nTo'g'rimi?",
            reply_markup=kb,
            parse_mode="HTML"
        )

    elif kind == "date":
        await state.update_data(parsed_text=text, parsed_date=value.isoformat())
        days_left = (value - date.today()).days

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ Ha, {value.strftime('%d.%m.%Y')}",
                    callback_data="confirm_smart"
                )],
                [InlineKeyboardButton(
                    text="🔄 Yo'q, qayta yozaman",
                    callback_data="retry_date"
                )],
                cancel_button(),
            ]
        )
        await message.answer(
            f"🤔 <b>Tushundim:</b>\n\n"
            f"<blockquote>"
            f"📅 Tugash sanasi: <b>{value.strftime('%d.%m.%Y')}</b>\n"
            f"⏳ Bugungacha: <b>{days_left} kun</b>"
            f"</blockquote>\n\nTo'g'rimi?",
            reply_markup=kb,
            parse_mode="HTML"
        )

    else:
        await state.update_data(parsed_text=text, parsed_unclear=True)
        await send_unclear_to_admin(message, state, bot)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TUSHUNARSIZ → ADMIN TASDIG'I
# ─────────────────────────────────────────────────────────────────────────────

async def send_unclear_to_admin(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    topic_id = await get_topic(user_id)
    if not topic_id:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=f"{full_name} | {user_id}"
        )
        topic_id = topic.message_thread_id
        await save_user(user_id, topic_id)

    text = (
        f"❓ <b>Mijoz tushunarsiz javob yubordi</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 {full_name}\n"
        f"💬 Yozgani: <i>«{message.text}»</i>\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ Operator: shu xabarga <u>reply</u> qilib aniq sanani yozing:\n"
        f"<code>15.05.2027</code>"
    )

    sent = await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=topic_id,
        text=text,
        parse_mode="HTML"
    )

    reminder_id = await save_reminder(
        user_id=user_id,
        topic_id=topic_id,
        phone=None,
        expiry_date_text=message.text,
        remind_days=7,
    )
    if reminder_id:
        await attach_request_msg_id(reminder_id, sent.message_id)

    await message.answer(
        "🤔 <b>Sizni to'liq tushunmadim</b>\n\n"
        "<blockquote>"
        "Operatorimiz so'rovingizni qabul qildi va\n"
        "tez orada siz bilan bog'lanadi 🛡"
        "</blockquote>",
        parse_mode="HTML"
    )

    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 5. SMART TASDIQ
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "confirm_smart")
async def confirm_smart(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.set_state(ReminderState.phone)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "✅ Yaxshi!\n\n"
        "📞 Endi telefon raqamingizni yuboring:\n"
        "<code>+998XXXXXXXXX</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "retry_date")
async def retry_date(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.set_state(ReminderState.expiry_date)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📅 Iltimos, sanani qayta yozing.\n\n"
        "Aniq sana ko'rinishida yaxshiroq:\n"
        "<code>15.05.2027</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 6. TELEFON QABUL QILISH
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ReminderState.phone, F.text)
async def receive_phone(message: types.Message, state: FSMContext):
    if message.text.startswith("/"):
        return

    phone = normalize_phone(message.text.strip())
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer(
            "❗ Telefon noto'g'ri\n\n"
            "+998901234567 yoki 901234567",
            reply_markup=kb
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(ReminderState.remind_days)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3 kun oldin", callback_data="rem_days_3"),
                InlineKeyboardButton(text="2 kun oldin", callback_data="rem_days_2"),
                InlineKeyboardButton(text="1 kun oldin", callback_data="rem_days_1"),
            ],
            cancel_button(),
        ]
    )

    await message.answer(
        "✅ Telefon qabul qilindi\n\n"
        "⏰ <b>Necha kun oldin eslatib turaylik?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. KUN TANLASH → DB SAQLASH
# ─────────────────────────────────────────────────────────────────────────────

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
        return

    topic_id = await get_topic(user_id)
    if not topic_id:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=f"{full_name} | {user_id}"
        )
        topic_id = topic.message_thread_id
        await save_user(user_id, topic_id)

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

    summary = (
        f"🔔 <b>YANGI ESLATMA</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 {full_name}\n"
        f"📞 <code>{phone}</code>\n"
        f"{mode_label}\n"
        f"💬 Mijoz yozgani: <i>«{parsed_text}»</i>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📅 Tugash sanasi: <b>{expiry_date.strftime('%d.%m.%Y')}</b>\n"
        f"🔔 Eslatish sanasi: <b>{notify_date.strftime('%d.%m.%Y')}</b> ({days} kun oldin)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"#{reminder_id or '?'} · ✅ avto-tasdiqlangan"
    )

    await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=topic_id,
        text=summary,
        parse_mode="HTML"
    )

    kb_done = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ]
    )

    await callback.message.answer(
        "✅ <b>Eslatma faollashtirildi!</b>\n\n"
        f"<blockquote>"
        f"📅 Tugash: {expiry_date.strftime('%d.%m.%Y')}\n"
        f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}"
        f"</blockquote>\n\n"
        "Belgilangan kuni sizga xabar yuboramiz 🛡",
        reply_markup=kb_done,
        parse_mode="HTML"
    )

    await state.clear()
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 8. OPERATOR TASDIQ — REPLY ORQALI (sana topilgandagina)
# ─────────────────────────────────────────────────────────────────────────────

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

    if expiry_date <= date.today():
        await message.reply("❌ Sana o'tib ketgan")
        return

    reply_msg_id = message.reply_to_message.message_id
    confirmed = await confirm_reminder_by_msg(reply_msg_id, expiry_date)
    if not confirmed:
        return

    days_until = (expiry_date - date.today()).days
    notify_days = confirmed["remind_days"] or 7
    notify_date = expiry_date - timedelta(days=notify_days)

    await message.reply(
        f"✅ <b>Tasdiqlandi</b>\n"
        f"📅 {expiry_date.strftime('%d.%m.%Y')} · ⏳ {days_until} kun\n"
        f"🔔 {notify_date.strftime('%d.%m.%Y')} ({notify_days} kun oldin)",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            chat_id=confirmed["user_id"],
            text=(
                "✅ <b>Eslatma faollashtirildi!</b>\n\n"
                f"<blockquote>"
                f"📅 Tugash: {expiry_date.strftime('%d.%m.%Y')}\n"
                f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}"
                f"</blockquote>\n\n"
                "Belgilangan kuni xabar yuboramiz 🛡"
            ),
            parse_mode="HTML"
        )
    except Exception:
        logger.error("notify_user_confirm_failed", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# 9. AVTOMATIK ESLATMA TUGMASI
# ─────────────────────────────────────────────────────────────────────────────

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
        f"<blockquote>"
        f"📅 Sug'urtangiz <b>{days_left} kundan keyin</b> tugaydi\n"
        f"🗓 Tugash sanasi: {rem['expiry_date'].strftime('%d.%m.%Y')}"
        f"</blockquote>\n\n"
        f"⚠️ Muddati o'tib ketmasidan oldin yangilashni unutmang!"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Sug'urtani yangilash",
                callback_data="start_insurance"
            )]
        ]
    )

    try:
        await bot.send_message(
            chat_id=rem["user_id"],
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.reply(
            f"✅ Mijozga eslatma yuborildi · {datetime.now().strftime('%H:%M')}"
        )
        await callback.answer("Yuborildi")
    except Exception as e:
        logger.error(f"notify_user_now failed: {e}", exc_info=True)
        await callback.answer("❌ Yuborib bo'lmadi", show_alert=True)