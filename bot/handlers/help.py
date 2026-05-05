"""
Yordam servisi.

Variantlar:
1. 📞 Operator chaqirish — telefon qoldiriladi, operator qo'ng'iroq qiladi
2. 💬 Savol yozish — matn/rasm/voice yuboriladi adminga
3. 🔙 Bosh menyu

Hech qanday yangi topic ochilmaydi — har xabar mijozning shaxsiy topic'iga boradi.
"""

import logging
import re
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_topic, save_user
from handlers.cancel import cancel_button
from config import GROUP_ID

logger = logging.getLogger(__name__)
router = Router(name="help")


class HelpState(StatesGroup):
    waiting_phone = State()
    waiting_question = State()


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. YORDAM MENYU
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help_mode")
async def help_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📞 Operator qo'ng'iroq qilsin",
                callback_data="help_call"
            )],
            [InlineKeyboardButton(
                text="💬 Savol yozish",
                callback_data="help_write"
            )],
            [InlineKeyboardButton(
                text="🏠 Bosh menyu",
                callback_data="go_main_menu"
            )]
        ]
    )

    await callback.message.answer_photo(
        photo="AgACAgIAAyEFAASY9hCdAAID_Wn3ikpf-SSsxEH3MFlAs0RGVWa8AAKQF2sb8a3AS-nPdtz6uB2oAQADAgADeQADOwQ",
        caption=(
            "<b>❓ Sizga qanday yordam beraylik?</b>\n\n"
            "<blockquote>"
            "📞 <b>Operator qo'ng'iroq qilsin</b> — raqam qoldiring,\n"
            "tez orada bog'lanamiz\n\n"
            "💬 <b>Savol yozish</b> — savolingizni yozing,\n"
            "operator topic'da javob beradi"
            "</blockquote>\n\n"
            "Tanlang 👇"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 2. OPERATOR CHAQIRISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help_call")
async def help_call(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    full_name = callback.from_user.full_name

    topic_id = await get_topic(user_id)
    if not topic_id:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=f"{full_name} | {user_id}"
        )
        topic_id = topic.message_thread_id
        await save_user(user_id, topic_id)

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=(
                f"📞 <b>Mijoz operator chaqirdi</b>\n"
                f"━━━━━━━━━━━━━\n"
                f"👤 {full_name}\n"
                f"⏳ Telefon raqami kutilmoqda..."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"help_call topic notify failed: {e}", exc_info=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📞 <b>Telefon raqamingizni qoldiring</b>\n\n"
        "<blockquote>"
        "Operatorimiz tez orada qo'ng'iroq qiladi"
        "</blockquote>\n\n"
        "<code>+998901234567</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await state.set_state(HelpState.waiting_phone)
    await callback.answer()


@router.message(HelpState.waiting_phone)
async def receive_help_phone(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return

    phone = normalize_phone(message.text.strip() if message.text else "")
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer(
            "❗ Telefon noto'g'ri\n\n"
            "+998901234567 yoki 901234567",
            reply_markup=kb
        )
        return

    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        try:
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=(
                    f"📞 <b>QO'NG'IROQ SO'ROVI</b>\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📞 <code>{phone}</code>\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"⚠️ Operator: tez orada qo'ng'iroq qiling"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"help phone notify failed: {e}", exc_info=True)

    kb_done = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ]
    )

    await message.answer(
        "✅ <b>Telefon raqami qabul qilindi!</b>\n\n"
        "<blockquote>"
        f"📞 <code>{phone}</code>\n\n"
        "Operator tez orada siz bilan bog'lanadi"
        "</blockquote>",
        reply_markup=kb_done,
        parse_mode="HTML"
    )
    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 3. SAVOL YOZISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help_write")
async def help_write(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    full_name = callback.from_user.full_name

    topic_id = await get_topic(user_id)
    if not topic_id:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=f"{full_name} | {user_id}"
        )
        topic_id = topic.message_thread_id
        await save_user(user_id, topic_id)

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=(
                f"💬 <b>Mijoz savol yozmoqchi</b>\n"
                f"━━━━━━━━━━━━━\n"
                f"👤 {full_name}\n"
                f"⏳ Savol kutilmoqda..."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"help_write topic notify failed: {e}", exc_info=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "💬 <b>Savolingizni yozing</b>\n\n"
        "<blockquote>"
        "Matn, rasm, ovozli xabar yoki fayl —\n"
        "istalgan ko'rinishda yuborishingiz mumkin"
        "</blockquote>\n\n"
        "Operator topic'da javob beradi 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await state.set_state(HelpState.waiting_question)
    await callback.answer()


@router.message(HelpState.waiting_question)
async def receive_question(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return

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

    try:
        # 1. "Yangi savol" belgisi
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=f"💬 <b>YANGI SAVOL</b>\n👤 {full_name}",
            parse_mode="HTML"
        )

        # 2. Mijoz xabarini ko'chirish (matn/rasm/voice/fayl — har xil)
        await bot.copy_message(
            chat_id=GROUP_ID,
            from_chat_id=user_id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
    except Exception as e:
        logger.error(f"help question forward failed: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi, qayta urinib ko'ring")
        return

    kb_done = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ]
    )

    await message.answer(
        "✅ <b>Savolingiz qabul qilindi!</b>\n\n"
        "<blockquote>"
        "Operator tez orada javob beradi"
        "</blockquote>",
        reply_markup=kb_done,
        parse_mode="HTML"
    )
    await state.clear()