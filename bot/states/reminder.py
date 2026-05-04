"""
Eslatma servisi.

Flow:
1. Foydalanuvchi "🔔 Eslatma so'rash" tugmasini bosadi (3 joydan)
2. Bot sug'urta tugash sanasini so'raydi (matn)
3. Bot telefon raqam so'raydi
4. Bot eslatish kunlarini so'raydi (3/2/1)
5. Ma'lumot foydalanuvchining shaxsiy topic'iga yuboriladi
6. Operator topic'ga reply qilib aniq sanani DD.MM.YYYY formatda yozadi
7. Bot sanani saqlaydi va belgilangan kuni avtomatik eslatma yuboradi
"""

import logging
import re
from datetime import datetime, date

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
from config import GROUP_ID

logger = logging.getLogger(__name__)
router = Router(name="reminder")


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. ESLATMA BOSHLASH (3 joydan kiriladi)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reminder_start")
async def reminder_start(callback: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi "Eslatma" tugmasini bosdi."""
    await state.clear()
    await state.set_state(ReminderState.expiry_date)

    await callback.message.answer(
        "🔔 <b>Sug'urta tugash sanasini eslab qolaylik!</b>\n\n"
        "<blockquote>Sug'urtangiz qachon tugaydi?</blockquote>\n\n"
        "📅 Sanani istalgan formatda yozing\n\n"
        "Misollar:\n"
        "• 15 may 2027\n"
        "• 15.05.2027\n"
        "• keyingi yil mart\n"
        "• 6 oydan keyin\n\n"
        "/cancel — bekor qilish",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("eslatma"), F.chat.type == "private")
async def reminder_command(message: types.Message, state: FSMContext):
    """Foydalanuvchi shaxsiy chat'da /eslatma yozdi."""
    await state.clear()
    await state.set_state(ReminderState.expiry_date)
    await message.answer(
        "🔔 <b>Sug'urta tugash sanasini eslab qolaylik!</b>\n\n"
        "📅 Sug'urtangiz qachon tugaydi?\n"
        "Istalgan formatda yozing (masalan: 15 may 2027)\n\n"
        "/cancel — bekor qilish",
        parse_mode="HTML"
    )


# Topic ichida operator /eslatma yozsa — mijozga taklif yuboradi
@router.message(Command("eslatma"), F.chat.id == GROUP_ID)
async def reminder_offer_from_topic(message: types.Message, bot: Bot):
    """Operator topic'da /eslatma yozdi — mijozga taklif yuboradi."""
    topic_id = message.message_thread_id
    if not topic_id:
        await message.reply("❌ Bu buyruq faqat topic ichida ishlaydi")
        return

    from database.db import get_user
    user_id = await get_user(topic_id)
    if not user_id:
        await message.reply("❌ Mijoz topilmadi")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔔 Ha, eslatib turing",
                callback_data="reminder_start"
            )],
            [InlineKeyboardButton(
                text="❌ Kerak emas",
                callback_data="reminder_decline"
            )]
        ]
    )

    await bot.send_message(
        chat_id=user_id,
        text=(
            "🔔 <b>Sug'urta eslatma servisi</b>\n\n"
            "<blockquote>"
            "Sug'urta tugashidan oldin sizga eslatib turamiz, "
            "muddati o'tib ketmasin 🛡"
            "</blockquote>\n\n"
            "Xizmatdan foydalanasizmi?"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )

    await message.answer("✅ Mijozga eslatma taklifi yuborildi")
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "reminder_decline")
async def reminder_decline(callback: types.CallbackQuery):
    await callback.message.answer(
        "Yaxshi, kerak bo'lsa istalgan vaqt /eslatma orqali yozing 👌"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 2. SANA QABUL QILISH
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ReminderState.expiry_date, F.text)
async def receive_expiry_date(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text.startswith("/"):
        return  # command'larni o'tkazib yuboramiz

    if len(text) < 3 or len(text) > 100:
        await message.answer("❗ Iltimos, sanani aniqroq yozing")
        return

    await state.update_data(expiry_date_text=text)
    await state.set_state(ReminderState.phone)

    await message.answer(
        "✅ Sana qabul qilindi\n\n"
        "📞 Endi telefon raqamingizni yuboring:\n"
        "<code>+998XXXXXXXXX</code>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. TELEFON QABUL QILISH
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ReminderState.phone, F.text)
async def receive_phone(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer(
            "❗ Telefon noto'g'ri\n\n"
            "To'g'ri formatlar:\n"
            "+998901234567\n"
            "901234567"
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
            ]
        ]
    )

    await message.answer(
        "✅ Telefon qabul qilindi\n\n"
        "⏰ <b>Necha kun oldin eslatib turaylik?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. ESLATISH KUNI TANLASH VA TOPIC'GA YUBORISH
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
    expiry_text = data.get("expiry_date_text", "—")
    phone = data.get("phone", "—")

    # Topic'ni olib kelamiz / yaratamiz
    topic_id = await get_topic(user_id)
    if not topic_id:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=f"{full_name} | {user_id}"
        )
        topic_id = topic.message_thread_id
        await save_user(user_id, topic_id)

    # DB'ga eslatmani saqlash (pending)
    reminder_id = await save_reminder(
        user_id=user_id,
        topic_id=topic_id,
        phone=phone,
        expiry_date_text=expiry_text,
        remind_days=days,
    )

    # Topic'ga yuborish — operator shu xabarga reply qilib aniq sana yozadi
    summary = (
        f"🔔 <b>YANGI ESLATMA SO'ROVI</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"📅 <b>Mijoz yozgan sana:</b> <i>{expiry_text}</i>\n"
        f"⏰ <b>Eslatish:</b> {days} kun oldin\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"#{reminder_id}\n\n"
        f"⚠️ <b>Operator:</b> shu xabarga <u>reply</u> qilib aniq sanani yozing:\n"
        f"<code>15.05.2027</code> ko'rinishida"
    )

    sent = await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=topic_id,
        text=summary,
        parse_mode="HTML"
    )

    # Reply uchun message_id ni saqlaymiz
    await attach_request_msg_id(reminder_id, sent.message_id)

    # Foydalanuvchiga tasdiq
    await callback.message.answer(
        "✅ <b>So'rovingiz qabul qilindi!</b>\n\n"
        "<blockquote>"
        f"📅 Sana: {expiry_text}\n"
        f"⏰ Eslatish: {days} kun oldin"
        "</blockquote>\n\n"
        "Operator sanani aniqlab tasdiqlaydi va belgilangan kuni\n"
        "sizga eslatib turamiz 🛡",
        parse_mode="HTML"
    )

    await state.clear()
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 5. OPERATOR TASDIQ — reply orqali sana yozadi
# ─────────────────────────────────────────────────────────────────────────────

DATE_PATTERN = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b")


@router.message(F.chat.id == GROUP_ID, F.reply_to_message)
async def confirm_via_reply(message: types.Message, bot: Bot):
    """Operator topic'da so'rovga reply qilib sanani yozadi."""
    if not message.text:
        return

    match = DATE_PATTERN.search(message.text)
    if not match:
        return  # bu reply, lekin sana emas — ehtimol oddiy javob, e'tibor bermaymiz

    day, month, year = map(int, match.groups())
    try:
        expiry_date = date(year, month, day)
    except ValueError:
        await message.reply("❌ Sana noto'g'ri")
        return

    if expiry_date <= date.today():
        await message.reply("❌ Sana o'tib ketgan, kelajakdagi sanani kiriting")
        return

    # Reply qilingan xabar ID si bo'yicha eslatmani topamiz
    reply_msg_id = message.reply_to_message.message_id
    confirmed = await confirm_reminder_by_msg(reply_msg_id, expiry_date)

    if not confirmed:
        return  # bu reply boshqa xabarga, e'tibor bermaymiz

    # Tasdiq xabarini chiqaramiz
    days_until = (expiry_date - date.today()).days
    notify_days = confirmed["remind_days"]
    notify_date = expiry_date - __import__("datetime").timedelta(days=notify_days)

    await message.reply(
        f"✅ <b>Tasdiqlandi</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📅 Tugash sanasi: <b>{expiry_date.strftime('%d.%m.%Y')}</b>\n"
        f"⏳ Bugungacha: <b>{days_until} kun</b>\n"
        f"🔔 Eslatish: <b>{notify_date.strftime('%d.%m.%Y')}</b> ({notify_days} kun oldin)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"#{confirmed['id']}",
        parse_mode="HTML"
    )

    # Mijozga tasdiq
    try:
        await bot.send_message(
            chat_id=confirmed["user_id"],
            text=(
                "✅ <b>Eslatma faollashtirildi!</b>\n\n"
                f"<blockquote>"
                f"📅 Tugash sanasi: {expiry_date.strftime('%d.%m.%Y')}\n"
                f"🔔 Eslatamiz: {notify_date.strftime('%d.%m.%Y')}\n"
                f"</blockquote>\n\n"
                "Belgilangan kuni sizga xabar yuboramiz 🛡"
            ),
            parse_mode="HTML"
        )
    except Exception:
        logger.error("notify_user_confirm_failed", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6. AVTOMATIK ESLATMA — operator tugmasi orqali jo'natish
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("notify_user_"))
async def notify_user_now(callback: types.CallbackQuery, bot: Bot):
    """Operator general'dagi tugmani bosdi — mijozga eslatma yuboriladi."""
    reminder_id = int(callback.data.split("_")[-1])
    rem = await get_reminder(reminder_id)
    if not rem:
        await callback.answer("❌ Eslatma topilmadi", show_alert=True)
        return

    days_left = (rem["expiry_date"] - date.today()).days

    text = (
        f"🔔 <b>SUG'URTA ESLATMASI</b>\n\n"
        f"<blockquote>"
        f"📅 Sug'urtangiz <b>{days_left} kundan keyin</b> tugaydi\n"
        f"🗓 Tugash sanasi: {rem['expiry_date'].strftime('%d.%m.%Y')}"
        f"</blockquote>\n\n"
        f"⚠️ Muddati o'tib ketmasidan oldin yangilashni unutmang!\n\n"
        f"👇 Yangilash uchun bosing"
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
        # Tugmani o'chirib, "Yuborildi" yozamiz
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(
            f"✅ Mijozga eslatma yuborildi · {datetime.now().strftime('%H:%M')}"
        )
        await callback.answer("Yuborildi")
    except Exception as e:
        logger.error(f"notify_user_now failed: {e}", exc_info=True)
        await callback.answer("❌ Yuborib bo'lmadi", show_alert=True)