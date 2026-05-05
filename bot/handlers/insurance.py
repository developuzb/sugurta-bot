"""
Sug'urta jarayoni — UX yaxshilangan versiya.

O'zgarishlar:
1. ✅ Bitta xabar yangilanadi (edit_message_media) — chat ifloslanmaydi
2. ✅ Progress indikator (1/4 → 2/4 → 3/4 → 4/4)
3. ✅ Oldingi tanlovlar ko'rinib turadi (✅ belgisi bilan)
4. ✅ "❓ Bu nima?" tugmalari — qisqa tushuntirishlar
5. ✅ Bekor qilish + Bosh menyu har joyda
6. ✅ State to'g'ri tozalash, KeyError himoya
7. ✅ State'da rasm message_id saqlanadi (qayta ishlatish uchun)
"""

import re
import logging
from aiogram import F, types, Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)

from states.insurance import InsuranceState
from database.db import get_topic, save_user
from handlers.cancel import cancel_button
from config import GROUP_ID

router = Router(name="insurance")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# RASMLAR — har bosqichga
# ─────────────────────────────────────────────────────────────────────────────

PHOTO_VEHICLE = "AgACAgIAAxkBAAIBcWnzj9Za0sMlpaLPtjnUpFQvqMqnAAJOGGsb0xKZS80sDfgQQ7SAAQADAgADeQADOwQ"
PHOTO_REGION = "AgACAgIAAxkBAAIBeGnzlEniA3L3h7ksujidC7TD0wLEAAJiGGsb0xKZS4_eNvA9GxwhAQADAgADeQADOwQ"
PHOTO_TYPE = "AgACAgIAAxkBAAIBdmnzlDESA8DMMrHYRrPaBCJiMNP1AAJhGGsb0xKZS7THMgU8dsh9AQADAgADeQADOwQ"
PHOTO_DURATION = "AgACAgIAAxkBAAIBcWnzj9Za0sMlpaLPtjnUpFQvqMqnAAJOGGsb0xKZS80sDfgQQ7SAAQADAgADeQADOwQ"


# ─────────────────────────────────────────────────────────────────────────────
# NARXLAR
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# YORDAMCHI: progress + tanlovlar matnini yasash
# ─────────────────────────────────────────────────────────────────────────────

def build_progress_text(step: int, total: int = 4) -> str:
    """Progress indikator: ▰▰▱▱"""
    filled = "▰" * step
    empty = "▱" * (total - step)
    return f"<b>{filled}{empty}</b>  <i>{step}/{total}</i>"


def build_summary(data: dict, current_step: str) -> str:
    """Oldingi tanlovlarni ko'rsatadi."""
    parts = []

    # Vehicle
    if data.get("vehicle"):
        parts.append(f"✅ Avto: <b>{VEHICLE_NAMES.get(data['vehicle'], '?')}</b>")
    elif current_step == "vehicle":
        parts.append("🔵 Avto: <i>tanlang...</i>")

    # Region
    if data.get("region"):
        region_label = REGION_NAMES.get(data['region'], '?')
        if data.get("subregion"):
            region_label = f"🌍 {data['subregion'].title()}"
        parts.append(f"✅ Hudud: <b>{region_label}</b>")
    elif current_step == "region":
        parts.append("🔵 Hudud: <i>tanlang...</i>")

    # Type
    if data.get("insurance_type"):
        parts.append(f"✅ Sug'urta: <b>{TYPE_NAMES.get(data['insurance_type'], '?')}</b>")
    elif current_step == "type":
        parts.append("🔵 Sug'urta: <i>tanlang...</i>")

    # Duration
    if current_step == "duration":
        parts.append("🔵 Muddat: <i>tanlang...</i>")

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# YORDAMCHI: ekranni yangilash (edit_message_media)
# ─────────────────────────────────────────────────────────────────────────────

async def update_screen(
    message: types.Message,
    photo: str,
    caption: str,
    keyboard: InlineKeyboardMarkup,
):
    """Mavjud xabarni yangilash. Yangi xabar yaratmaydi.

    Agar fail bo'lsa (rasm bir xil yoki xabar tahrir qilib bo'lmasa),
    yangi xabar yuboradi.
    """
    try:
        await message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML",
            ),
            reply_markup=keyboard,
        )
    except Exception:
        # Fallback — eski xabarni o'chirib, yangisini yuboramiz
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1-EKRAN: AVTOMOBIL TURI
# ─────────────────────────────────────────────────────────────────────────────

def build_vehicle_caption() -> str:
    return (
        f"{build_progress_text(1)}\n\n"
        f"<blockquote>{build_summary({}, 'vehicle')}</blockquote>\n\n"
        f"<b>🚗 Qanday turdagi avtomobil minasiz?</b>\n\n"
        f"<i>Sug'urta narxi transport turiga qarab farq qiladi</i>"
    )


def build_vehicle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚗 Yengil", callback_data="vehicle_yengil"),
                InlineKeyboardButton(text="🚚 Yuk", callback_data="vehicle_yuk"),
            ],
            [
                InlineKeyboardButton(text="🚌 Avtobus", callback_data="vehicle_bus"),
                InlineKeyboardButton(text="🏍 Boshqa", callback_data="vehicle_other"),
            ],
            [InlineKeyboardButton(text="❓ Qaysi avtomobilim?", callback_data="info_vehicle")],
            cancel_button(),
        ]
    )


@router.callback_query(F.data == "start_insurance")
async def start_insurance(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        user_id = callback.from_user.id

        # Topic ensure
        topic_id = await get_topic(user_id)
        if not topic_id:
            topic = await callback.bot.create_forum_topic(
                chat_id=GROUP_ID,
                name=f"{callback.from_user.full_name} | {user_id}"
            )
            topic_id = topic.message_thread_id
            await save_user(user_id, topic_id)

        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text="🚀 Sug'urta jarayoni boshlandi"
            )
        except Exception:
            pass

        # Eski xabar tugmalarini tozalash
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Yangi xabar — bu boshlang'ich, edit emas
        sent = await callback.message.answer_photo(
            photo=PHOTO_VEHICLE,
            caption=build_vehicle_caption(),
            reply_markup=build_vehicle_keyboard(),
            parse_mode="HTML"
        )

        # Bu xabar ID sini saqlaymiz — keyingi ekranlarda edit qilamiz
        await state.update_data(screen_msg_id=sent.message_id)
        await state.set_state(InsuranceState.vehicle)
        await callback.answer()

    except Exception as e:
        logger.error(f"start_insurance error: {e}", exc_info=True)
        await callback.answer("⚠️ Xatolik", show_alert=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2-EKRAN: HUDUD
# ─────────────────────────────────────────────────────────────────────────────

def build_region_caption(data: dict) -> str:
    return (
        f"{build_progress_text(2)}\n\n"
        f"<blockquote>{build_summary(data, 'region')}</blockquote>\n\n"
        f"<b>📍 Avtomobil qayerda ro'yxatdan o'tgan?</b>\n\n"
        f"<i>Bonus va narx hududga bog'liq:\n"
        f"• Toshkent — 5% bonus\n"
        f"• Viloyat — 25% bonus 🎁</i>"
    )


def build_region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏙 Toshkent shahri", callback_data="region_toshkent")],
            [InlineKeyboardButton(text="🌍 Viloyat", callback_data="region_viloyat")],
            [InlineKeyboardButton(text="❓ Hudud nima uchun muhim?", callback_data="info_region")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_vehicle"),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow"),
            ],
        ]
    )


@router.callback_query(InsuranceState.vehicle, F.data.startswith("vehicle_"))
async def choose_vehicle(callback: types.CallbackQuery, state: FSMContext):
    vehicle = callback.data.split("_")[1]
    await state.update_data(vehicle=vehicle)
    data = await state.get_data()

    # Topic'ga log
    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🚗 Avtomobil: {VEHICLE_NAMES.get(vehicle, vehicle)}"
            )
        except Exception:
            pass

    await update_screen(
        callback.message,
        photo=PHOTO_REGION,
        caption=build_region_caption(data),
        keyboard=build_region_keyboard(),
    )
    await state.set_state(InsuranceState.region)
    await callback.answer()


@router.callback_query(F.data == "back_to_vehicle")
async def back_to_vehicle(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(region=None, subregion=None, insurance_type=None)
    await update_screen(
        callback.message,
        photo=PHOTO_VEHICLE,
        caption=build_vehicle_caption(),
        keyboard=build_vehicle_keyboard(),
    )
    await state.set_state(InsuranceState.vehicle)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 3-EKRAN: SUG'URTA TURI (yoki viloyat tanlash)
# ─────────────────────────────────────────────────────────────────────────────

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
            [InlineKeyboardButton(text="👑 VIP sug'urta", callback_data="type_unlimited")],
            [InlineKeyboardButton(text="🚗 Oddiy sug'urta", callback_data="type_limited")],
            [InlineKeyboardButton(text="❓ VIP va Oddiy farqi?", callback_data="info_type")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_target),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow"),
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
    buttons = [
        InlineKeyboardButton(text=name, callback_data=f"sub_{code}")
        for name, code in regions
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_region"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(InsuranceState.region, F.data.startswith("region_"))
async def choose_region(callback: types.CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[1]
    await state.update_data(region=region, subregion=None)
    data = await state.get_data()

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"📍 Hudud: {REGION_NAMES.get(region, region)}"
            )
        except Exception:
            pass

    if region == "toshkent":
        await update_screen(
            callback.message,
            photo=PHOTO_TYPE,
            caption=build_type_caption(data),
            keyboard=build_type_keyboard(back_target="back_to_region"),
        )
        await state.set_state(InsuranceState.insurance_type)
    else:
        await update_screen(
            callback.message,
            photo=PHOTO_REGION,
            caption=build_subregion_caption(data),
            keyboard=build_subregion_keyboard(),
        )
        await state.set_state(InsuranceState.subregion)

    await callback.answer()


@router.callback_query(F.data == "back_to_region")
async def back_to_region(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(region=None, subregion=None, insurance_type=None)
    data = await state.get_data()
    await update_screen(
        callback.message,
        photo=PHOTO_REGION,
        caption=build_region_caption(data),
        keyboard=build_region_keyboard(),
    )
    await state.set_state(InsuranceState.region)
    await callback.answer()


@router.callback_query(InsuranceState.subregion, F.data.startswith("sub_"))
async def choose_subregion(callback: types.CallbackQuery, state: FSMContext):
    sub = callback.data.split("_", 1)[1]
    await state.update_data(region="viloyat", subregion=sub)
    data = await state.get_data()

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🌍 Viloyat: {sub}"
            )
        except Exception:
            pass

    await update_screen(
        callback.message,
        photo=PHOTO_TYPE,
        caption=build_type_caption(data),
        keyboard=build_type_keyboard(back_target="back_to_subregion"),
    )
    await state.set_state(InsuranceState.insurance_type)
    await callback.answer()


@router.callback_query(F.data == "back_to_subregion")
async def back_to_subregion(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(insurance_type=None)
    data = await state.get_data()
    await update_screen(
        callback.message,
        photo=PHOTO_REGION,
        caption=build_subregion_caption(data),
        keyboard=build_subregion_keyboard(),
    )
    await state.set_state(InsuranceState.subregion)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# 4-EKRAN: MUDDAT
# ─────────────────────────────────────────────────────────────────────────────

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
            [InlineKeyboardButton(text="🛡 1 yil (tavsiya)", callback_data="dur_12")],
            [InlineKeyboardButton(text="📅 6 oy", callback_data="dur_6")],
            [InlineKeyboardButton(text="⚡ 20 kun", callback_data="dur_20")],
            [InlineKeyboardButton(text="❓ Qaysi muddat foydali?", callback_data="info_duration")],
            [
                InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_target),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow"),
            ],
        ]
    )


@router.callback_query(InsuranceState.insurance_type, F.data.startswith("type_"))
async def choose_type(callback: types.CallbackQuery, state: FSMContext):
    insurance_type = "unlimited" if callback.data == "type_unlimited" else "limited"
    await state.update_data(insurance_type=insurance_type)
    data = await state.get_data()

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)
    if topic_id:
        try:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🛡 Sug'urta: {TYPE_NAMES.get(insurance_type, insurance_type)}"
            )
        except Exception:
            pass

    # Orqaga qaytishda subregion bormi?
    back_target = "back_to_subregion" if data.get("subregion") else "back_to_region"

    await update_screen(
        callback.message,
        photo=PHOTO_DURATION,
        caption=build_duration_caption(data),
        keyboard=build_duration_keyboard(back_target=back_target),
    )
    await state.set_state(InsuranceState.duration)
    await callback.answer()


@router.callback_query(F.data == "back_to_type")
async def back_to_type(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(insurance_type=None)
    back_target = "back_to_subregion" if data.get("subregion") else "back_to_region"
    await update_screen(
        callback.message,
        photo=PHOTO_TYPE,
        caption=build_type_caption(data),
        keyboard=build_type_keyboard(back_target=back_target),
    )
    await state.set_state(InsuranceState.insurance_type)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# YAKUN: NARX HISOBLASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.duration, F.data.startswith("dur_"))
async def final_calc(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()

        # Validation
        required = ["vehicle", "region", "insurance_type"]
        if any(k not in data or not data.get(k) for k in required):
            await callback.message.answer(
                "⚠️ Sessiya yo'qoldi. /start orqali qayta boshlang"
            )
            await state.clear()
            await callback.answer()
            return

        duration_map = {"dur_20": 0.2, "dur_6": 0.7, "dur_12": 1.0}
        coef = duration_map.get(callback.data, 1.0)

        try:
            base_price = PRICES[data["vehicle"]][data["region"]][data["insurance_type"]]
        except KeyError:
            await callback.message.answer("⚠️ Xato. /start qayta boshlang")
            await state.clear()
            await callback.answer()
            return

        price = int(base_price * coef)
        bonus = int(price * (0.05 if data["region"] == "toshkent" else 0.25))

        await state.update_data(
            price=price,
            bonus=bonus,
            duration=callback.data
        )

        # Eski tugmalarni tozalash (rasmni qoldiramiz)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Davom etish", callback_data="continue")],
                [InlineKeyboardButton(text="💳 30 kun 0% nasiya", callback_data="nasiya_info")],
                [InlineKeyboardButton(text="🔔 Eslatma so'rash", callback_data="reminder_start")],
                [
                    InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="restart"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_flow"),
                ],
            ]
        )

        result_text = (
            f"<b>🎉 Hisoblash tayyor!</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🚗 {VEHICLE_NAMES.get(data['vehicle'], '?')}\n"
            f"📍 {REGION_NAMES.get(data['region'], '?')}"
            f"{' · ' + data['subregion'].title() if data.get('subregion') else ''}\n"
            f"🛡 {TYPE_NAMES.get(data['insurance_type'], '?')}\n"
            f"⏳ {DURATION_NAMES.get(callback.data, '?')}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Narx: {price:,} so'm</b>\n"
            f"🎁 <b>Bonus: {bonus:,} so'm</b>\n\n"
            f"<i>Davom etishni tanlang yoki nasiya orqali rasmiylashtiring</i>"
        )

        await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"final_calc error: {e}", exc_info=True)
        await callback.message.answer("⚠️ Xatolik. Qayta urinib ko'ring")
        await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# INFO TUGMALARI (alert orqali tushuntirish)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "info_vehicle")
async def info_vehicle(callback: types.CallbackQuery):
    await callback.answer(
        "🚗 Yengil — sedan, hatchback, SUV\n"
        "🚚 Yuk — gruzovik, fura, pikap\n"
        "🚌 Avtobus — passazhir tashish\n"
        "🏍 Boshqa — moped, traktor va h.k.",
        show_alert=True
    )


@router.callback_query(F.data == "info_region")
async def info_region(callback: types.CallbackQuery):
    await callback.answer(
        "📍 Avtomobilingiz qayerda ro'yxatdan o'tgani\n"
        "(texpasportdagi hudud).\n\n"
        "💰 Toshkent: 5% bonus\n"
        "💰 Viloyat: 25% bonus",
        show_alert=True
    )


@router.callback_query(F.data == "info_type")
async def info_type(callback: types.CallbackQuery):
    await callback.answer(
        "👑 VIP sug'urta — istalgan haydovchi haydashi mumkin "
        "(oila, do'st, yollanma).\n\n"
        "🚗 Oddiy sug'urta — faqat 1-5 ta belgilangan haydovchi. "
        "Arzonroq.",
        show_alert=True
    )


@router.callback_query(F.data == "info_duration")
async def info_duration(callback: types.CallbackQuery):
    await callback.answer(
        "🛡 1 yil — eng tejamli, kun bo'yicha arzonroq.\n\n"
        "📅 6 oy — o'rta variant.\n\n"
        "⚡ 20 kun — qisqa safar yoki sotish oldidan.",
        show_alert=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# DAVOM ETISH → TELEFON SO'RASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "continue")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
    await callback.message.answer(
        "📞 <b>Telefon raqamingizni yozing</b>\n\n"
        "<blockquote>"
        "Operator siz bilan tez orada bog'lanadi"
        "</blockquote>\n\n"
        "<code>+998901234567</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InsuranceState.phone)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# QAYTA HISOBLASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "restart")
async def restart_calc(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    sent = await callback.message.answer_photo(
        photo=PHOTO_VEHICLE,
        caption=build_vehicle_caption(),
        reply_markup=build_vehicle_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(screen_msg_id=sent.message_id)
    await state.set_state(InsuranceState.vehicle)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# TELEFON QABUL QILISH
# ─────────────────────────────────────────────────────────────────────────────

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

    phone = normalize_phone(message.text.strip() if message.text else "")
    if not phone:
        kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button()])
        await message.answer(
            "❗ Telefon noto'g'ri\n\n"
            "+998901234567 yoki 901234567",
            reply_markup=kb
        )
        return

    data = await state.get_data()
    user_id = message.from_user.id
    is_nasiya = data.get("payment_type") == "nasiya"

    topic_id = await get_topic(user_id)
    if topic_id:
        try:
            if is_nasiya:
                text = (
                    f"💳 <b>NASIYA SO'ROVI</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📞 <code>{phone}</code>\n"
                    f"📋 To'lov: 30 kun nasiya"
                )
            else:
                text = (
                    f"📞 <b>YANGI MIJOZ</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📞 <code>{phone}</code>\n"
                    f"🚗 {VEHICLE_NAMES.get(data.get('vehicle'), '?')}\n"
                    f"📍 {REGION_NAMES.get(data.get('region'), '?')}"
                    f"{' · ' + data['subregion'].title() if data.get('subregion') else ''}\n"
                    f"🛡 {TYPE_NAMES.get(data.get('insurance_type'), '?')}\n"
                    f"⏳ {DURATION_NAMES.get(data.get('duration'), '?')}\n"
                    f"💰 {data.get('price', 0):,} so'm\n"
                    f"🎁 Bonus: {data.get('bonus', 0):,} so'm"
                )

            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"phone topic notify failed: {e}", exc_info=True)

    await state.clear()

    user_text = (
        "✅ <b>Nasiya so'rovi qabul qilindi!</b>\n\n"
        "<blockquote>"
        "📋 Operator Uzum Nasiya orqali rasmiylashtirish\n"
        "uchun siz bilan bog'lanadi.\n\n"
        "⏳ 5-10 daqiqa ichida"
        "</blockquote>"
    ) if is_nasiya else (
        "✅ <b>So'rovingiz qabul qilindi!</b>\n\n"
        "<blockquote>"
        "⏳ Operator 5-10 daqiqa ichida bog'lanadi"
        "</blockquote>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_main_menu")]
        ]
    )

    await message.answer(user_text, reply_markup=kb, parse_mode="HTML")