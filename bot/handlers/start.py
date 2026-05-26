import logging

from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.inline import start_menu_inline

from services.topic_service import ensure_topic
from services.status_service import update_status, reset_status
from database.db import clear_user_state_time, get_web_lead, link_web_lead

logger = logging.getLogger(__name__)
router = Router()

_VN = {"yengil": "🚗 Yengil", "yuk": "🚚 Yuk", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}
_TN = {"limited": "Oddiy", "unlimited": "👑 VIP"}
_DN = {"dur_12": "🛡 1 yil", "dur_6": "📅 6 oy", "dur_20": "⚡ 20 kun"}


@router.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message, state: FSMContext, command: CommandObject):
    await state.clear()
    await clear_user_state_time(message.from_user.id)

    user_id   = message.from_user.id
    full_name = message.from_user.full_name

    # Topic yaratish (har doim)
    await ensure_topic(user_id, full_name, message.bot)

    # ─── Web Lead orqali kelgan mijoz ───────────────────────────────────────
    args = (command.args or "").strip()
    if args.startswith("wl_"):
        lead = await get_web_lead(args)
        if lead:
            await link_web_lead(args, user_id)

            name     = lead["name"] or "Hurmatli mijoz"
            phone    = lead["phone"] or "—"
            vehicle  = _VN.get(lead["vehicle"], lead["vehicle"] or "—")
            region   = lead["region_label"] or "—"
            itype    = _TN.get(lead["insurance_type"], lead["insurance_type"] or "—")
            duration = _DN.get(lead["duration"], lead["duration"] or "—")
            price    = lead["price"] or 0
            bonus    = lead["bonus"] or 0

            # ① Mijozga: ariza qabul qilindi, operator bog'lanadi
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="go_main_menu")],
            ])
            await message.answer(
                f"✅ <b>Arizangiz qabul qilindi, {name}!</b>\n\n"
                f"<blockquote>"
                f"{vehicle}  ·  📍 {region}\n"
                f"{itype}  ·  {duration}\n"
                f"💰 <b>{price:,} so'm</b>   🎁 +{bonus:,} so'm bonus"
                f"</blockquote>\n\n"
                f"👨‍💼 <b>Operatorimiz tez orada siz bilan bog'lanadi.</b>\n\n"
                f"⏳ Odatda <b>5–15 daqiqa</b> ichida qo'ng'iroq qilamiz.\n"
                f"Shu orada bu yerda operatorga savolingizni yo'llashingiz mumkin.",
                reply_markup=kb,
                parse_mode="HTML",
            )

            # ② Operator topic'iga: yangi ulangan mijoz bildirishnomasi
            from database.db import get_topic
            topic_id = await get_topic(user_id)
            if topic_id:
                from config import GROUP_ID
                try:
                    await message.bot.send_message(
                        chat_id=GROUP_ID,
                        message_thread_id=topic_id,
                        text=(
                            f"🔔 <b>MIJOZ TELEGRAM'GA ULANDI</b>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"👤 {name}\n"
                            f"📞 <code>{phone}</code>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"{vehicle}  ·  📍 {region}\n"
                            f"{itype}  ·  {duration}\n"
                            f"💰 <b>{price:,} so'm</b>   🎁 +{bonus:,} so'm\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"💬 Shu topic orqali yozing — mijozga yetadi"
                        ),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(f"web_lead topic notify error: {e}", exc_info=True)

            await update_status(
                bot=message.bot, user_id=user_id, full_name=full_name,
                stage="🌐 Websaytdan Telegram'ga o'tdi — kutmoqda",
                details=f"📞 {phone} | {vehicle} | {price:,} so'm",
            )
            return  # Oddiy /start ni ko'rsatmaymiz

    # ─── Oddiy /start — avval sug'urta holati aniqlanadi ────────────────────
    await reset_status(user_id)
    await update_status(
        bot=message.bot,
        user_id=user_id,
        full_name=full_name,
        stage="🟢 Bot ochildi — sug'urta holati so'ralmoqda",
        details=f"👤 {full_name}",
    )

    kb_check = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Ha, bor — qachon tugashini bilaman",
            callback_data="has_insurance_yes",
        )],
        [InlineKeyboardButton(
            text="🚗 Yo'q, yangi sug'urta kerak",
            callback_data="has_insurance_no",
        )],
    ])
    await message.answer(
        f"👋 <b>Salom, {full_name}!</b>\n\n"
        f"🤔 <b>Avtomobilingizda hozir sug'urta bormi?</b>\n\n"
        f"<blockquote>Sug'urta muddati tugashidan oldin eslatma "
        f"beramiz — jarima va xavfdan saqlanasiz</blockquote>",
        reply_markup=kb_check,
        parse_mode="HTML",
    )
