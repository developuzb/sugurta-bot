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

            # Mijozga — uning ma'lumotlari tasdiqlanganini ko'rsatamiz
            name     = lead["name"] or "Siz"
            phone    = lead["phone"] or "—"
            vehicle  = _VN.get(lead["vehicle"], lead["vehicle"] or "—")
            region   = lead["region_label"] or "—"
            itype    = _TN.get(lead["insurance_type"], lead["insurance_type"] or "—")
            duration = _DN.get(lead["duration"], lead["duration"] or "—")
            price    = lead["price"] or 0
            bonus    = lead["bonus"] or 0

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🛡 Sug'urtani rasmiylashtirish",
                    callback_data="start_insurance"
                )],
                [InlineKeyboardButton(
                    text="🏠 Bosh menyu",
                    callback_data="go_main_menu"
                )],
            ])
            await message.answer(
                f"👋 <b>Xush kelibsiz, {name}!</b>\n\n"
                f"Websaytdagi so'rovingiz topildi:\n"
                f"<blockquote>"
                f"{vehicle} · {region}\n"
                f"{itype} · {duration}\n"
                f"💰 <b>{price:,} so'm</b>  🎁 +{bonus:,} so'm"
                f"</blockquote>\n\n"
                f"📞 Telefon: <code>{phone}</code>\n\n"
                f"Operator tez orada bog'lanadi. Yoki hoziroq sug'urtani "
                f"rasmiylashtiring 👇",
                reply_markup=kb,
                parse_mode="HTML",
            )

            # Operator topic'iga xabar
            from database.db import get_topic
            topic_id = await get_topic(user_id)
            if topic_id:
                from config import GROUP_ID
                try:
                    await message.bot.send_message(
                        chat_id=GROUP_ID,
                        message_thread_id=topic_id,
                        text=(
                            f"🌐 <b>WEBSAYTDAN KELDI</b>\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"👤 {name}  |  📞 <code>{phone}</code>\n"
                            f"{vehicle} · {itype} · {duration}\n"
                            f"📍 {region}\n"
                            f"💰 <b>{price:,} so'm</b>  🎁 +{bonus:,} so'm\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"✅ Telegram orqali ulandi — bu topic orqali bog'laning"
                        ),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(f"web_lead topic notify error: {e}", exc_info=True)

            await update_status(
                bot=message.bot, user_id=user_id, full_name=full_name,
                stage="🌐 Websaytdan Telegram'ga o'tdi",
                details=f"📞 {phone} | {vehicle} | {price:,} so'm",
            )
            return  # Oddiy /start ni ko'rsatmaymiz

    # ─── Oddiy /start ────────────────────────────────────────────────────────
    caption = (
        "<b>🛡 Avtosug'urta — bir necha tugmada tayyor</b>\n\n"
        "<blockquote>"
        "⚡ <b>10 soniyada</b> narxni biling\n"
        "🎁 <b>25% gacha</b> bonusni qaytaramiz\n"
        "💳 <b>Uzum Nasiya</b> — 30 kun foizsiz\n"
        "📦 Uygacha yetkazib beramiz (<b>5,000 so'm</b>)"
        "</blockquote>\n\n"
        "🔥 <i>Hoziroq boshlang — atigi 1 daqiqa vaqtingizni oladi</i> 👇"
    )
    photo = "AgACAgIAAxkBAAIBoWn0MPkM26eiGX3RxxSaaHIwlUj9AAJLGGsb0xKZS-vwjS8WK6cLAQADAgADeQADOwQ"

    await reset_status(user_id)
    await update_status(
        bot=message.bot,
        user_id=user_id,
        full_name=full_name,
        stage="🟢 Bot ochildi — bosh menyuda",
        details=f"👤 {full_name}",
    )
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=start_menu_inline(),
        parse_mode="HTML"
    )
