import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

WEEKDAYS_UA_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

def get_booking_dates_kb() -> InlineKeyboardMarkup:
    """Returns 14 inline buttons representing the next 2 weeks (2 per row)."""
    today = datetime.date.today()
    buttons = []
    row = []
    for i in range(14):
        d = today + datetime.timedelta(days=i)
        weekday = WEEKDAYS_UA_SHORT[d.weekday()]
        label = f"📅 {weekday}, {d.strftime('%d.%m')}"
        callback = f"book_date_{d.isoformat()}"
        
        row.append(InlineKeyboardButton(text=label, callback_data=callback))
        if len(row) == 2:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking_flow")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_free_shelters_kb(free_shelters: list[int]) -> InlineKeyboardMarkup:
    """Returns inline buttons for free shatras on the selected date."""
    buttons = []
    row = []
    for s in free_shelters:
        row.append(InlineKeyboardButton(text=f"🛖 Шатро №{s}", callback_data=f"book_shelter_{s}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([
        InlineKeyboardButton(text="📅 Змінити дату", callback_data="change_date"),
        InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking_flow")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Returns contact sharing button."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поділитись номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_confirmation_kb() -> InlineKeyboardMarkup:
    """Returns final confirmation options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_booking_final"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_booking_flow")
        ]
    ])
