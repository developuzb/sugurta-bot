from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from datetime import datetime, timedelta
import logging
import os
import uuid
import asyncio

from config import GROUP_ID
from database.db import (
    get_user, add_pending_check, is_awaiting_check, remove_pending_check,
    save_order, update_order_payment, get_order, update_order_status_by_id,
)
from services.topic_service import ensure_topic
from services.payment_service import (
    click_payment_url, uzumpay_payment_url, get_available_providers,
)

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────────────────────────────────────
# INVOICE HTML TEMPLATE (glassmorphism, dark gradient, modern)
# ─────────────────────────────────────────────────────────────────────────────

INVOICE_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: radial-gradient(ellipse at top, #1E293B 0%, #0F172A 100%);
    width: 760px;
    padding: 60px 50px;
    color: white;
    -webkit-font-smoothing: antialiased;
  }}

  .card {{
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 32px;
    padding: 48px 44px;
    backdrop-filter: blur(20px);
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 48px;
  }}

  .brand {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}

  .brand-icon {{
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
  }}

  .brand-text {{
    font-size: 18px;
    color: #94A3B8;
    letter-spacing: 1px;
    font-weight: 500;
  }}

  .badge {{
    background: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 999px;
    font-weight: 500;
    border: 1px solid rgba(245, 158, 11, 0.2);
  }}

  .amount-block {{
    margin-bottom: 40px;
  }}

  .amount-label {{
    font-size: 14px;
    color: #64748B;
    margin-bottom: 10px;
    letter-spacing: 1.5px;
    font-weight: 500;
  }}

  .amount {{
    font-size: 64px;
    font-weight: 700;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #FFFFFF 0%, #94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
  }}

  .amount-currency {{
    font-size: 26px;
    color: #94A3B8;
    font-weight: 500;
    margin-left: 8px;
    -webkit-text-fill-color: #94A3B8;
  }}

  .card-block {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 26px 28px;
    margin-bottom: 20px;
    backdrop-filter: blur(10px);
  }}

  .card-label {{
    font-size: 13px;
    color: #64748B;
    margin-bottom: 12px;
    letter-spacing: 1.5px;
    font-weight: 500;
  }}

  .card-number {{
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 28px;
    letter-spacing: 4px;
    color: white;
    margin-bottom: 18px;
    font-weight: 500;
  }}

  .card-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .card-holder {{
    font-size: 16px;
    color: #CBD5E1;
    font-weight: 500;
    letter-spacing: 1px;
  }}

  .chip {{
    width: 48px;
    height: 32px;
    border-radius: 6px;
    background: linear-gradient(135deg, #F59E0B 0%, #DC2626 100%);
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
  }}

  .details {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 24px;
  }}

  .row {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    font-size: 16px;
  }}

  .row + .row {{
    border-top: 1px solid rgba(255, 255, 255, 0.04);
  }}

  .row-label {{ color: #64748B; }}
  .row-value {{ color: #E2E8F0; font-weight: 500; }}
  .row-bonus {{ color: #34D399; font-weight: 600; }}

  .deadline {{
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: 16px;
    padding: 18px 20px;
    display: flex;
    gap: 14px;
    align-items: center;
  }}

  .deadline-icon {{ font-size: 24px; }}

  .deadline-title {{
    font-size: 15px;
    color: #FBBF24;
    font-weight: 600;
    margin-bottom: 2px;
  }}

  .deadline-sub {{
    font-size: 13px;
    color: #94A3B8;
  }}

  .footer {{
    text-align: center;
    margin-top: 32px;
    font-size: 12px;
    color: #475569;
    letter-spacing: 1px;
    font-weight: 500;
  }}
</style>
</head>
<body>
  <div class="card">

    <div class="header">
      <div class="brand">
        <div class="brand-icon">🛡</div>
        <div class="brand-text">SUG'URTA TO'LOVI</div>
      </div>
      <div class="badge">⏳ Kutilmoqda</div>
    </div>

    <div class="amount-block">
      <div class="amount-label">SUMMA</div>
      <div class="amount">{amount}<span class="amount-currency">so'm</span></div>
    </div>

    <div class="card-block">
      <div class="card-label">KARTA RAQAMI</div>
      <div class="card-number">{card_number}</div>
      <div class="card-footer">
        <div class="card-holder">{card_holder}</div>
        <div class="chip"></div>
      </div>
    </div>

    <div class="details">
      <div class="row">
        <span class="row-label">Xizmat</span>
        <span class="row-value">Avtosug'urta</span>
      </div>
      <div class="row">
        <span class="row-label">Paket</span>
        <span class="row-value">VIP · 1 yil</span>
      </div>
      <div class="row">
        <span class="row-label">Bonus</span>
        <span class="row-bonus">+20,000 so'm</span>
      </div>
    </div>

    <div class="deadline">
      <div class="deadline-icon">⏰</div>
      <div>
        <div class="deadline-title">24 soat ichida to'lang</div>
        <div class="deadline-sub">{deadline} gacha</div>
      </div>
    </div>

    <div class="footer">INVOICE #{invoice_id} · {date}</div>

  </div>
</body>
</html>
"""

CARD_NUMBER = "5614 6861 0182 0184"
CARD_HOLDER = "NURZOD NORQULOV"


# ─────────────────────────────────────────────────────────────────────────────
# PLAYWRIGHT: HTML → PNG
# ─────────────────────────────────────────────────────────────────────────────

async def generate_invoice_image(amount: int, deadline: str) -> str:
    """HTML ni PNG ga o'giradi va fayl yo'lini qaytaradi"""
    from playwright.async_api import async_playwright

    invoice_id = str(uuid.uuid4())[:8].upper()
    date = datetime.now().strftime("%d.%m.%Y")

    html = INVOICE_HTML.format(
        amount=f"{amount:,}",
        card_number=CARD_NUMBER,
        card_holder=CARD_HOLDER,
        deadline=deadline,
        invoice_id=invoice_id,
        date=date
    )

    path = f"invoice_{uuid.uuid4().hex}.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page(viewport={"width": 760, "height": 1100})
        await page.set_content(html, wait_until="networkidle")
        # full page screenshot — kontent balandligiga moslashadi
        await page.screenshot(path=path, full_page=True, omit_background=False)
        await browser.close()

    return path


# ─────────────────────────────────────────────────────────────────────────────
# CHEK YUBORISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "send_check")
async def send_check_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await add_pending_check(user_id)

    await callback.message.answer(
        "📸 Iltimos, to'lov chekini rasm ko'rinishida yuboring"
    )
    await callback.answer()


@router.message(F.chat.type == "private", F.photo)
async def receive_check(message: types.Message):
    try:
        user_id = message.from_user.id
        if not await is_awaiting_check(user_id):
            topic_id = await ensure_topic(user_id, message.from_user.full_name, message.bot)
            if topic_id:
                await message.bot.copy_message(
                    chat_id=GROUP_ID,
                    from_chat_id=user_id,
                    message_id=message.message_id,
                    message_thread_id=topic_id,
                )
            return

        await remove_pending_check(user_id)

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


@router.callback_query(F.data.regexp(r"^approve_\d+$"))
async def approve_check(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])

        from database.db import update_order_status
        await update_order_status(user_id, 'paid')

        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n✅ Qabul qilindi"
        )

        await callback.bot.send_message(user_id, "✅ To'lovingiz qabul qilindi")
        await callback.answer()
        logger.info(f"Payment approved: {user_id}")

    except Exception as e:
        logger.error(f"Approve error: {e}", exc_info=True)
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.regexp(r"^fake_\d+$"))
async def fake_check(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    from database.db import update_order_status
    await update_order_status(user_id, 'rejected')

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n❌ Soxta chek"
    )

    await callback.bot.send_message(user_id, "❌ Chek tasdiqlanmadi")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^cancel_\d+$"))
async def cancel_check(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n🚫 Bekor qilindi"
    )

    await callback.bot.send_message(user_id, "🚫 Buyurtma bekor qilindi")
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# /invoys
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.chat.id == GROUP_ID, F.text.startswith("/invoys"))
async def create_invoice(message: types.Message):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else None

    logger.info(f"INVOYS: thread={message.message_thread_id}, args={args}")

    topic_id = message.message_thread_id
    if not topic_id:
        await message.reply("❌ Bu buyruq faqat topic ichida ishlaydi")
        return

    user_id = await get_user(topic_id)
    if not user_id:
        await message.reply("❌ Mijoz topilmadi")
        return

    try:
        amount = int(args)
    except (TypeError, ValueError):
        await message.reply("❌ Format: /invoys 500000")
        return

    deadline = datetime.now() + timedelta(hours=24)
    deadline_str = deadline.strftime("%d-%m %H:%M")

    # Orderni avval yaratamiz — provayder URL'larida order_id kerak
    order_id = await save_order(user_id, topic_id, amount, "waiting", deadline_str)
    if not order_id:
        await message.reply("❌ Order yaratishda xatolik")
        return

    # Online to'lov tugmalari
    providers = get_available_providers(amount, order_id)
    buttons = []
    for label, url in providers:
        buttons.append([types.InlineKeyboardButton(text=label, url=url)])

    # Mijoz to'lab bo'lgach o'zi tasdiqlashi uchun
    if providers:
        buttons.append([types.InlineKeyboardButton(
            text="✅ To'lab bo'ldim",
            callback_data=f"payment_done_{order_id}",
            style="success",
        )])

    # Qo'lda to'lov fallback (karta)
    buttons.append([types.InlineKeyboardButton(
        text="📸 Karta orqali to'lash (chek yuborish)",
        callback_data="send_check"
    )])

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    if providers:
        # Online to'lov bor — oddiy matn yuboramiz, rasm shart emas
        provider_names = ", ".join(label.split(" bilan")[0] for label, _ in providers)
        caption = (
            f"🛡 <b>Sug'urta to'lovi</b>\n\n"
            f"💰 Summa: <b>{amount:,} so'm</b>\n"
            f"⏰ Muddat: <b>{deadline_str}</b> gacha\n\n"
            f"💳 <b>Onlayn to'lash:</b> {provider_names}\n"
            f"📸 Yoki kartaga to'lash mumkin\n\n"
            f"👇 Tanlang"
        )
        await message.bot.send_message(
            chat_id=user_id, text=caption, reply_markup=kb, parse_mode="HTML"
        )
    else:
        # Online to'lov sozlanmagan — eski karta + chek flow
        try:
            image_path = await generate_invoice_image(amount, deadline_str)
        except Exception as e:
            logger.error(f"Invoice image error: {e}", exc_info=True)
            await message.reply("❌ Rasm yaratishda xatolik")
            return

        await message.bot.send_photo(
            chat_id=user_id,
            photo=types.FSInputFile(image_path),
            caption=(
                f"🛡 <b>Sug'urta to'lovi tayyor</b>\n\n"
                f"💳 <code>{CARD_NUMBER}</code>\n"
                f"👤 {CARD_HOLDER}\n\n"
                f"☝️ <i>Karta raqamiga bosib nusxalang</i>\n\n"
                f"To'lovdan so'ng chek yuboring 👇"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        try:
            os.remove(image_path)
        except Exception:
            pass

    await message.answer(
        f"💳 Invoys yuborildi (#{order_id})\n💰 {amount:,} so'm\n⏳ {deadline_str}"
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data.regexp(r"^payment_done_\d+$"))
async def user_marked_paid(callback: types.CallbackQuery):
    """Mijoz onlayn to'lab bo'lganini bildiradi — operatorga tasdiqlash uchun yuboriladi."""
    order_id = int(callback.data.split("_")[-1])
    order = await get_order(order_id)
    if not order:
        await callback.answer("❌ Order topilmadi", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "⏳ <b>Tasdiqlash kutilmoqda</b>\n\n"
        "<blockquote>Operator merchant kabinetda to'lovingizni tekshiradi.\n"
        "5-10 daqiqa ichida sug'urta rasmiylashtiriladi.</blockquote>",
        parse_mode="HTML",
    )

    # Operatorga topicga xabar — qo'lda tasdiqlash kerak
    op_kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(
            text="✅ Tasdiqlash (to'lov keldi)",
            callback_data=f"payment_confirm_{order_id}",
            style="success",
        ),
        types.InlineKeyboardButton(
            text="❌ Rad etish",
            callback_data=f"payment_reject_{order_id}",
            style="danger",
        ),
    ]])
    await callback.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=order["topic_id"],
        text=(
            f"💳 <b>MIJOZ TO'LADIM DEDI</b>\n━━━━━━━━━━━\n"
            f"🆔 Order: #{order_id}\n"
            f"💰 Summa: <b>{order['amount']:,} so'm</b>\n"
            f"📲 Provayder: {order.get('provider') or 'Click/Uzum (qolda tekshiring)'}\n"
            f"━━━━━━━━━━━\n"
            f"⚠️ Merchant kabinetda tekshirib, tasdiqlang"
        ),
        reply_markup=op_kb, parse_mode="HTML",
    )
    await callback.answer("Yuborildi", show_alert=False)


@router.callback_query(F.data.regexp(r"^payment_confirm_\d+$"))
async def operator_confirm_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    order = await update_order_status_by_id(order_id, "paid")
    if not order:
        await callback.answer("❌ Order topilmadi", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n✅ Tasdiqlandi"
        )
    except Exception:
        pass

    await callback.bot.send_message(
        chat_id=order["user_id"],
        text="✅ <b>To'lovingiz tasdiqlandi!</b>\n\nSug'urta rasmiylashtirilmoqda.",
        parse_mode="HTML",
    )
    await callback.answer("Tasdiqlandi")


@router.callback_query(F.data.regexp(r"^payment_reject_\d+$"))
async def operator_reject_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    order = await update_order_status_by_id(order_id, "rejected")
    if not order:
        await callback.answer("❌ Order topilmadi", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n❌ Rad etildi"
        )
    except Exception:
        pass

    await callback.bot.send_message(
        chat_id=order["user_id"],
        text="❌ <b>To'lov tasdiqlanmadi</b>\n\nOperator siz bilan bog'lanadi.",
        parse_mode="HTML",
    )
    await callback.answer("Rad etildi")