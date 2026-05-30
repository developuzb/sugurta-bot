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

import base64
import hashlib
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from aiohttp import web
from aiogram import Bot

from config import API_TOKEN, CLICK_SECRET_KEY, GROUP_ID, UZUM_API_KEY
from database.db import (
    init_postgres, get_order, update_order_status_by_id,
    create_web_lead, get_web_lead, get_web_leads_list, get_leads_stats,
    update_web_lead_status, set_web_lead_topic_id,
    create_partner_lead, get_partner_leads, update_partner_lead_status,
    set_partner_topic_id, get_partner_lead, add_partner_cashback,
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "texnoset2025")

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
    logger.info(
        "CLICK webhook: action=%s order=%s amount=%s click_trans=%s",
        data.get("action"), data.get("merchant_trans_id"),
        data.get("amount"), data.get("click_trans_id"),
    )

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

    Signature verification hali tayyor emas — Uzum credentials kelgach
    HMAC formulasiga moslab to'ldirish kerak. Shu vaqtgacha endpoint
    503 qaytaradi, fake to'lov tasdiqlanmasligi uchun.
    """
    if not UZUM_API_KEY:
        return web.json_response(
            {"error": "uzum not configured"}, status=503,
        )

    # TODO: signature verification (Uzum HMAC, secret = UZUM_API_KEY)
    # TODO: extract order_id and amount, validate
    # TODO: on success → update_order_status_by_id + notify_payment_success
    logger.warning("UZUM webhook called but signature verification not implemented")
    return web.json_response(
        {"error": "uzum signature verification not implemented"}, status=503,
    )


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

STATIC_DIR = Path(__file__).parent / "static"

_VN = {"yengil": "🚗 Yengil", "yuk": "🚚 Yuk", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}
_TN = {"limited": "Oddiy", "unlimited": "👑 VIP"}
_DN = {"dur_12": "🛡 1 yil", "dur_6": "📅 6 oy", "dur_20": "⚡ 20 kun"}


# ─────────────────────────────────────────────────────────────────────────────
# WEB SAYT
# ─────────────────────────────────────────────────────────────────────────────

async def index_handler(request: web.Request) -> web.FileResponse:
    host = request.headers.get("Host", "")
    if host in ("texnoset.uz", "www.texnoset.uz"):
        return web.FileResponse(STATIC_DIR / "landing.html")
    return web.FileResponse(STATIC_DIR / "index.html")


# ─────────────────────────────────────────────────────────────────────────────
# WEB LEAD — websaytdan kelgan so'rov
# ─────────────────────────────────────────────────────────────────────────────

BOT_USERNAME = os.getenv("BOT_USERNAME", "texnoset_avto_bot")


async def web_lead_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    name          = data.get("name") or "Noma'lum"
    phone         = data.get("phone") or "—"
    vehicle       = data.get("vehicle") or "—"
    region_label  = data.get("region_label") or "—"
    itype         = data.get("insurance_type") or "—"
    duration      = data.get("duration") or "—"
    price         = int(data.get("price") or 0)
    bonus         = int(data.get("bonus") or 0)
    subregion     = data.get("subregion") or ""

    # 1) Bazaga saqlash (unikal kod bilan)
    code = "wl_" + secrets.token_urlsafe(8)
    saved = await create_web_lead(code, {
        "name": name, "phone": phone, "vehicle": vehicle,
        "region": data.get("region"), "region_label": region_label,
        "subregion": subregion, "insurance_type": itype,
        "duration": duration, "price": price, "bonus": bonus,
    })
    if not saved:
        logger.error(f"web_lead DB save FAILED: {code} {phone}")
        return web.json_response({"ok": False, "error": "db_error"}, status=500)

    # 2) Operatorga xabar
    bot_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    text = (
        f"🌐 <b>WEB SAYT ORQALI SO'ROV</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 {name}\n"
        f"📞 <code>{phone}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{_VN.get(vehicle, vehicle)}\n"
        f"📍 {region_label}"
        + (f" ({subregion})" if subregion else "") + "\n"
        f"🛡 {_TN.get(itype, itype)} · {_DN.get(duration, duration)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>{price:,} so'm</b>\n"
        f"🎁 Bonus: <b>+{bonus:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 Agar mijoz botga ulansa — <a href='{bot_link}'>bu havola</a> orqali"
    )

    try:
        await bot.send_message(chat_id=GROUP_ID, text=text,
                               parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"web_lead: {name} {phone} {price} code={code}")
        return web.json_response({
            "ok": True,
            "lead_code": code,
            "bot_link": bot_link,
        })
    except Exception as e:
        logger.error(f"web_lead_handler error: {e}", exc_info=True)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────────────────

async def health(_request: web.Request) -> web.Response:
    return web.Response(text="OK")


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────────────────────────────────────

def _check_admin(request: web.Request) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        _, pwd = decoded.split(":", 1)
        return pwd == ADMIN_PASSWORD
    except Exception:
        return False


def _require_admin(handler):
    async def wrapper(request: web.Request):
        if not _check_admin(request):
            return web.Response(
                status=401,
                headers={"WWW-Authenticate": 'Basic realm="TexnoSet Admin"'},
                text="401 Unauthorized",
            )
        return await handler(request)
    return wrapper


@_require_admin
async def admin_handler(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "admin.html")


@_require_admin
async def admin_api_handler(_request: web.Request) -> web.Response:
    stats = await get_leads_stats()
    leads = await get_web_leads_list(200)

    _VN = {"yengil": "🚗 Yengil", "yuk": "🚚 Yuk", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}
    _TN = {"limited": "Oddiy", "unlimited": "VIP"}
    _DN = {"dur_12": "1 yil", "dur_6": "6 oy", "dur_20": "20 kun"}

    # GROUP_ID dan topic link prefix hisoblash
    _group_abs = str(abs(GROUP_ID))
    if _group_abs.startswith("100"):
        _group_abs = _group_abs[3:]

    rows = []
    for l in leads:
        tid = l.get("lead_topic_id")
        topic_link = f"https://t.me/c/{_group_abs}/{tid}" if tid else None
        rows.append({
            "code":       l["code"],
            "name":       l["name"] or "—",
            "phone":      l["phone"] or "—",
            "vehicle":    _VN.get(l["vehicle"] or "", l["vehicle"] or "—"),
            "region":     l["region_label"] or "—",
            "type":       _TN.get(l["insurance_type"] or "", l["insurance_type"] or "—"),
            "duration":   _DN.get(l["duration"] or "", l["duration"] or "—"),
            "price":      l["price"],
            "bonus":      l["bonus"],
            "linked":     l["telegram_user_id"] is not None,
            "tg_user_id": l["telegram_user_id"],
            "topic_id":   tid,
            "topic_link": topic_link,
            "status":     l.get("status") or "new",
            "note":       l.get("note") or "",
            "created_at": l["created_local"].strftime("%d.%m %H:%M") if l.get("created_local") else "—",
        })

    # done count qo'shamiz
    stats["done"] = sum(1 for r in rows if r.get("status") == "done")
    return web.json_response({"stats": stats, "leads": rows})


VALID_STATUSES = {"new", "called", "in_progress", "done", "cancelled"}


@_require_admin
async def admin_status_handler(request: web.Request) -> web.Response:
    """Admin: web lead statusini yangilash."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    code   = (data.get("code") or "").strip()
    status = (data.get("status") or "").strip()
    note   = data.get("note")  # ixtiyoriy

    if not code:
        return web.json_response({"ok": False, "error": "code required"}, status=400)
    if status not in VALID_STATUSES:
        return web.json_response(
            {"ok": False, "error": f"status must be one of {VALID_STATUSES}"}, status=400
        )

    ok = await update_web_lead_status(code, status, note)
    if ok:
        logger.info(f"admin_status: code={code} → {status}")
        return web.json_response({"ok": True})
    return web.json_response({"ok": False, "error": "db error"}, status=500)


@_require_admin
async def admin_create_topic_handler(request: web.Request) -> web.Response:
    """Admin: web lead uchun Telegram forum topic yaratadi."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    code = (data.get("code") or "").strip()
    if not code:
        return web.json_response({"ok": False, "error": "code required"}, status=400)

    lead = await get_web_lead(code)
    if not lead:
        return web.json_response({"ok": False, "error": "lead not found"}, status=404)

    # Agar topic allaqachon mavjud bo'lsa, uni qaytaramiz
    if lead.get("lead_topic_id"):
        topic_id = lead["lead_topic_id"]
        group_abs = str(abs(GROUP_ID))
        if group_abs.startswith("100"):
            group_abs = group_abs[3:]
        topic_link = f"https://t.me/c/{group_abs}/{topic_id}"
        return web.json_response({"ok": True, "topic_id": topic_id, "topic_link": topic_link, "existed": True})

    # Yangi forum topic yaratamiz
    name  = lead.get("name") or "Noma'lum"
    phone = lead.get("phone") or "—"
    topic_title = f"{name} · {phone}"[:128]  # Telegram max 128 chars

    try:
        from aiogram.types import ForumTopic
        result: ForumTopic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=topic_title,
        )
        topic_id = result.message_thread_id

        # Birinchi xabar — lead ma'lumotlari
        _VN2 = {"yengil": "🚗 Yengil", "yuk": "🚚 Yuk", "bus": "🚌 Avtobus", "other": "🏍 Boshqa"}
        _TN2 = {"limited": "Oddiy", "unlimited": "👑 VIP"}
        _DN2 = {"dur_12": "🛡 1 yil", "dur_6": "📅 6 oy", "dur_20": "⚡ 20 kun"}
        price = lead.get("price") or 0
        bonus = lead.get("bonus") or 0
        info_text = (
            f"📋 <b>WEB LEAD CHAT</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 {name}\n"
            f"📞 <code>{phone}</code>\n"
            f"🚗 {_VN2.get(lead.get('vehicle') or '', lead.get('vehicle') or '—')}\n"
            f"📍 {lead.get('region_label') or '—'}\n"
            f"🛡 {_TN2.get(lead.get('insurance_type') or '', '—')} · "
            f"{_DN2.get(lead.get('duration') or '', '—')}\n"
            f"💰 <b>{price:,} so'm</b>   🎁 +{bonus:,} so'm bonus\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Kod: <code>{code}</code>"
        )
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic_id,
            text=info_text,
            parse_mode="HTML",
        )

        await set_web_lead_topic_id(code, topic_id)

        group_abs = str(abs(GROUP_ID))
        if group_abs.startswith("100"):
            group_abs = group_abs[3:]
        topic_link = f"https://t.me/c/{group_abs}/{topic_id}"

        logger.info(f"admin_create_topic: code={code} topic_id={topic_id}")
        return web.json_response({"ok": True, "topic_id": topic_id, "topic_link": topic_link, "existed": False})

    except Exception as e:
        logger.error(f"admin_create_topic_handler error: {e}", exc_info=True)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# HAMKORLIK ARIZASI
# ─────────────────────────────────────────────────────────────────────────────

async def partner_lead_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    name            = (data.get("name") or "").strip() or "Noma'lum"
    phone           = (data.get("phone") or "").strip()
    region          = (data.get("region") or "").strip()
    monthly_clients = (data.get("monthly_clients") or "").strip()

    if not phone:
        return web.json_response({"ok": False, "error": "phone required"}, status=400)

    lead_id = await create_partner_lead({
        "name": name, "phone": phone,
        "region": region, "monthly_clients": monthly_clients,
    })
    if not lead_id:
        return web.json_response({"ok": False, "error": "db_error"}, status=500)

    # Forum topic yaratamiz
    topic_id = None
    try:
        from aiogram.types import ForumTopic
        topic_title = f"🤝 {name} · {phone}"[:128]
        result: ForumTopic = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            name=topic_title,
        )
        topic_id = result.message_thread_id
        await set_partner_topic_id(lead_id, topic_id)
    except Exception as e:
        logger.error(f"partner_lead create_topic error: {e}", exc_info=True)

    # Topic ichiga yoki guruhga xabar yubor
    text = (
        f"🤝 <b>HAMKORLIK ARIZASI #{lead_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b>\n"
        f"📞 <code>{phone}</code>\n"
        f"📍 {region or '—'}\n"
        f"📊 Oylik mijozlar: {monthly_clients or 'koʼrsatilmagan'}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Viloyat: <b>27%</b>  |  Toshkent: <b>7%</b>\n"
        f"📦 Reklama materiallari: pochta (2 000 so'm)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💎 Umumiy keshbek: <b>0 so'm</b>\n"
        f"📋 Jami polislar: <b>0 ta</b>"
    )
    try:
        send_kwargs = dict(chat_id=GROUP_ID, text=text, parse_mode="HTML")
        if topic_id:
            send_kwargs["message_thread_id"] = topic_id
        await bot.send_message(**send_kwargs)
    except Exception as e:
        logger.error(f"partner_lead notify error: {e}", exc_info=True)

    logger.info(f"partner_lead: #{lead_id} {name} {phone} topic={topic_id}")
    return web.json_response({"ok": True, "id": lead_id, "topic_id": topic_id})


@_require_admin
async def admin_partner_api_handler(_request: web.Request) -> web.Response:
    leads = await get_partner_leads(200)
    rows = []
    for l in leads:
        rows.append({
            "id":              l["id"],
            "name":            l["name"] or "—",
            "phone":           l["phone"] or "—",
            "region":          l["region"] or "—",
            "monthly_clients": l["monthly_clients"] or "—",
            "status":          l.get("status") or "new",
            "note":            l.get("note") or "",
            "topic_id":        l.get("topic_id"),
            "total_cashback":  l.get("total_cashback") or 0,
            "total_policies":  l.get("total_policies") or 0,
            "created_at":      l["created_local"].strftime("%d.%m %H:%M") if l.get("created_local") else "—",
        })
    total = len(rows)
    new_count = sum(1 for r in rows if r["status"] == "new")
    return web.json_response({"leads": rows, "total": total, "new": new_count})


VALID_PARTNER_STATUSES = {"new", "called", "active", "cancelled"}


@_require_admin
async def admin_partner_status_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    lead_id = data.get("id")
    status  = (data.get("status") or "").strip()
    note    = data.get("note")
    if not lead_id or status not in VALID_PARTNER_STATUSES:
        return web.json_response({"ok": False, "error": "invalid"}, status=400)
    ok = await update_partner_lead_status(int(lead_id), status, note)

    # Status o'zgarganda topicga xabar yubor
    if ok:
        lead = await get_partner_lead(int(lead_id))
        if lead and lead.get("topic_id"):
            STATUS_LABELS = {
                "new": "🆕 Yangi",
                "called": "📞 Qo'ng'iroq qilindi",
                "active": "✅ Faol hamkor",
                "cancelled": "❌ Bekor qilindi",
            }
            try:
                await bot.send_message(
                    chat_id=GROUP_ID,
                    message_thread_id=lead["topic_id"],
                    text=(
                        f"📊 <b>Status yangilandi</b>\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"🔄 {STATUS_LABELS.get(status, status)}\n"
                        f"{f'📝 {note}' if note else ''}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"partner_status_notify error: {e}")

    return web.json_response({"ok": ok})


@_require_admin
async def admin_partner_cashback_handler(request: web.Request) -> web.Response:
    """Hamkor topiciga keshbek qo'shadi."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    lead_id  = data.get("id")
    cashback = data.get("cashback")  # so'mda
    policies = int(data.get("policies") or 1)
    comment  = (data.get("comment") or "").strip()

    if not lead_id or not cashback:
        return web.json_response({"ok": False, "error": "id and cashback required"}, status=400)

    lead_id  = int(lead_id)
    cashback = int(cashback)

    ok = await add_partner_cashback(lead_id, cashback, policies)
    if not ok:
        return web.json_response({"ok": False, "error": "db error"}, status=500)

    # Yangilangan ma'lumotlarni ol
    lead = await get_partner_lead(lead_id)
    if not lead:
        return web.json_response({"ok": False, "error": "not found"}, status=404)

    total_cashback = lead.get("total_cashback") or 0
    total_policies = lead.get("total_policies") or 0

    # Topicga keshbek xabari
    if lead.get("topic_id"):
        try:
            msg = (
                f"💰 <b>KESHBEK HISOBLANDI</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"➕ Bu safar: <b>+{cashback:,} so'm</b>\n"
                f"📋 Polislar soni: <b>{policies} ta</b>\n"
            )
            if comment:
                msg += f"📝 {comment}\n"
            msg += (
                f"━━━━━━━━━━━━━━━\n"
                f"💎 Jami keshbek: <b>{total_cashback:,} so'm</b>\n"
                f"📊 Jami polislar: <b>{total_policies} ta</b>"
            )
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=lead["topic_id"],
                text=msg,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"partner_cashback_notify error: {e}")

    return web.json_response({
        "ok": True,
        "total_cashback": total_cashback,
        "total_policies": total_policies,
    })


async def on_startup(_app):
    await init_postgres()
    logger.info("Webhook server READY")


async def on_cleanup(_app):
    await bot.session.close()


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_post("/web-lead", web_lead_handler)
    app.router.add_post("/click/webhook", click_handler)
    app.router.add_post("/uzum/webhook", uzum_handler)
    app.router.add_get("/health", health)
    app.router.add_get("/admin", admin_handler)
    app.router.add_get("/admin/api", admin_api_handler)
    app.router.add_post("/admin/api/status", admin_status_handler)
    app.router.add_post("/admin/api/create-topic", admin_create_topic_handler)
    app.router.add_post("/partner-lead", partner_lead_handler)
    app.router.add_get("/admin/partner", admin_partner_api_handler)
    app.router.add_post("/admin/partner/status", admin_partner_status_handler)
    app.router.add_post("/admin/partner/cashback", admin_partner_cashback_handler)
    app.router.add_static("/static", STATIC_DIR, show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    web.run_app(make_app(), host="0.0.0.0", port=port)
