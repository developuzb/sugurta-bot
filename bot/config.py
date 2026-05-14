import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

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
