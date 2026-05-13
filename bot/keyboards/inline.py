from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


def phone_share_kb() -> ReplyKeyboardMarkup:
    """Telefon raqamini bir bosish bilan yuborish uchun reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="📱 Telefon raqamni yuborish",
            request_contact=True,
        )]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def start_menu_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Avtomobilni sug'urtalash", callback_data="start_insurance", style="success")],
            [InlineKeyboardButton(text="💳 30 kun 0% nasiya", callback_data="nasiya_info", style="primary")],
            [InlineKeyboardButton(text="📦 Uyga yetkazib berish", callback_data="start_delivery", style="primary")],
            [
                InlineKeyboardButton(text="💰 Narx", callback_data="start_insurance"),
                InlineKeyboardButton(text="🎁 Bonus", callback_data="bonus", style="success"),
            ],
            [InlineKeyboardButton(text="❓ Yordam", callback_data="help_mode")],
            [InlineKeyboardButton(text="🔔 Eslatma so'rash", callback_data="reminder_start", style="primary")],
        ]
    )
