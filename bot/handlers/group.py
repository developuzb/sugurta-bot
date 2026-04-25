from aiogram import Router, F, types
from datetime import datetime, timedelta
import aiosqlite
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
    import random
    from datetime import datetime

    W, H = 720, 1280
    img = Image.new("RGB", (W, H), "#F5F7FB")
    draw = ImageDraw.Draw(img)

    # 🔤 FONT (yuklab qo‘y: fonts/Inter-Bold.ttf, Inter-Regular.ttf)
    try:
        font_bold = ImageFont.truetype("fonts/Inter-Bold.ttf", 48)
        font_big = ImageFont.truetype("fonts/Inter-Bold.ttf", 64)
        font = ImageFont.truetype("fonts/Inter-Regular.ttf", 28)
        font_small = ImageFont.truetype("fonts/Inter-Regular.ttf", 24)
    except:
        font_bold = font_big = font = font_small = ImageFont.load_default()

    def round_rect(x1, y1, x2, y2, r, fill):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=r, fill=fill)

    y = 60

    # 🔵 HEADER
    draw.text((40, y), "💳 To‘lov hisobi", font=font_bold, fill="#1E293B")

    # status badge
    round_rect(420, y, 680, y+50, 20, "#FEF3C7")
    draw.text((440, y+10), "⏳ Kutilmoqda", font=font_small, fill="#92400E")

    y += 100

    # 🟦 CARD (gradient imitation)
    round_rect(40, y, 680, y+220, 30, "#2563EB")

    draw.text((70, y+40), "💳 5614 6861 0182 0184", font=font_bold, fill="white")
    draw.text((70, y+110), "NURZOD NORQULOV", font=font_small, fill="#E0E7FF")

    y += 260

    # 🧾 MAIN BLOCK
    round_rect(40, y, 680, y+260, 30, "white")

    draw.text((70, y+30), "🚗 Xizmat", font=font_small, fill="#64748B")
    draw.text((70, y+70), "Avtomobil sug‘urtasi", font=font, fill="#0F172A")

    draw.text((70, y+120), "💰 Summa", font=font_small, fill="#64748B")
    draw.text((70, y+160), f"{amount:,} so‘m", font=font_big, fill="#16A34A")

    draw.text((70, y+220), f"⏳ {deadline}", font=font_small, fill="#64748B")

    y += 300

    # 🔢 TRANSACTION INFO
    round_rect(40, y, 680, y+160, 30, "white")

    tx_id = random.randint(100000, 999999)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    draw.text((70, y+30), f"🧾 ID: {tx_id}", font=font_small, fill="#334155")
    draw.text((70, y+80), f"🕒 {now}", font=font_small, fill="#334155")

    y += 200

    # ⚠️ FOOTER
    round_rect(40, y, 680, y+140, 30, "#FFF7ED")

    draw.text((70, y+30), "📸 Chekni yuboring", font=font, fill="#C2410C")
    draw.text((70, y+80), "To‘lovdan keyin tasdiqlanadi", font=font_small, fill="#7C2D12")

    path = f"invoice_{amount}.png"
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

        async with aiosqlite.connect("db.sqlite") as db:
            await db.execute("""
                UPDATE orders 
                SET status='paid' 
                WHERE rowid = (
                    SELECT rowid FROM orders 
                    WHERE user_id=? 
                    ORDER BY rowid DESC LIMIT 1
                )
            """, (user_id,))
            await db.commit()

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

    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("""
            UPDATE orders 
            SET status='rejected' 
            WHERE rowid = (
                SELECT rowid FROM orders 
                WHERE user_id=? 
                ORDER BY rowid DESC LIMIT 1
            )
        """, (user_id,))
        await db.commit()

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
        caption="💳 To‘lov uchun invoys tayyor",
        reply_markup=kb
    )

    await message.answer(
        f"💳 Invoys yuborildi\n💰 {amount:,} so‘m\n⏳ {deadline_str}"
    )

    try:
        await message.delete()
    except:
        pass

    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            (user_id, topic_id, amount, "waiting", deadline_str)
        )
        await db.commit()

    # 🔥 faylni o‘chiramiz (optional)
    try:
        os.remove(image_path)
    except:
        pass