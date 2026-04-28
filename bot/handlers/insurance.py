from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
from database.db import get_topic
from database.db import get_user_by_topic
from config import GROUP_ID
import logging

def normalize_phone(phone: str) -> str | None:
    # faqat raqamlarni qoldiramiz
    digits = re.sub(r"\D", "", phone)

    # 998 bilan boshlansa
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"

    # 9 xonali bo‘lsa (masalan: 770097171)
    if len(digits) == 9:
        return f"+998{digits}"

    return None

# BOT START OLDIN QO‘SH
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

# FUNCTION: bonus_info

@router.callback_query(F.data == "bonus")
async def bonus_info(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Sug‘urtalashni boshlash", callback_data="start_insurance")],
            [InlineKeyboardButton(text="🎁 Bonusni hisoblash", callback_data="calc_bonus")]
        ]
    )

    await callback.message.answer(
        "<b>🎁 Bonus tizimi qanday ishlaydi?</b>\n\n"

        "<blockquote>"
        "💰 Sug‘urta rasmiylashtirilgandan so‘ng\n"
        "sizga bonus puli hisoblanadi"
        "</blockquote>\n\n"

        "<blockquote>"
        "⚡ Bonus 10 daqiqa ichida\n"
        "kartangizga o‘tkazib beriladi"
        "</blockquote>\n\n"

        "<blockquote>"
        "🔒 Barcha jarayon xavfsiz va kafolatlangan"
        "</blockquote>\n\n"

        "<b>Ko‘pchilik shu orqali foyda qilmoqda</b> 🚀\n\n"

        "Davom etish uchun tanlang 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await callback.answer()


# FUNCTION: calc_bonus_redirect

@router.callback_query(F.data == "calc_bonus")
async def calc_bonus_redirect(callback: types.CallbackQuery, state: FSMContext):
    await start_insurance(callback, state)
    
@router.callback_query(F.data == "start_insurance")
async def start_insurance(callback: types.CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id

        # topic olish
        topic_id = await get_topic(user_id)

        # agar yo‘q bo‘lsa yaratamiz
        if not topic_id:
            topic = await callback.bot.create_forum_topic(
                chat_id=GROUP_ID,
                name=f"{callback.from_user.full_name} | {user_id}"
            )
            topic_id = topic.message_thread_id
            await save_user(user_id, topic_id)

        # ACTION LOG
        await callback.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="🚀 Sug‘urta jarayoni boshlandi"
        )

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

        await callback.message.answer_photo(
            photo="AgACAgIAAxkBAAIB02nwyJS8Z5nBrqux9RvRERu0ci_yAAIRF2sbraiASx2wMx5AAAH_2wEAAwIAA3kAAzsE",

            caption=
                "<b>🚗 Qanday turdagi avtomobil minasiz?</b>\n\n"

                "Sug‘urta narxi transport turiga qarab farq qiladi.\n"
                "Mos variantni tanlang 👇",

            reply_markup=kb,
            parse_mode="HTML"
        )       
        await state.set_state(InsuranceState.vehicle)

        await callback.answer()

    except Exception as e:
        logger.error(f"Start insurance error: {e}", exc_info=True)
                                
# FUNCTION: choose_vehicle

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

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏙 Toshkent", callback_data="region_toshkent")],
                [InlineKeyboardButton(text="🌍 Viloyat", callback_data="region_viloyat")]
            ]
        )

        await callback.message.answer_photo(
            photo="AgACAgIAAxkBAAIB5WnwyxwDoD6LjfhSECfNK34m040_AAIrF2sbraiAS5ynxB-23dzNAQADAgADeQADOwQ",

            caption=(
                "<b>📍 Avtomobil qayerda ro‘yxatdan o‘tgan?</b>\n\n"

                "Bu orqali sug‘urta narxi\n"
                "va bonusni aniq hisoblaymiz 💰\n\n"

                "Hududni tanlang 👇"
            ),

            reply_markup=kb,
            parse_mode="HTML"
        )
        await state.set_state(InsuranceState.region)

        await callback.answer()

    except Exception as e:
        logger.error(f"Vehicle error: {e}", exc_info=True)
                       
# FUNCTION: choose_region

@router.callback_query(InsuranceState.region, F.data.startswith("region_"))
async def choose_region(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        region = callback.data.split("_")[1]

        region_names = {
            "toshkent": "🏙 Toshkent",
            "viloyat": "🌍 Viloyat"
        }

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
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="👥 VIP sug'urta", callback_data="type_unlimited")],
                    [InlineKeyboardButton(text="👤 ODDIY sug'urta", callback_data="type_limited")]
                ]
            )

            await callback.message.answer(
                "<b>🚗 Sug‘urta turini tanlang</b>\n\n"

                "<blockquote>"
                "👑 <b>VIP sug‘urta</b>\n"
                "Istalgan haydovchi mumkin\n"
                "🎁 Bonus mavjud\n"
                "</blockquote>\n\n"

                "<blockquote>"
                "🚗 <b>Oddiy sug‘urta</b>\n"
                "1–5 ta haydovchi\n"
                "💰 Arzonroq variant\n"
                "</blockquote>\n\n"

                "Qaysi biri sizga mos? 👇",
                reply_markup=kb,
                parse_mode="HTML"
            )
            await state.set_state(InsuranceState.insurance_type)

        else:
            regions = [
                (" 01 | Toshkent sh.", "toshkent_city"),
                (" 10 | Toshkent vil.", "toshkent_vil"),
                (" 20 | Sirdaryo", "sirdaryo"),
                (" 25 | Jizzax", "jizzax"),
                (" 30 | Samarqand", "samarqand"),
                (" 40 | Farg‘ona", "fargona"),
                (" 50 | Namangan", "namangan"),
                (" 60 | Andijon", "andijon"),
                (" 70 | Qashqadaryo", "qashqadaryo"),
                (" 75 | Surxondaryo", "surxondaryo"),
                (" 80 | Buxoro", "buxoro"),
                (" 85 | Navoiy", "navoiy"),
                (" 90 | Xorazm", "xorazm"),
                (" 95 | Qoraqalpog‘iston", "qq")
            ]

            buttons = [
                InlineKeyboardButton(text=name, callback_data=f"sub_{code}")
                for name, code in regions
            ]

            kb = InlineKeyboardMarkup(
                inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)]
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
                        
# FUNCTION: choose_subregion

@router.callback_query(InsuranceState.subregion, F.data.startswith("sub_"))
async def choose_subregion(callback: types.CallbackQuery, state: FSMContext):
    try:
        # eski tugmani o‘chiramiz
        await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        sub = callback.data.split("_")[1]

        # userga feedback
        await callback.message.answer(f"🌍 Tanlandi: {sub}")

        # state update
        await state.update_data(region="viloyat", subregion=sub)

        # topic log
        topic_id = await get_topic(user_id)
        if topic_id:
            await callback.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic_id,
                text=f"🌍 Subregion: {sub}"
            )

        # 🔥 BU YERDA region tekshirish kerak emas (allaqachon viloyat)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👑 VIP sug'urta", callback_data="type_unlimited")],
                [InlineKeyboardButton(text="🚗 Oddiy sug'urta", callback_data="type_limited")]
            ]
        )

        await callback.message.answer(
            "<b>🚗 Sug‘urta turini tanlang</b>\n\n"

            "<blockquote>"
            "👑 <b>VIP sug‘urta</b>\n"
            "Istalgan haydovchi mumkin\n"
            "🎁 Bonus mavjud\n"
            "</blockquote>\n\n"

            "<blockquote>"
            "🚗 <b>Oddiy sug‘urta</b>\n"
            "1–5 ta haydovchi\n"
            "💰 Arzonroq variant\n"
            "</blockquote>\n\n"

            "Qaysi biri sizga mos? 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )

        await state.set_state(InsuranceState.insurance_type)
        await callback.answer()

    except Exception as e:
        logger.error(f"Subregion error: {e}", exc_info=True)

@router.callback_query(InsuranceState.insurance_type, F.data.startswith("type_"))
async def choose_type(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        insurance_type = "unlimited" if callback.data == "type_unlimited" else "limited"

        await state.update_data(insurance_type=insurance_type)

        # 🔥 duration tanlash
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚡ 20 kun", callback_data="dur_20")],
                [InlineKeyboardButton(text="📅 6 oy", callback_data="dur_6")],
                [InlineKeyboardButton(text="🛡 1 yil (tavsiya etiladi)", callback_data="dur_12")]
            ]
        )

        await callback.message.answer(
            "<b>⏳ Sug‘urta muddatini tanlang</b>\n\n"

            "<blockquote>"
            "🛡 <b>1 yil</b> (tavsiya etiladi)\n"
            "Qulay, qayta rasmiylashtirish shart emas\n"
            "</blockquote>\n\n"

            "<blockquote>"
            "📅 <b>6 oy</b>\n"
            "O‘rtacha variant\n"
            "</blockquote>\n\n"

            "<blockquote>"
            "⚡ <b>20 kun</b>\n"
            "Qisqa muddatli, vaqtinchalik\n"
            "</blockquote>\n\n"

            "Qaysi muddat sizga mos? 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )

        await state.set_state(InsuranceState.duration)
        await callback.answer()

    except Exception as e:
        logger.error(f"Type error: {e}", exc_info=True)
        
# FUNCTION: final_calc
@router.callback_query(InsuranceState.duration, F.data.startswith("dur_"))
async def final_calc(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)

        data = await state.get_data()

        # 🔹 duration
        duration_map = {
            "dur_20": 0.2,
            "dur_6": 0.7,
            "dur_12": 1.0
        }

        coef = duration_map.get(callback.data, 1.0)

        # 🔹 base price
        base_price = PRICES[data["vehicle"]][data["region"]][data["insurance_type"]]

        price = int(base_price * coef)

        # 🔹 bonus (region asosida)
        if data["region"] == "toshkent":
            bonus_percent = 0.05
        else:
            bonus_percent = 0.25

        bonus = int(price * bonus_percent)

        await state.update_data(price=price, bonus=bonus)

        # 🔥 tugmalar
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Davom etish", callback_data="continue")],
                [InlineKeyboardButton(text="🔄 Qayta hisoblash", callback_data="restart")]
            ]
        )

        await callback.message.answer(
            f"""💰 Narx: {price:,} so‘m
🎁 Bonus: {bonus:,} so‘m

🔥 Davom etamizmi?""",
            reply_markup=kb
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Final calc error: {e}", exc_info=True)
                                                
@router.callback_query(F.data == "continue")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("📞 Raqamingizni yozing:\n+998XXXXXXXXX")
        await state.set_state(InsuranceState.phone)
        await callback.answer()

    except Exception as e:
        logger.error(f"Phone ask error: {e}", exc_info=True)

@router.callback_query(F.data == "restart")
async def restart_calc(callback: types.CallbackQuery, state: FSMContext):

    await state.clear()

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

    await callback.message.answer(
        "🚗 10 soniyada sug‘urta narxini hisoblang\n"
        "🎁 Sizga qaytadigan bonusni ham ko‘ring\n\n"
        "Qaysi avtomobil uchun? 👇",
        reply_markup=kb
    )
    await state.set_state(InsuranceState.vehicle)

    await callback.answer()

# ❌ ESKI (o‘chiriladi)
# kb = types.ReplyKeyboardMarkup(
#     keyboard=[[types.KeyboardButton(
#         text="📲 Raqamni yuborish",
#         request_contact=True
#     )]],
#     resize_keyboard=True
# )


# ✅ YANGI — inline tugma
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

from database.db import get_topic, save_user
from aiogram import Bot
from config import GROUP_ID
from datetime import datetime

from aiogram import types

# bot instance olish (aiogram 3)
from aiogram import Router

# FUNCTION: forward_to_operator (FIXED)

@router.message(InsuranceState.phone)
async def receive_phone(message: types.Message, state: FSMContext, bot: Bot):
    raw_phone = message.text.strip()

    phone = normalize_phone(raw_phone)

    if not phone:
        await message.answer(
            "❗ Telefon noto‘g‘ri\n\n"
            "To‘g‘ri formatlar:\n"
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

    await message.answer("✅ So‘rovingiz qabul qilindi!")
    await state.clear()



@router.message(F.chat.type == "private", F.text)
async def forward_to_operator(message: types.Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()

    # ❗ faqat help_mode da ishlasin
    if current_state != "help_mode":
        return

    user_id = message.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=f"""
💬 <b>Yangi savol</b>

👤 {message.from_user.full_name}
🆔 {user_id}

📝 {message.text}
""",
            parse_mode="HTML"
        )

    await message.answer("✅ Savolingiz yuborildi")
    await state.clear()

@router.callback_query(F.data == "help_mode")
async def help_inline(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Operator bilan bog‘lanish", callback_data="help_operator")],
            [InlineKeyboardButton(text="💬 Savol yozish", callback_data="help_write")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="help_back")]
        ]
    )

    await callback.message.answer(
        "<b>❓ Yordam</b>\n\nQuyidagilardan birini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await callback.answer()

@router.message(InsuranceState.phone)
async def receive_phone(message: types.Message, state: FSMContext, bot: Bot):
    raw_phone = message.text.strip()

    phone = normalize_phone(raw_phone)

    if not phone:
        await message.answer(
            "❗ Telefon noto‘g‘ri\n\n"
            "To‘g‘ri formatlar:\n"
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

    await message.answer("✅ So‘rovingiz qabul qilindi!")
    await state.clear()
            
# FUNCTION: admin_pochta_command

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

    await bot.send_message(
        chat_id=user_id,
        text="<b>📦 Sug‘urtani yetkazib berish xizmati</b>\n\nSug‘urtangizni pochta orqali olishni xohlaysizmi?",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await message.answer(
        "📦 Pochta xizmati taklif qilindi",
        message_thread_id=thread_id
    )

# FUNCTION: user_accept_delivery

@router.callback_query(F.data == "start_delivery")
async def user_accept_delivery(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
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
        "Agar ma’qul bo‘lsa, ismingizni yuboring 👇"
    )

    await state.set_state(DeliveryState.full_name)
    await callback.answer()

# FUNCTION: user_cancel_delivery

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
               
# FUNCTION: get_name (FULL WITH LOG)

@router.message(DeliveryState.full_name)
async def get_name(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 3:
        await message.answer("❗ Ism noto‘g‘ri")
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
        "📍 Manzil:\n"
        "Viloyat, tuman, ko‘cha\n\n"
        "Masalan: Toshkent, Chilonzor, 12-mavze"
    )
    await state.set_state(DeliveryState.address)
    
    
# FUNCTION: get_address (FULL WITH LOG)

@router.message(DeliveryState.address)
async def get_address(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 5:
        await message.answer("❗ Manzil to‘liq emas")
        return

    await state.update_data(address=message.text.strip())

    topic_id = await get_topic(message.from_user.id)
    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📍 Manzil kiritdi"
        )

    await message.answer("📮 Index (yo‘q bo‘lsa 0 yozing)")
    await state.set_state(DeliveryState.index)
    
# FUNCTION: get_index (FULL WITH LOG)

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

# FUNCTION: get_phone (FULL WITH LOG)

@router.message(DeliveryState.phone)
async def get_phone(message: types.Message, state: FSMContext, bot: Bot):
    phone = message.text.strip()

    if not re.match(r"^\+998\d{9}$", phone):
        await message.answer("❗ Telefon noto‘g‘ri")
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

    text = f"""
📦 <b>YETKAZIB BERISH MA’LUMOTI</b>

👤 Ism: {data.get("full_name")}
📍 Manzil: {data.get("address")}
📮 Index: {data.get("index")}
📞 Telefon: {phone}
"""

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML"
        )

    await message.answer("✅ Ma’lumotlar yuborildi")
    await state.clear()
    
@router.message(F.text == "❓ Yordam", F.chat.type == "private")
async def help_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Operator bilan bog‘lanish", callback_data="help_operator")],
            [InlineKeyboardButton(text="💬 Savol yozish", callback_data="help_write")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="help_back")]
        ]
    )

    await message.answer(
        "<b>❓ Yordam</b>\n\nQuyidagilardan birini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )    

@router.callback_query(F.data == "help_operator")
async def help_operator(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    topic_id = await get_topic(user_id)

    if topic_id:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text="📞 Mijoz yordam so‘radi"
        )

    await callback.message.answer("📞 Operator siz bilan tez orada bog‘lanadi. Istasangiz telefon raqamingizni yuboring. biz sizga qo'ng'iroq qilamiz")
    await callback.answer()        

@router.callback_query(F.data == "help_write")
async def help_write(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state("help_mode")

    await callback.message.answer(
        "💬 Savolingizni yozing, operatorga yuboramiz"
    )
    await callback.answer()    

    
@router.callback_query(F.data == "help_back")
async def help_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()    