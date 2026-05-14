import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        sys.stderr.write(f"FATAL: {name} env var is not set\n")
        sys.exit(1)
    return val


API_TOKEN = _required("BOT_TOKEN")
DATABASE_URL = _required("DATABASE_URL")

try:
    GROUP_ID = int(_required("GROUP_ID"))
except ValueError:
    sys.stderr.write("FATAL: GROUP_ID must be an integer (e.g. -1001234567890)\n")
    sys.exit(1)

# To'lov provayderlari (ixtiyoriy — credentials bo'lmasa, tugma ko'rsatilmaydi)
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY")

UZUM_MERCHANT_ID = os.getenv("UZUM_MERCHANT_ID")
UZUM_SERVICE_ID = os.getenv("UZUM_SERVICE_ID")
UZUM_API_KEY = os.getenv("UZUM_API_KEY")

# To'lovdan keyin mijozni qaytaradigan URL (bot deeplink)
PAYMENT_RETURN_URL = os.getenv("PAYMENT_RETURN_URL", "https://t.me/")
