from aiogram import types


def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🚗 Sug‘urta qilish")],
            [
                types.KeyboardButton(text="🎁 Bonusni olish"),
                types.KeyboardButton(text="💰 Narxni bilish")
            ]
        ],
        resize_keyboard=True
    )