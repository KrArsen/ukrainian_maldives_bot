# bot/keyboards/calendar_kb.py
import calendar
from datetime import date, timedelta
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MONTHS_UA = ["","Січень","Лютий","Березень","Квітень","Травень","Червень",
             "Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"]
DAYS_UA = ["Пн","Вт","Ср","Чт","Пт","Сб","Нд"]

class CalCb(CallbackData, prefix="cal"):
    action: str   # day | prev | next | ignore | cancel
    year:   int
    month:  int
    day:    int = 0

def build_calendar(year: int, month: int, fully_booked: set = None) -> InlineKeyboardMarkup:
    fully_booked = fully_booked or set()
    today = date.today()
    rows = []

    # Заголовок місяця
    rows.append([InlineKeyboardButton(
        text=f"📅 {MONTHS_UA[month]} {year}",
        callback_data=CalCb(action="ignore", year=year, month=month).pack()
    )])

    # Назви днів тижня
    rows.append([InlineKeyboardButton(
        text=d, callback_data=CalCb(action="ignore", year=year, month=month).pack()
    ) for d in DAYS_UA])

    # Дні
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(
                    text=" ", callback_data=CalCb(action="ignore", year=year, month=month).pack()
                ))
            else:
                d = date(year, month, day)
                if d < today:
                    text, action = "·", "ignore"
                elif d in fully_booked:
                    text, action = "❌", "ignore"
                else:
                    text, action = str(day), "day"
                row.append(InlineKeyboardButton(
                    text=text,
                    callback_data=CalCb(action=action, year=year, month=month, day=day).pack()
                ))
        rows.append(row)

    # Навігація
    prev = (date(year, month, 1) - timedelta(days=1))
    nxt  = (date(year, month, 28) + timedelta(days=4)).replace(day=1)
    max_d = today.replace(day=1)
    for _ in range(3):
        if max_d.month == 12:
            max_d = max_d.replace(year=max_d.year+1, month=1)
        else:
            max_d = max_d.replace(month=max_d.month+1)

    nav = []
    if date(year, month, 1) > today.replace(day=1):
        nav.append(InlineKeyboardButton(
            text="◀️", callback_data=CalCb(action="prev", year=prev.year, month=prev.month).pack()
        ))
    else:
        nav.append(InlineKeyboardButton(
            text=" ", callback_data=CalCb(action="ignore", year=year, month=month).pack()
        ))

    nav.append(InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data=CalCb(action="cancel", year=year, month=month).pack()
    ))

    if nxt <= max_d:
        nav.append(InlineKeyboardButton(
            text="▶️", callback_data=CalCb(action="next", year=nxt.year, month=nxt.month).pack()
        ))
    else:
        nav.append(InlineKeyboardButton(
            text=" ", callback_data=CalCb(action="ignore", year=year, month=month).pack()
        ))

    rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)
