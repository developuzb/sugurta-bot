"""
Sug'urta jarayoni — UX yaxshilangan versiya.
"""

import re
import logging
from aiogram import F, types, Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    ReplyKeyboardRemove,
)

from states.insurance import InsuranceState
from database.db import set_user_state_time, clear_user_state_time, save_temp_order, update_last_activity
from services.topic_service import ensure_topic
from services.status_service import update_status
from services.prompt_service import clear_prev_prompt, track_prompt
from keyboards.inline import phone_share_kb
from handlers.cancel import cancel_button
from config import GROUP_ID

router = Router(name="insurance")
logger = logging.getLogger(__name__)

PHOTO_VEHICLE = "AgACAgIAAxkBAAIBcWnzj9Za0sMlpaLPtjnUpFQvqMqnAAJOGGsb0xKZS80sDfgQQ7SAAQADAgADeQADOwQ"
PHOTO_REGION = "AgACAgIAAxkBAAIBeGnzlEniA3L3h7ksujidC7TD0wLEAAJiGGsb0xKZS4_eNvA9GxwhAQADAgADeQADOwQ"
PHOTO_TYPE = "AgACAgIAAxkBAAIBdmnzlDESA8DMMrHYRrPaBCJiMNP1AAJhGGsb0xKZS7THMgU8dsh9AQADAgADeQADOwQ"
PHOTO_DURATION = "AgACAgIAAxkBAAIBcWnzj9Za0sMlpaLPtjnUpFQvqMqnAAJOGGsb0xKZS80sDfgQQ7SAAQADAgADeQADOwQ"

PRICES = {
    "yengil": {"toshkent": {"limited": 192000, "unlimited": 384000},
               "viloyat": {"limited": 160000, "unlimited": 320000}},
    "yuk":    {"toshkent": {"limited": 336000, "unlimited": 672000},
               "viloyat": {"limited": 280000, "unlimited": 560000}},
    "bus":    {"toshkent": {"limited": 384000, "unlimited": 768000},
               "viloyat": {"limited": 320000, "unlimited": 640000}},
    "other":  {"toshkent": {"limited": 72000,  "unlimited": 144000},
               "viloyat": {"limited": 60000,   "unlimited": 120000}}
}

VEHICLE_NAMES = {
    "yengil": "🚗 Yengil avtomobil",
    "yuk":    "🚚 Yuk avtomobili",
    "bus":    "🚌 Avtobus",
    "other":  "🏍 Boshqa",
}
REGION_NAMES = {
    "toshkent": "🏙 Toshkent",
    "viloyat":  "🌍 Viloyat",
}
TYPE_NAMES = {
    "limited":   "🚗 Oddiy sug'urta",
    "unlimited": "👑 VIP sug'urta",
}
DURATION_NAMES = {
    "dur_20": "⚡ 20 kun",
    "dur_6":  "📅 6 oy",
    "dur_12": "🛡 1 yil",
}

BONUS_PREVIEW = (
    "💸 <b>Sizga qaytariladigan bonus:</b>\n"
    "📊 O'rtacha: <b>~40,000 so'm</b> (yengil avto)\n"
    "🔥 Maksimal: <b>~280,000 so'm gacha</b> (yuk avto)"
)


def build_progress_text(step: int, total: int = 4) -> str:
    filled = "▰" * step
    empty = "▱" * (total - step)
    return f"<b>{filled}{empty}</b>  <i>{step}/{total}</i>"


def build_summary(data: dict, current_step: str) -> str:
    parts = []
    if data.get("vehicle"):
        parts.append(f"✅ Avto: <b>{VEHICLE_NAMES.get(data['vehicle'], '?')}</b>")
    elif current_step == "vehicle":
        parts.append("🔵 Avto: <i>tanlang...</i>")
    if data.get("region"):
        region_label = REGION_NAMES.get(data['region'], '?')
        if data.get("subregion"):
            region_label = f"🌍 {data['subregion'].title()}"
        parts.append(f"✅ Hudud: <b>{region_label}</b>")
    elif current_step == "region":
        parts.append("🔵 Hudud: <i>tanlang...</i>")
    if data.get("insurance_type"):
        parts.append(f"✅ Sug'urta: <b>{TYPE_NAMES.get(data['insurance_type'], '?')}</b>")
    elif current_step == "type":
        parts.append("🔵 Sug'urta: <i>tanlang...</i>")
    if current_step == "duration":
        parts.append("🔵 Muddat: <i>tanlang...</i>")
    return "\n".join(parts)


async def update_screen(message: types.Message, photo: str, caption: str, keyboard: InlineKeyboardMarkup):
    try:
        await message.edit_media(
            media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
            reply_markup=keyboard,
        )
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard, parse_mode="HTML")


def build_vehicle_caption() -> str:
    return (
        f"{build_progress_text(1)}\n\n"
        f"<blockquote>{build_summary({}, 'vehicle')}</blockquote>\n\n"
        f"{BONUS_PREVIEW}\n\n"
        f"<b>🚗 Qanday turdagi avtomobil minasiz?</b>\n\n"
        f"<i>Sug'urta narxi transport turiga qarab farq qiladi</i>"
    )


def build_vehicle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚗 Yengil", callback_data="vehicle_yengil", style="success"),
                InlineKeyboardButton(text="🚚 Yuk", callback_data="vehicle_yuk", style="success"),
            ],
            [
                InlineKeyboardButton(text="🚌 Avtobus", callback_data="vehicle_bus", style="success"),
                InlineKeyboardButton(text="🏍 Boshqa", callback_data="vehicle_other", style="success"),
            ],
            [InlineKeyboardButton(text="❓ Qaysi avtomobilim?", callback_data="info_vehicle")],
            cancel_button(),
        ]
    )


@router.callback_query(F.data == "start_insurance")
async def start_insurance(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await clear_user_state_time(callback.from_user.id)
        user_id = callback.from_user.id
        full_name = callback.from_user.full_name

        await ensure_topic(user_id, full_name, callback.bot)

        await update_status(
            bot=callback.bot,
            user_id=user_id,
            full_name=full_name,
            stage="🚀 Sug'urta jarayoni — avto tanlamoqda",
        )

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.bot.send_chat_action(user_id, "upload_photo")
        sent = await callback.message.answer_photo(
            photo=PHOTO_VEHICLE,
            caption=build_vehicle_caption(),
            reply_markup=build_vehicle_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(screen_msg_id=sent.message_id)
        await state.set_state(InsuranceState.vehicle)
        await set_user_state_time(user_id)
        await callback.answer()

    except Exception as e:
        logger.error(f"start_insurance error: {e}", exc_info=True)
        await callback.answer("⚠️ Xatolik", show_alert=True)


def build_region_caption(data: dict) -> str:
    return (
        f"{build_progress_text(2)}\n\n"
        f"<blockquote>{build_summary(data, 'region')}</blockquote>\n\n"
        f"<b>📍 Avtomobil qayerda ro'yxatdan o'tgan?</b>\n\n"
        f"<i>Bonus va narx hududga bog'liq:\n"
        f"• Toshkent shahri va viloyati — 5% bonus\n"
        f"• Boshqa viloyatlar — 20% bonus 🎁</i>"
    )


def build_region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏙 Toshkent shahri", callback_data="region_toshkent", style="success")],
            [InlineKeyboardButton(text="🌍 Viloyat", callback_data="region_viloyat", style="success")],
            [InlineKeyboardButton(text="❓ Hudud nima uchun muhim?", callback_data="info_region")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_vehicle"),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow", style="danger"),
            ],
        ]
    )


@router.callback_query(InsuranceState.vehicle, F.data.startswith("vehicle_"))
async def choose_vehicle(callback: types.CallbackQuery, state: FSMContext):
    vehicle = callback.data.split("_")[1]
    await state.update_data(vehicle=vehicle)
    data = await state.get_data()

    user_id = callback.from_user.id
    await update_status(
        bot=callback.bot, user_id=user_id, full_name=callback.from_user.full_name,
        stage="🚗 Avto tanlandi — hudud tanlamoqda",
        details=f"🚗 Avto: {VEHICLE_NAMES.get(vehicle, vehicle)}",
    )

    await update_screen(callback.message, photo=PHOTO_REGION,
                        caption=build_region_caption(data), keyboard=build_region_keyboard())
    await state.set_state(InsuranceState.region)
    await set_user_state_time(user_id)
    await callback.answer()


@router.callback_query(F.data == "back_to_vehicle")
async def back_to_vehicle(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(region=None, subregion=None, insurance_type=None)
    await update_screen(callback.message, photo=PHOTO_VEHICLE,
                        caption=build_vehicle_caption(), keyboard=build_vehicle_keyboard())
    await state.set_state(InsuranceState.vehicle)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


def build_type_caption(data: dict) -> str:
    return (
        f"{build_progress_text(3)}\n\n"
        f"<blockquote>{build_summary(data, 'type')}</blockquote>\n\n"
        f"<b>🛡 Sug'urta turini tanlang</b>\n\n"
        f"<i>👑 VIP — istalgan haydovchi mumkin\n"
        f"🚗 Oddiy — 1–5 haydovchi (arzonroq)</i>"
    )


def build_type_keyboard(back_target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 VIP sug'urta", callback_data="type_unlimited", style="success")],
            [InlineKeyboardButton(text="🚗 Oddiy sug'urta", callback_data="type_limited", style="success")],
            [InlineKeyboardButton(text="❓ VIP va Oddiy farqi?", callback_data="info_type")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_target),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow", style="danger"),
            ],
        ]
    )


def build_subregion_caption(data: dict) -> str:
    return (
        f"{build_progress_text(2)}\n\n"
        f"<blockquote>{build_summary(data, 'region')}</blockquote>\n\n"
        f"<b>🌍 Qaysi viloyatdansiz?</b>"
    )


def build_subregion_keyboard() -> InlineKeyboardMarkup:
    regions = [
        (" 10 | Toshkent vil.", "toshkent_vil"),
        (" 20 | Sirdaryo", "sirdaryo"),
        (" 25 | Jizzax", "jizzax"),
        (" 30 | Samarqand", "samarqand"),
        (" 40 | Farg'ona", "fargona"),
        (" 50 | Namangan", "namangan"),
        (" 60 | Andijon", "andijon"),
        (" 70 | Qashqadaryo", "qashqadaryo"),
        (" 75 | Surxondaryo", "surxondaryo"),
        (" 80 | Buxoro", "buxoro"),
        (" 85 | Navoiy", "navoiy"),
        (" 90 | Xorazm", "xorazm"),
        (" 95 | Qoraqalpog'iston", "qq"),
    ]
    buttons = [InlineKeyboardButton(text=name, callback_data=f"sub_{code}", style="success") for name, code in regions]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_region"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow", style="danger"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(InsuranceState.region, F.data.startswith("region_"))
async def choose_region(callback: types.CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[1]
    await state.update_data(region=region, subregion=None)
    data = await state.get_data()
    user_id = callback.from_user.id

    next_stage = "sug'urta turi tanlamoqda" if region == "toshkent" else "viloyat tanlamoqda"
    await update_status(
        bot=callback.bot, user_id=user_id, full_name=callback.from_user.full_name,
        stage=f"📍 Hudud tanlandi — {next_stage}",
        details=(
            f"🚗 Avto: {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
            f"📍 Hudud: {REGION_NAMES.get(region, region)}"
        ),
    )

    if region == "toshkent":
        await update_screen(callback.message, photo=PHOTO_TYPE,
                            caption=build_type_caption(data),
                            keyboard=build_type_keyboard(back_target="back_to_region"))
        await state.set_state(InsuranceState.insurance_type)
    else:
        await update_screen(callback.message, photo=PHOTO_REGION,
                            caption=build_subregion_caption(data),
                            keyboard=build_subregion_keyboard())
        await state.set_state(InsuranceState.subregion)

    await set_user_state_time(user_id)
    await callback.answer()


@router.callback_query(F.data == "back_to_region")
async def back_to_region(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(region=None, subregion=None, insurance_type=None)
    data = await state.get_data()
    await update_screen(callback.message, photo=PHOTO_REGION,
                        caption=build_region_caption(data), keyboard=build_region_keyboard())
    await state.set_state(InsuranceState.region)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


@router.callback_query(InsuranceState.subregion, F.data.startswith("sub_"))
async def choose_subregion(callback: types.CallbackQuery, state: FSMContext):
    sub = callback.data.split("_", 1)[1]
    await state.update_data(region="viloyat", subregion=sub)
    data = await state.get_data()
    user_id = callback.from_user.id

    await update_status(
        bot=callback.bot, user_id=user_id, full_name=callback.from_user.full_name,
        stage="🌍 Viloyat tanlandi — sug'urta turi tanlamoqda",
        details=(
            f"🚗 Avto: {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
            f"🌍 Viloyat: {sub.title()}"
        ),
    )

    await update_screen(callback.message, photo=PHOTO_TYPE,
                        caption=build_type_caption(data),
                        keyboard=build_type_keyboard(back_target="back_to_subregion"))
    await state.set_state(InsuranceState.insurance_type)
    await set_user_state_time(user_id)
    await callback.answer()


@router.callback_query(F.data == "back_to_subregion")
async def back_to_subregion(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(insurance_type=None)
    data = await state.get_data()
    await update_screen(callback.message, photo=PHOTO_REGION,
                        caption=build_subregion_caption(data), keyboard=build_subregion_keyboard())
    await state.set_state(InsuranceState.subregion)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


def build_duration_caption(data: dict) -> str:
    return (
        f"{build_progress_text(4)}\n\n"
        f"<blockquote>{build_summary(data, 'duration')}</blockquote>\n\n"
        f"<b>⏳ Sug'urta muddatini tanlang</b>\n\n"
        f"<i>🛡 1 yil — eng tejamli\n"
        f"📅 6 oy — o'rtacha\n"
        f"⚡ 20 kun — qisqa muddatli</i>"
    )


def build_duration_keyboard(back_target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛡 1 yil (tavsiya)", callback_data="dur_12", style="success")],
            [InlineKeyboardButton(text="📅 6 oy", callback_data="dur_6", style="success")],
            [InlineKeyboardButton(text="⚡ 20 kun", callback_data="dur_20", style="success")],
            [InlineKeyboardButton(text="❓ Qaysi muddat foydali?", callback_data="info_duration")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_target),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow", style="danger"),
            ],
        ]
    )


@router.callback_query(InsuranceState.insurance_type, F.data.startswith("type_"))
async def choose_type(callback: types.CallbackQuery, state: FSMContext):
    insurance_type = "unlimited" if callback.data == "type_unlimited" else "limited"
    await state.update_data(insurance_type=insurance_type)
    data = await state.get_data()
    user_id = callback.from_user.id

    region_label = REGION_NAMES.get(data.get("region"), "?")
    if data.get("subregion"):
        region_label = f"🌍 {data['subregion'].title()}"
    await update_status(
        bot=callback.bot, user_id=user_id, full_name=callback.from_user.full_name,
        stage="🛡 Sug'urta turi tanlandi — muddat tanlamoqda",
        details=(
            f"🚗 {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
            f"📍 {region_label}\n"
            f"🛡 {TYPE_NAMES.get(insurance_type, '?')}"
        ),
    )

    await update_screen(callback.message, photo=PHOTO_DURATION,
                        caption=build_duration_caption(data),
                        keyboard=build_duration_keyboard(back_target="back_to_type"))
    await state.set_state(InsuranceState.duration)
    await set_user_state_time(user_id)
    await callback.answer()


@router.callback_query(F.data == "back_to_type")
async def back_to_type(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(insurance_type=None)
    data = await state.get_data()
    back_target = "back_to_subregion" if data.get("subregion") else "back_to_region"
    await update_screen(callback.message, photo=PHOTO_TYPE,
                        caption=build_type_caption(data),
                        keyboard=build_type_keyboard(back_target=back_target))
    await state.set_state(InsuranceState.insurance_type)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


@router.callback_query(InsuranceState.duration, F.data.startswith("dur_"))
async def final_calc(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        required = ["vehicle", "region", "insurance_type"]
        if any(k not in data or not data.get(k) for k in required):
            await callback.message.answer("⚠️ Sessiya yo'qoldi. /start orqali qayta boshlang")
            await state.clear()
            await clear_user_state_time(callback.from_user.id)
            await callback.answer()
            return

        await callback.bot.send_chat_action(callback.from_user.id, "typing")
        duration_map = {"dur_20": 0.2, "dur_6": 0.7, "dur_12": 1.0}
        coef = duration_map.get(callback.data, 1.0)

        # PDF: "Toshkent shahri VA Toshkent viloyati" — bitta narx guruhi
        price_region = "toshkent" if (
            data["region"] == "toshkent" or data.get("subregion") == "toshkent_vil"
        ) else "viloyat"

        try:
            base_price = PRICES[data["vehicle"]][price_region][data["insurance_type"]]
        except KeyError:
            await callback.message.answer("⚠️ Xato. /start qayta boshlang")
            await state.clear()
            await clear_user_state_time(callback.from_user.id)
            await callback.answer()
            return

        price = int(base_price * coef)
        is_toshkent_zone = (
            data["region"] == "toshkent" or data.get("subregion") == "toshkent_vil"
        )
        bonus = int(price * (0.05 if is_toshkent_zone else 0.20))
        await state.update_data(price=price, bonus=bonus, duration=callback.data)

        user_id = callback.from_user.id
        await save_temp_order(user_id, {
            "vehicle": data["vehicle"],
            "region": price_region,   # "toshkent" or "viloyat" — narx uchun to'g'ri qiymat
            "insurance_type": data["insurance_type"],
            "price": price,
            "bonus": bonus,
        })
        await update_last_activity(user_id)

        region_label = REGION_NAMES.get(data.get("region"), "?")
        if data.get("subregion"):
            region_label = f"🌍 {data['subregion'].title()}"
        await update_status(
            bot=callback.bot, user_id=user_id,
            full_name=callback.from_user.full_name,
            stage="💰 Narx hisoblandi — qaror kutilmoqda",
            details=(
                f"🚗 {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
                f"📍 {region_label}\n"
                f"🛡 {TYPE_NAMES.get(data.get('insurance_type'), '?')} · "
                f"{DURATION_NAMES.get(callback.data, '?')}\n"
                f"💰 <b>{price:,} so'm</b> · 🎁 +{bonus:,} bonus"
            ),
        )

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Hozir rasmiylashtirish", callback_data="continue", style="success")],
                [InlineKeyboardButton(text="💳 Uzum Nasiya (30 kun foizsiz)", callback_data="nasiya_info")],
                [InlineKeyboardButton(text="🔔 Hozir emas — eslatib turing", callback_data="reminder_start")],
                [
                    InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="restart"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow", style="danger"),
                ],
            ]
        )

        bonus_note = (
            "😔 <i>Afsuski, Toshkent shahri va viloyatida davlat tarifi bo'yicha "
            "bonus atigi 5% — boshqa viloyatlarda esa 20% bo'lardi</i>\n"
        ) if is_toshkent_zone else (
            "🎁 <i>Viloyat bo'lgani uchun bonus 20%!</i>\n"
        )

        result_text = (
            f"<b>🎉 Sizning shaxsiy narxingiz tayyor!</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🚗 {VEHICLE_NAMES.get(data['vehicle'], '?')}\n"
            f"📍 {REGION_NAMES.get(data['region'], '?')}"
            f"{' · ' + data['subregion'].title() if data.get('subregion') else ''}\n"
            f"🛡 {TYPE_NAMES.get(data['insurance_type'], '?')} · {DURATION_NAMES.get(callback.data, '?')}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"💰 To'lov: <b>{price:,} so'm</b>\n"
            f"🎁 Sizga qaytadi: <b>+{bonus:,} so'm bonus</b>\n\n"
            f"{bonus_note}"
            f"✅ <i>Bonus sug'urta rasmiylashgach kartangizga o'tadi</i>\n"
            f"💳 <i>Pulingiz yo'qmi? — Uzum Nasiya (30 kun foizsiz)</i>\n\n"
            f"👇 Hozir rasmiylashtirib, bonusni oling"
        )
        await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"final_calc error: {e}", exc_info=True)
        await callback.message.answer("⚠️ Xatolik. Qayta urinib ko'ring")
        await callback.answer()


@router.callback_query(F.data == "info_vehicle")
async def info_vehicle(callback: types.CallbackQuery):
    await callback.answer(
        "🚗 Yengil — sedan, hatchback, SUV\n🚚 Yuk — gruzovik, fura, pikap\n"
        "🚌 Avtobus — passazhir tashish\n🏍 Boshqa — moped, traktor va h.k.",
        show_alert=True
    )


@router.callback_query(F.data == "info_region")
async def info_region(callback: types.CallbackQuery):
    await callback.answer(
        "📍 Avtomobilingiz qayerda ro'yxatdan o'tgani\n(texpasportdagi hudud).\n\n"
        "💰 Toshkent: 5% bonus\n💰 Viloyat: 20% bonus",
        show_alert=True
    )


@router.callback_query(F.data == "info_type")
async def info_type(callback: types.CallbackQuery):
    await callback.answer(
        "👑 VIP sug'urta — istalgan haydovchi haydashi mumkin (oila, do'st, yollanma).\n\n"
        "🚗 Oddiy sug'urta — faqat 1-5 ta belgilangan haydovchi. Arzonroq.",
        show_alert=True
    )


@router.callback_query(F.data == "info_duration")
async def info_duration(callback: types.CallbackQuery):
    await callback.answer(
        "🛡 1 yil — eng tejamli, kun bo'yicha arzonroq.\n\n"
        "📅 6 oy — o'rta variant.\n\n⚡ 20 kun — qisqa safar yoki sotish oldidan.",
        show_alert=True
    )


@router.callback_query(F.data == "continue")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await update_status(
        bot=callback.bot, user_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        stage="📞 Telefon raqami kutilmoqda",
        details="🔥 Mijoz rasmiylashtirishga tayyor — qo'ng'iroq qilishga shay turing",
    )

    await clear_prev_prompt(callback.bot, callback.message.chat.id, state)
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    sent = await callback.message.answer(
        "📞 <b>Bitta qadam qoldi — telefon raqamingiz</b>\n\n"
        "<blockquote>⚡ Operator <b>5-10 daqiqa</b> ichida qo'ng'iroq qilib,\nsug'urtangizni rasmiylashtiradi</blockquote>\n\n"
        "👇 Pastdagi tugma orqali 1 ta bosish bilan yuboring\n"
        "yoki qo'lda kiriting: <code>+998901234567</code>",
        reply_markup=inline_kb, parse_mode="HTML"
    )
    await track_prompt(state, sent.message_id)
    await callback.message.answer(
        "📱 <i>Tugmadan foydalaning</i>",
        reply_markup=phone_share_kb(),
    )
    await state.set_state(InsuranceState.phone)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "restart")
async def restart_calc(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await clear_user_state_time(callback.from_user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    sent = await callback.message.answer_photo(
        photo=PHOTO_VEHICLE, caption=build_vehicle_caption(),
        reply_markup=build_vehicle_keyboard(), parse_mode="HTML"
    )
    await state.update_data(screen_msg_id=sent.message_id)
    await state.set_state(InsuranceState.vehicle)
    await set_user_state_time(callback.from_user.id)
    await callback.answer()


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


@router.message(InsuranceState.phone)
async def receive_phone(message: types.Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return

    raw = message.contact.phone_number if message.contact else (message.text.strip() if message.text else "")
    phone = normalize_phone(raw)
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer(
            "❗ Telefon raqami noto'g'ri formatda\n\n"
            "Iltimos, quyidagi formatda yozing:\n"
            "<code>+998901234567</code> yoki <code>901234567</code>",
            reply_markup=kb, parse_mode="HTML"
        )
        return

    data = await state.get_data()
    user_id = message.from_user.id
    is_nasiya = data.get("payment_type") == "nasiya"
    await bot.send_chat_action(user_id, "typing")
    topic_id = await ensure_topic(user_id, message.from_user.full_name, bot)

    if topic_id:
        try:
            if is_nasiya:
                text = (
                    f"💳 <b>NASIYA SO'ROVI</b>\n━━━━━━━━━━━━━━━\n"
                    f"👤 {message.from_user.full_name}\n📞 <code>{phone}</code>\n📋 To'lov: Uzum Nasiya (30 kun foizsiz)"
                )
            else:
                text = (
                    f"📞 <b>YANGI MIJOZ</b>\n━━━━━━━━━━━━━━━\n"
                    f"👤 {message.from_user.full_name}\n📞 <code>{phone}</code>\n"
                    f"🚗 {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
                    f"📍 {REGION_NAMES.get(data.get('region'), '?')}"
                    f"{' · ' + data['subregion'].title() if data.get('subregion') else ''}\n"
                    f"🛡 {TYPE_NAMES.get(data.get('insurance_type'), '?')}\n"
                    f"⏳ {DURATION_NAMES.get(data.get('duration'), '?')}\n"
                    f"💰 {data.get('price', 0):,} so'm\n"
                    f"🎁 Bonus: {data.get('bonus', 0):,} so'm"
                )
            await bot.send_message(
                chat_id=GROUP_ID, message_thread_id=topic_id, text=text, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"phone topic notify failed: {e}", exc_info=True)

    final_stage = "💳 NASIYA so'rovi yuborildi" if is_nasiya else "✅ Sug'urta so'rovi tugatildi"
    await update_status(
        bot=bot, user_id=user_id, full_name=message.from_user.full_name,
        stage=final_stage,
        details=f"📞 {phone} — qo'ng'iroq qiling",
    )
    # Yangi mijoz seansida toza status xabari yaratiladi
    from services.status_service import reset_status
    await reset_status(user_id)
    await clear_prev_prompt(bot, message.chat.id, state)

    await state.clear()
    await clear_user_state_time(user_id)

    user_text = (
        "✅ <b>Ajoyib! So'rovingiz qabul qilindi</b>\n\n"
        "<blockquote>"
        "📞 Operator <b>Uzum Nasiya</b> orqali rasmiylashtirish uchun\n"
        "⏳ <b>5-10 daqiqa ichida</b> qo'ng'iroq qiladi\n\n"
        "💳 <b>30 kun ichida</b> to'lasangiz — foizsiz\n"
        "(undan keyin Uzum Nasiya komissiyasi qo'llaniladi)\n\n"
        "🎁 Sug'urta rasmiylashgach <b>bonus avtomatik to'lanadi</b>"
        "</blockquote>"
    ) if is_nasiya else (
        "✅ <b>Ajoyib! So'rovingiz qabul qilindi</b>\n\n"
        "<blockquote>"
        "📞 Operator <b>5-10 daqiqa ichida</b> qo'ng'iroq qiladi\n"
        "🎁 Sug'urta rasmiylashgach <b>bonus avtomatik to'lanadi</b>"
        "</blockquote>"
    )

    # Reply keyboard'ni olib tashlaymiz
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]])
    await message.answer(user_text, reply_markup=kb, parse_mode="HTML")


@router.message(StateFilter(
    InsuranceState.vehicle,
    InsuranceState.region,
    InsuranceState.subregion,
    InsuranceState.insurance_type,
    InsuranceState.duration,
))
async def insurance_button_required(message: types.Message):
    if message.text and message.text.startswith("/"):
        return
    await message.answer("👆 Iltimos, yuqoridagi tugmalardan birini tanlang")
