"""
Click va Uzum Pay webhook serveri.

Bu — polling botdan ALOHIDA process. HTTPS ostida deploy qilinishi kerak
(Render/Railway/Fly.io/o'z VPS + Nginx + Let's Encrypt).

Click cabinet'da webhook URL'i shu serverga yo'naltirilishi kerak:
    https://yourdomain.uz/click/webhook
    https://yourdomain.uz/uzum/webhook

Bot tokeni orqali to'lov tasdiqlangach mijozga avtomatik xabar yuboradi
va operator topic'iga ham qisqa xulosa beradi.

Run:
    python webhook.py
    # yoki production:
    gunicorn webhook:make_app --bind 0.0.0.0:8080 --worker-class aiohttp.GunicornWebWorker
"""

import hashlib
import logging
import os
from typing import Optional

from aiohttp import web
from aiogram import Bot

from config import API_TOKEN, CLICK_SECRET_KEY, GROUP_ID, UZUM_API_KEY
from database.db import init_postgres, get_order, update_order_status_by_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("webhook")

bot = Bot(token=API_TOKEN)


# ─────────────────────────────────────────────────────────────────────────────
# CLICK
# ─────────────────────────────────────────────────────────────────────────────

def click_make_signature(data: dict, action: str) -> str:
    """
    Click Prepare/Complete MD5 signature.

    Prepare (action=0):
        MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id +
            amount + action + sign_time)

    Complete (action=1):
        MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id +
            merchant_prepare_id + amount + action + sign_time)
    """
    parts = [
        str(data.get("click_trans_id", "")),
        str(data.get("service_id", "")),
        CLICK_SECRET_KEY or "",
        str(data.get("merchant_trans_id", "")),
    ]
    if action == "1":
        parts.append(str(data.get("merchant_prepare_id", "")))
    parts.extend([
        str(data.get("amount", "")),
        str(action),
        str(data.get("sign_time", "")),
    ])
    return hashlib.md5("".join(parts).encode()).hexdigest()


async def click_handler(request: web.Request) -> web.Response:
    data = dict(await request.post())
    logger.info(f"CLICK webhook: {data}")

    action = data.get("action")
    if action not in ("0", "1"):
        return web.json_response({"error": -3, "error_note": "UNKNOWN ACTION"})

    # 1) Signature
    expected = click_make_signature(data, action)
    if data.get("sign_string", "").lower() != expected.lower():
        logger.warning("CLICK signature mismatch")
        return web.json_response({"error": -1, "error_note": "SIGN CHECK FAILED"})

    # 2) Order ID
    try:
        order_id = int(data["merchant_trans_id"])
    except (KeyError, ValueError):
        return web.json_response({"error": -8, "error_note": "BAD ORDER ID"})

    order = await get_order(order_id)
    if not order:
        return web.json_response({"error": -5, "error_note": "ORDER NOT FOUND"})

    # 3) Amount
    try:
        if int(float(data.get("amount", 0))) != int(order["amount"]):
            return web.json_response({"error": -2, "error_note": "AMOUNT MISMATCH"})
    except (TypeError, ValueError):
        return web.json_response({"error": -2, "error_note": "BAD AMOUNT"})

    # 4) Prepare
    if action == "0":
        return web.json_response({
            "click_trans_id": data["click_trans_id"],
            "merchant_trans_id": str(order_id),
            "merchant_prepare_id": str(order_id),
            "error": 0,
            "error_note": "OK",
        })

    # 5) Complete
    if int(data.get("error", -1)) == 0 and order["status"] != "paid":
        await update_order_status_by_id(order_id, "paid")
        await notify_payment_success(order_id, order, provider="click",
                                     transaction_id=data.get("click_trans_id"))
    return web.json_response({
        "click_trans_id": data["click_trans_id"],
        "merchant_trans_id": str(order_id),
        "merchant_confirm_id": str(order_id),
        "error": 0,
        "error_note": "OK",
    })


# ─────────────────────────────────────────────────────────────────────────────
# UZUM PAY
# ─────────────────────────────────────────────────────────────────────────────

async def uzum_handler(request: web.Request) -> web.Response:
    """
    Uzum Pay webhook. Format Uzum hujjatlarida (developer.uzum.uz).
    Hozir placeholder — credentials kelgach signature formulasiga moslab to'ldiring.
    """
    try:
        data = await request.json()
    except Exception:
        data = dict(await request.post())
    logger.info(f"UZUM webhook: {data}")

    # TODO: signature verification (Uzum HMAC, secret = UZUM_API_KEY)
    # TODO: extract order_id and amount, validate
    # TODO: on success → update_order_status_by_id + notify_payment_success

    order_id_raw = data.get("order_id") or data.get("merchant_transaction_id")
    if order_id_raw:
        try:
            order_id = int(order_id_raw)
            order = await get_order(order_id)
            if order and order["status"] != "paid":
                await update_order_status_by_id(order_id, "paid")
                await notify_payment_success(order_id, order, provider="uzum",
                                             transaction_id=str(data.get("transaction_id", "")))
        except (ValueError, TypeError):
            pass

    return web.json_response({"status": "ok"})


# ─────────────────────────────────────────────────────────────────────────────
# SHARED: Mijoz va operatorga xabar
# ─────────────────────────────────────────────────────────────────────────────

async def notify_payment_success(order_id: int, order: dict, provider: str,
                                 transaction_id: Optional[str] = None) -> None:
    """To'lov keldi — mijozga va operatorga xabar."""
    try:
        await bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
                f"<blockquote>💰 {order['amount']:,} so'm\n"
                f"🆔 Order: #{order_id}\n"
                f"📲 Provayder: {provider.title()}</blockquote>\n\n"
                f"📦 Sug'urtangiz tayyorlanmoqda — operator tez orada bog'lanadi"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"notify_user error: {e}", exc_info=True)

    try:
        if order.get("topic_id"):
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=order["topic_id"],
                text=(
                    f"💰 <b>TO'LOV AVTOMATIK TASDIQLANDI</b>\n"
                    f"🆔 #{order_id} · {order['amount']:,} so'm\n"
                    f"📲 {provider.title()}"
                    + (f" · TX: <code>{transaction_id}</code>" if transaction_id else "")
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"notify_operator error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

async def health(_request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def on_startup(_app):
    await init_postgres()
    logger.info("Webhook server READY")


async def on_cleanup(_app):
    await bot.session.close()


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/click/webhook", click_handler)
    app.router.add_post("/uzum/webhook", uzum_handler)
    app.router.add_get("/health", health)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    web.run_app(make_app(), host="0.0.0.0", port=port)
