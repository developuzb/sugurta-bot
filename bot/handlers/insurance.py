from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram import Router
router = Router()
from states.insurance import InsuranceState
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
import re  
class DeliveryState(StatesGroup):
    full_name = State()
    address = State()
    index = State()
    phone = State()
from database.db import save_temp_order
from database.db import get_temp_order
from keyboards.reply import main_menu
from database.db import get_topic, save_user
from database.db import get_user_by_topic
from config import GROUP_ID
import logging

def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None

from database.db import init_db
logger = logging.getLogger(__name__)


PRICES = {
    "yengil": {"toshkent": {"limited": 192000, "unlimited": 384000},
               "viloyat": {"limited": 160000, "unlimited": 320000}},
    "yuk": {"toshkent": {"limited": 336000, "unlimited": 672000},
            "viloyat": {"limited": 280000, "unlimited": 560000}},
    "bus": {"toshkent": {"limited": 384000, "unlimited": 768000},
            "viloyat": {"limited": 320000, "unlimited": 640000}},
    "other": {"toshkent": {"limited": 72000, "unlimited": 144000},
              "viloyat": {"limited": 60000, "unlimited": 120000}}
}


# ─── YORDAMCHI: avtomobil tanlash ekranini ko'rsatish ───────────────────────
async def show_vehicle_screen(target, state: FSMContext):
    """target — callback yoki message ob'ekti"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚗 Yengil", callback_data="vehicle_yengil"),
                InlineKeyboardButton(text="🚚 Yuk", callback_data="vehicle_yuk")
            ],
            [
                InlineKeyboardButton(text="🚌 Avtobus", callback_data="vehicle_bus"),
                InlineKeyboardButton(text="🏍 Boshqa", callback_data="vehicle_other")
            ]
        ]
    )
    msg = target.message if hasattr(target, "message") else target
    await msg.answer_photo(
        photo="AgACAgIAAxkBAAIBcWnzj9Za0sMlpaLPtjnUpFQvqMqnAAJOGGsb0xKZS80sDfgQQ7SAAQADAgADeQADOwQ",
        caption=(
            "<b>🚗 Qanday turdagi avtomobil minasiz?</b>\n\n"
            "Sug'urta narxi transport turiga qarab farq qiladi.\n"
            "Mos variantni tanlang 👇"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InsuranceState.vehicle)


# ─── YORDAMCHI: hudud tanlash ekranini ko'rsatish ───────────────────────────
async def show_region_screen(msg, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏙 Toshkent", callback_data="region_toshkent")],
            [InlineKeyboardButton(text="🌍 Viloyat", callback_data="region_viloyat")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_vehicle")]
        ]
    )
    await msg.answer_photo(
        photo="AgACAgIAAxkBAAIBeGnzlEniA3L3h7ksujidC7TD0wLEAAJiGGsb0xKZS4_eNvA9GxwhAQADAgADeQADOwQ",
        caption=(
            "<b>📍 Avtomobil qayerda ro'yxatdan o'tgan?</b>\n\n"
            "Bu orqali sug'urta narxi\n"
            "va bonusni aniq hisoblaymiz 💰\n\n"
            "Hududni tanlang 👇"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InsuranceState.region)


# ─── YORDAMCHI: sug'urta turi ekranini ko'rsatish ───────────────────────────
async def show_type_screen(msg, state: FSMContext, back_target: str):
    """back_target: orqaga qaytganda qaysi callback ishga tushadi"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 VIP sug'urta", callback_data="type_unlimited")],
            [InlineKeyboardButton(text="🚗 Oddiy sug'urta", callback_data="type_limited")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_target)]
        ]
    )
    await msg.answer_photo(
        photo="AgACAgIAAxkBAAIBdmnzlDESA8DMMrHYRrPaBCJiMNP1AAJhGGsb0xKZS7THMgU8dsh9AQADAgADeQADOwQ",
        caption=(
            "<b>🛡 Sug'urta turini tanlang</b>\n\n"
            "👑 VIP — istalgan haydovchi mumkin\n"
            "🎁 Bonus mavjud\n\n"
            "🚗 Oddiy — 1–5 haydovchi\n"
            "💰 Arzonroq variant\n\n"
            "Sizga mos variantni tanlang 👇"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InsuranceState.insurance_type)


# ─── YORDAMCHI: muddat ekranini ko'rsatish ──────────────────────────────────
async def show_duration_screen(msg, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ 20 kun", callback_data="dur_20")],
            [InlineKeyboardButton(text="📅 6 oy", callback_data="dur_6")],
            [InlineKeyboardButton(text="🛡 1 yil (tavsiya etiladi)", callback_data="dur_12")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_type")]
        ]
    )
    await msg.answer(
        "<b>⏳ Sug'urta muddatini tanlang</b>\n\n"
        "<blockquote>🛡 <b>1 yil</b> (tavsiya etiladi)\nQulay, qayta rasmiylashtirish shart emas\n</blockquote>\n\n"
        "<blockquote>📅 <b>6 oy</b>\nO'rtacha variant\n</blockquote>\n\n"
        "<blockquote>⚡ <b>20 kun</b>\nQisqa muddatli, vaqtinchalik\n</blockquote>\n\n"
        "Qaysi muddat sizga mos? 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InsuranceState.duration)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: bonus_info
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bonus")
async def bonus_info(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Sug'urtalashni boshlash", callback_data="start_insurance")],
            [InlineKeyboardButton(text="🎁 Bonusni hisoblash", callback_data="calc_bonus")]
        ]
    )
    await callback.message.answer(
        "<b>🎁 Bonus tizimi qanday ishlaydi?</b>\n\n"
        "<blockquote>💰 Sug'urta rasmiylashtirilgandan so'ng\nsizga bonus puli hisoblanadi</blockquote>\n\n"
        "<blockquote>⚡ Bonus 10 daqiqa ichida\nkartangizga o'tkazib beriladi</blockquote>\n\n"
        "<blockquote>🔒 Barcha jarayon xavfsiz va kafolatlangan</blockquote>\n\n"
        "<b>Ko'pchilik shu orqali foyda qilmoqda</b> 🚀\n\n"
        "Davom etish uchun tanlang 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: calc_bonus_redirect
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "calc_bonus")
async def calc_bonus_redirect(callback: types.CallbackQuery, state: FSMContext):
    await start_insurance(callback, state)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: start_insurance  →  1-qadam: avtomobil turi
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "start_insurance")
async def start_insurance(callback: types.CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        topic_id = await get_topic(user_id)

        if not topic_id:
            topic = await callback.bot.create_forum_topic(
                chat_id=GROUP_ID,
                name=f"{callback.from_user.full_name} | {user_id}"
            )
            topic_id = topic.message_thread_id
            await save_user(user_id, topic_id)   # ✅ bazaga saqlash

        await callback.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="🚀 Sug'urta jarayoni boshlandi"
        )

        await show_vehicle_screen(callback, state)
        await callback.answer()

    except Exception as e:
        logger.error(f"Start insurance error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORQAGA: vehicle ekraniga qaytish
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_vehicle")
async def back_to_vehicle(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_vehicle_screen(callback, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_vehicle error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: choose_vehicle  →  2-qadam: hudud
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.vehicle, F.data.startswith("vehicle_"))
async def choose_vehicle(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        vehicle = callback.data.split("_")[1]

        vehicle_names = {
            "yengil": "🚗 Yengil avtomobil",
            "yuk": "🚚 Yuk avtomobili",
            "bus": "🚌 Avtobus",
            "other": "🏍 Boshqa"
        }
        await callback.message.answer(f"{vehicle_names.get(vehicle, vehicle)} tanlandi")
        await state.update_data(vehicle=vehicle)

        topic_id = await get_topic(user_id)
        if topic_id:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🚗 Vehicle: {vehicle}"
            )

        await show_region_screen(callback.message, state)
        await callback.answer()

    except Exception as e:
        logger.error(f"Vehicle error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORQAGA: region ekraniga qaytish
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_region")
async def back_to_region(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_region_screen(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_region error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: choose_region  →  3-qadam: sug'urta turi (yoki viloyat tanlash)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.region, F.data.startswith("region_"))
async def choose_region(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        region = callback.data.split("_")[1]

        region_names = {"toshkent": "🏙 Toshkent", "viloyat": "🌍 Viloyat"}
        await callback.message.answer(f"{region_names.get(region, region)} tanlandi")
        await state.update_data(region=region)

        topic_id = await get_topic(user_id)
        if topic_id:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"📍 Region: {region}"
            )

        if region == "toshkent":
            await show_type_screen(callback.message, state, back_target="back_to_region")
        else:
            regions = [
                (" 01 | Toshkent sh.", "toshkent_city"),
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
                (" 95 | Qoraqalpog'iston", "qq")
            ]
            buttons = [
                InlineKeyboardButton(text=name, callback_data=f"sub_{code}")
                for name, code in regions
            ]
            kb = InlineKeyboardMarkup(
                inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)]
                + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_region")]]
            )
            await callback.message.answer(
                "🌍 <b>Viloyatingizni tanlang:</b>",
                reply_markup=kb,
                parse_mode="HTML"
            )
            await state.set_state(InsuranceState.subregion)

        await callback.answer()

    except Exception as e:
        logger.error(f"Region error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORQAGA: subregion ekraniga qaytish (viloyat ro'yxatiga)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_subregion")
async def back_to_subregion(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        regions = [
            (" 01 | Toshkent sh.", "toshkent_city"),
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
            (" 95 | Qoraqalpog'iston", "qq")
        ]
        buttons = [
            InlineKeyboardButton(text=name, callback_data=f"sub_{code}")
            for name, code in regions
        ]
        kb = InlineKeyboardMarkup(
            inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)]
            + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_region")]]
        )
        await callback.message.answer(
            "🌍 <b>Viloyatingizni tanlang:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await state.set_state(InsuranceState.subregion)
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_subregion error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: choose_subregion  →  sug'urta turi
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.subregion, F.data.startswith("sub_"))
async def choose_subregion(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        sub = callback.data.split("_")[1]

        await callback.message.answer(f"🌍 Tanlandi: {sub}")
        await state.update_data(region="viloyat", subregion=sub)

        topic_id = await get_topic(user_id)
        if topic_id:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🌍 Subregion: {sub}"
            )

        await show_type_screen(callback.message, state, back_target="back_to_subregion")
        await callback.answer()

    except Exception as e:
        logger.error(f"Subregion error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORQAGA: type ekraniga qaytish
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_type")
async def back_to_type(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        # viloyat yoki toshkent ekanligiga qarab orqaga tugmani belgilaymiz
        if data.get("subregion"):
            back_target = "back_to_subregion"
        else:
            back_target = "back_to_region"
        await show_type_screen(callback.message, state, back_target=back_target)
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_type error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: choose_type  →  muddat tanlash
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.insurance_type, F.data.startswith("type_"))
async def choose_type(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        insurance_type = "unlimited" if callback.data == "type_unlimited" else "limited"
        await state.update_data(insurance_type=insurance_type)

        await show_duration_screen(callback.message, state)
        await callback.answer()

    except Exception as e:
        logger.error(f"Type error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORQAGA: duration ekraniga qaytish
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_duration")
async def back_to_duration(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_duration_screen(callback.message, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"back_to_duration error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: final_calc  →  natija
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(InsuranceState.duration, F.data.startswith("dur_"))
async def final_calc(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        data = await state.get_data()

        duration_map = {"dur_20": 0.2, "dur_6": 0.7, "dur_12": 1.0}
        coef = duration_map.get(callback.data, 1.0)

        base_price = PRICES[data["vehicle"]][data["region"]][data["insurance_type"]]
        price = int(base_price * coef)

        bonus_percent = 0.05 if data["region"] == "toshkent" else 0.25
        bonus = int(price * bonus_percent)

        await state.update_data(price=price, bonus=bonus)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Davom etish", callback_data="continue")],
                [InlineKeyboardButton(text="💳 30 kun 0% nasiya", callback_data="nasiya_info")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_duration")],
                [InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="restart")]
            ]
        )

        await callback.message.answer(
            f"💰 Narx: {price:,} so'm\n"
            f"🎁 Bonus: {bonus:,} so'm\n\n"
            "🔥 Davom etamizmi?",
            reply_markup=kb
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Final calc error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: ask_phone
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "continue")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("📞 Raqamingizni yozing:\n+998XXXXXXXXX")
        await state.set_state(InsuranceState.phone)
        await callback.answer()
    except Exception as e:
        logger.error(f"Phone ask error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: restart
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "restart")
async def restart_calc(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_vehicle_screen(callback, state)
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION: receive_phone
# ─────────────────────────────────────────────────────────────────────────────

kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📲 Raqamni yuborish", callback_data="send_contact")]
    ]
)

@router.callback_query(F.data == "send_contact")
async def request_contact(callback: types.CallbackQuery):
    await callback.message.answer(
        "📞 Iltimos, raqamingizni yozib yuboring:\n\nMasalan: +998901234567"
    )
    await callback.answer()


from aiogram import Bot
from config import GROUP_ID
from datetime import datetime
from aiogram import types
from aiogram import Router


@router.message(InsuranceState.phone)
async def receive_phone(message: types.Message, state: FSMContext, bot: Bot):
    raw_phone = message.text.strip()
    phone = normalize_phone(raw_phone)

    if not phone:
        await message.answer(
            "❗ Telefon noto'g'ri\n\n"
            "To'g'ri formatlar:\n"
            "+998901234567\n"
            "901234567\n"
            "90 123 45 67"
        )
        return

    data = await state.get_data()
    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=f"📞 Telefon: {phone}"
        )

    await message.answer("✅ So'rovingiz qabul qilindi!")
    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

@router.message(StateFilter("help_mode"), F.text)
async def forward_to_operator(message: types.Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state != "help_mode":
        return

    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=f"💬 Yangi savol\n\n👤 {message.from_user.full_name}\n📝 {message.text}"
        )

    await message.answer("✅ Savolingiz yuborildi")
    await state.clear()


@router.callback_query(F.data == "help_mode")
async def help_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Operator bilan bog'lanish", callback_data="help_operator")],
            [InlineKeyboardButton(text="💬 Savol yozish", callback_data="help_write")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="help_back")]
        ]
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await callback.message.answer_photo(
        photo="AgACAgIAAyEFAASY9hCdAAID_Wn3ikpf-SSsxEH3MFlAs0RGVWa8AAKQF2sb8a3AS-nPdtz6uB2oAQADAgADeQADOwQ",
        caption="<b>❓ Yordam</b>\n\nQuyidagilardan birini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# POCHTA (admin)
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "/pochta", F.chat.type.in_({"group", "supergroup"}))
async def admin_pochta_command(message: types.Message, bot: Bot):
    thread_id = message.message_thread_id
    if not thread_id:
        return

    user_id = await get_user_by_topic(thread_id)
    if not user_id:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Foydalanish", callback_data="start_delivery")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_delivery")]
        ]
    )
    await bot.send_photo(
        chat_id=user_id,
        photo="AgACAgIAAyEFAASY9hCdAAID62n3hXYlmg9gNC7Js07c_Jsbt4o7AAJcF2sb8a3AS6_KLsVXwhGEAQADAgADeQADOwQ",
        caption=(
            "<b>📦 Sug'urtani yetkazib berish xizmati</b>\n\n"
            "Sug'urtangizni pochta orqali olishni xohlaysizmi?"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await message.answer("📦 Pochta xizmati taklif qilindi")


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERY
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "start_delivery")
async def user_accept_delivery(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📥 Mijoz yetkazib berishni tanladi"
        )

    await callback.message.answer(
        "📦 Polisni siz uchun tayyorlab, uyingizgacha yetkazib beramiz 😊\n\n"
        "Agar ma'qul bo'lsa, ismingizni yuboring 👇"
    )
    await state.set_state(DeliveryState.full_name)
    await callback.answer()


@router.callback_query(F.data == "cancel_delivery")
async def user_cancel_delivery(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="❌ Mijoz yetkazib berishni rad etdi"
        )
    await callback.message.answer("❌ Bekor qilindi")
    await callback.answer()


@router.message(DeliveryState.full_name)
async def get_name(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 3:
        await message.answer("❗ Ism noto'g'ri")
        return

    await state.update_data(full_name=message.text.strip())

    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="👤 Ism kiritdi"
        )

    await message.answer(
        "📍 Manzil:\nViloyat, tuman, ko'cha\n\nMasalan: Toshkent, Chilonzor, 12-mavze"
    )
    await state.set_state(DeliveryState.address)


@router.message(DeliveryState.address)
async def get_address(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 5:
        await message.answer("❗ Manzil to'liq emas")
        return

    await state.update_data(address=message.text.strip())

    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📍 Manzil kiritdi"
        )
    await message.answer("📮 Index (yo'q bo'lsa 0 yozing)")
    await state.set_state(DeliveryState.index)


@router.message(DeliveryState.index)
async def get_index(message: types.Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.answer("❗ Faqat raqam kiriting")
        return

    await state.update_data(index=message.text)

    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📮 Index kiritdi"
        )
    await message.answer("📞 Telefon: +998901234567")
    await state.set_state(DeliveryState.phone)


@router.message(DeliveryState.phone)
async def get_phone(message: types.Message, state: FSMContext, bot: Bot):
    phone = message.text.strip()

    if not re.match(r"^\+998\d{9}$", phone):
        await message.answer("❗ Telefon noto'g'ri")
        return

    data = await state.get_data()
    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📞 Telefon kiritdi"
        )

    text = (
        f"📦 <b>YETKAZIB BERISH MA'LUMOTI</b>\n\n"
        f"👤 Ism: {data.get('full_name')}\n"
        f"📍 Manzil: {data.get('address')}\n"
        f"📮 Index: {data.get('index')}\n"
        f"📞 Telefon: {phone}"
    )

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML"
        )

    await message.answer("✅ Ma'lumotlar yuborildi")
    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
# HELP tugmalari
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help_operator")
async def help_operator(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📞 Mijoz yordam so'radi"
        )
    await callback.message.answer(
        "📞 Operator siz bilan tez orada bog'lanadi. "
        "Istasangiz telefon raqamingizni yuboring. biz sizga qo'ng'iroq qilamiz"
    )
    await callback.answer()


@router.callback_query(F.data == "help_write")
async def help_write(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state("help_mode")
    await callback.message.answer("💬 Savolingizni yozing, operatorga yuboramiz")
    await callback.answer()


@router.callback_query(F.data == "help_back")
async def help_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()
