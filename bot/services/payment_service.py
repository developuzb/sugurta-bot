"""
To'lov provayderlari: Click va Uzum Pay.

Foydalanuvchi to'lov tugmasini bossa, brauzer/ilovada Click yoki Uzum Pay
sahifasi ochiladi. To'lovdan keyin webhook orqali tasdiqlash kerak
(hozircha qo'lda — operator merchant kabinetda tekshiradi va "✅ Qabul"
tugmasini bosadi).

Credentials .env'da bo'lmasa, provayder None qaytaradi va tugma
ko'rsatilmaydi.

Click hujjatlari:   https://docs.click.uz/
Uzum Pay hujjatlari: https://developer.uzum.uz/
"""

import logging
import urllib.parse
from typing import Optional

from config import (
    CLICK_MERCHANT_ID, CLICK_SERVICE_ID,
    UZUM_MERCHANT_ID, UZUM_SERVICE_ID,
    PAYMENT_RETURN_URL,
)

logger = logging.getLogger(__name__)


def click_payment_url(amount: int, order_id: int) -> Optional[str]:
    """
    Click SHOP-API URL generator.
    Click admin panelida 'Online to'lov uchun havola' formati:
    https://my.click.uz/services/pay?service_id=XXX&merchant_id=YYY&amount=ZZZ&transaction_param=ORDER_ID&return_url=...
    """
    if not (CLICK_MERCHANT_ID and CLICK_SERVICE_ID):
        return None

    params = {
        "service_id": CLICK_SERVICE_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": amount,
        "transaction_param": str(order_id),
        "return_url": PAYMENT_RETURN_URL,
    }
    return f"https://my.click.uz/services/pay?{urllib.parse.urlencode(params)}"


def uzumpay_payment_url(amount: int, order_id: int) -> Optional[str]:
    """
    Uzum Pay URL generator.
    Uzum merchant kabinetida 'To'lov havolasi' formati:
    https://pay.uzum.uz/?merchant_id=XXX&service_id=YYY&amount=ZZZ&order_id=ORDER_ID&return_url=...
    """
    if not (UZUM_MERCHANT_ID and UZUM_SERVICE_ID):
        return None

    params = {
        "merchant_id": UZUM_MERCHANT_ID,
        "service_id": UZUM_SERVICE_ID,
        "amount": amount,
        "order_id": str(order_id),
        "return_url": PAYMENT_RETURN_URL,
    }
    return f"https://pay.uzum.uz/?{urllib.parse.urlencode(params)}"


def get_available_providers(amount: int, order_id: int) -> list[tuple[str, str, str]]:
    """
    Mavjud (credentials bor) provayderlar ro'yxati.
    Qaytadi: [(tugma matni, callback yoki url, "url" | "callback"), ...]
    """
    providers = []
    click_url = click_payment_url(amount, order_id)
    if click_url:
        providers.append(("💳 Click bilan to'lash", click_url))
    uzum_url = uzumpay_payment_url(amount, order_id)
    if uzum_url:
        providers.append(("🟣 Uzum Pay bilan to'lash", uzum_url))
    return providers
