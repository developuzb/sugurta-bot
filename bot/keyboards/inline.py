from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def start_menu_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Avtomobilni sug'urtalash", callback_data="start_insurance")],
            [
                InlineKeyboardButton(text="💰 Narx", callback_data="start_insurance"),
                InlineKeyboardButton(text="🎁 Bonus", callback_data="bonus")
            ],
            [InlineKeyboardButton(text="❓ Yordam", callback_data="help_mode")]
        ]
    )