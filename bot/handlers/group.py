from aiogram import Router, F, types
from datetime import datetime, timedelta
import logging
logger = logging.getLogger(__name__)
from config import GROUP_ID
from database.db import get_user
from PIL import Image, ImageDraw, ImageFont
import os


router = Router()

waiting_for_check = set()

def generate_invoice_image(amount, deadline):
    from PIL import Image, ImageDraw, ImageFont
    from datetime import datetime
    import uuid

    W, H = 1080, 1800
    img = Image.new("RGB", (W, H), "#F5F7FB")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("bot/fonts/Inter-Bold.ttf", 74)
        font_big = ImageFont.truetype("bot/fonts/Inter-Bold.ttf", 118)
        font_bold = ImageFont.truetype("bot/fonts/Inter-Bold.ttf", 52)
        font = ImageFont.truetype("bot/fonts/Inter-Regular.ttf", 42)
        font_small = ImageFont.truetype("bot/fonts/Inter-Regular.ttf", 34)
    except:
        font_title = font_big = font_bold = font = font_small = ImageFont.load_default()

    def card(x1,y1,x2,y2,r,color):
        draw.rounded_rectangle(
            (x1,y1,x2,y2),
            radius=r,
            fill=color
        )

    y=70

    # HEADER
    draw.text(
        (70,y),
        "🛡 Sug'urta To'lovi",
        font=font_title,
        fill="#0F172A"
    )

    card(650,y,1010,y+85,30,"#FEF3C7")
    draw.text(
        (700,y+18),
        "⏳ Kutilmoqda",
        font=font_small,
        fill="#92400E"
    )

    y += 150

    # BLUE CARD
    card(60,y,1020,y+340,48,"#1D4ED8")

    draw.text(
        (110,y+70),
        "💳 5614 6861 0182 0184",
        font=font_bold,
        fill="white"
    )

    draw.text(
        (110,y+160),
        "NURZOD NORQULOV",
        font=font,
        fill="#DBEAFE"
    )

    draw.text(
        (110, y+235),
        "Xavfsiz to'lov tizimi",
        font=font_small,
        fill="#BFDBFE"
    )

    y += 410

    # AMOUNT CARD
    card(60,y,1020,y+420,48,"white")

    draw.text(
        (110,y+60),
        "💰 To'lov summasi",
        font=font,
        fill="#64748B"
    )

    draw.text(
        (150,y+170),
        f"{amount:,} so'm",
        font=font_big,
        fill="#16A34A"
    )

    draw.text(
        (110,y+315),
        f"⏳ Amal qilish muddati: {deadline}",
        font=font_small,
        fill="#475569"
    )

    y += 500

    # DETAILS CARD
    card(60,y,1020,y+330,48,"white")

    rows = [
        (" Xizmat","Avtosug'urta"),
        (" Paket","VIP sug'urta"),
        (" Muddat","1 yil"),
        (" Bonus","+20 000 so'm")
    ]

    ry = y+50
    for a,b in rows:
        draw.text(
            (110,ry),
            a,
            font=font_small,
            fill="#64748B"
        )
        draw.text(
            (500,ry),
            b,
            font=font_small,
            fill="#111827"
        )
        ry += 65

    y += 390

    # INFO CARD
    card(60,y,1020,y+240,48,"#ECFDF5")

    tx = str(uuid.uuid4())[:8].upper()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    draw.text(
        (110,y+55),
        f"🧾 Invoice ID: {tx}",
        font=font,
        fill="#065F46"
    )

    draw.text(
        (110,y+135),
        f"🕒 {now}",
        font=font_small,
        fill="#047857"
    )

    y += 320

    # FOOTER CTA
    card(60,y,1020,y+250,48,"#FFF7ED")

    draw.text(
        (110,y+60),
        "📎 To'lovdan keyin chek yuboring",
        font=font_bold,
        fill="#C2410C"
    )

    draw.text(
        (110,y+145),
        "Tasdiqdan keyin polis yuboriladi",
        font=font_small,
        fill="#7C2D12"
    )

    path = f"invoice_{uuid.uuid4().hex}.png"
    img.save(path)

    return path

@router.callback_query(F.data == "send_check")
async def send_check_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    waiting_for_check.add(user_id)

    await callback.message.answer(
        "📸 Iltimos, to‘lov chekini rasm ko‘rinishida yuboring"
    )
    await callback.answer()


@router.message(F.chat.type == "private", F.photo)
async def receive_check(message: types.Message):
    try:
        user_id = message.from_user.id

        if user_id not in waiting_for_check:
            return

        waiting_for_check.remove(user_id)

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="✅ Qabul qilindi",
                        callback_data=f"approve_{user_id}"
                    ),
                    types.InlineKeyboardButton(
                        text="❌ Soxta chek",
                        callback_data=f"fake_{user_id}"
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="🚫 Bekor qilish",
                        callback_data=f"cancel_{user_id}"
                    )
                ]
            ]
        )

        await message.bot.send_photo(
            chat_id=GROUP_ID,
            photo=message.photo[-1].file_id,
            caption=f"📸 Chek keldi\n👤 {message.from_user.full_name}\n🆔 {user_id}",
            reply_markup=kb
        )

        await message.answer("⏳ Chekingiz tekshirilmoqda")

        logger.info(f"Check received: {user_id}")

    except Exception as e:
        logger.error(f"Receive check error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi")
        
@router.callback_query(F.data.startswith("approve_"))
async def approve_check(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])

        from database.db import update_order_status
        await update_order_status(user_id, 'paid')
        
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n✅ Qabul qilindi"
        )

        await callback.bot.send_message(user_id, "✅ To‘lovingiz qabul qilindi")
        await callback.answer()

        logger.info(f"Payment approved: {user_id}")

    except Exception as e:
        logger.error(f"Approve error: {e}", exc_info=True)
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        
@router.callback_query(F.data.startswith("fake_"))
async def fake_check(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    from database.db import update_order_status
    await update_order_status(user_id, 'rejected')

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n❌ Soxta chek"
    )

    await callback.bot.send_message(user_id, "❌ Chek tasdiqlanmadi")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_check(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n🚫 Bekor qilindi"
    )

    await callback.bot.send_message(user_id, "🚫 Buyurtma bekor qilindi")
    await callback.answer()


@router.message(F.chat.id == GROUP_ID, F.text.startswith("/invoys"))
async def create_invoice(message: types.Message):

    if not message.message_thread_id:
        return

    topic_id = message.message_thread_id
    user_id = await get_user(topic_id)

    if not user_id:
        await message.reply("❌ Mijoz topilmadi")
        return

    try:
        amount = int(message.text.split()[1])
    except:
        await message.reply("❌ Format: /invoys 500000")
        return

    deadline = datetime.now() + timedelta(hours=24)
    deadline_str = deadline.strftime("%d-%m %H:%M")

    # 🔥 RASM GENERATE
    image_path = generate_invoice_image(amount, deadline_str)

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="📸 Chek yuborish",
                callback_data="send_check"
            )]
        ]
    )

    # 🔥 USERGA RASM YUBORISH
    await message.bot.send_photo(
        chat_id=user_id,
        photo=types.FSInputFile(image_path),
        caption="🛡 Sug'urta to'lovi tayyor. Chekni yuborib tasdiqlang.",
        reply_markup=kb
    )

    await message.answer(
        f"💳 Invoys yuborildi\n💰 {amount:,} so‘m\n⏳ {deadline_str}"
    )

    try:
        await message.delete()
    except:
        pass

    from database.db import save_order
    await save_order(user_id, topic_id, amount, "waiting", deadline_str)

    # 🔥 faylni o‘chiramiz (optional)
    try:
        os.remove(image_path)
    except:
        pass