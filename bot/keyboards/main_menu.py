# bot/keyboards/main_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu() -> ReplyKeyboardMarkup:
    """Returns the persistent main menu reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Забронювати"), KeyboardButton(text="📋 Мої бронювання")],
            [KeyboardButton(text="📞 Контакти")]
        ],
        resize_keyboard=True,
        persistent=True
    )
