# bot/keyboards/calendar_kb.py
import calendar
from datetime import date, timedelta
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.pricing import is_weekend

MONTHS_UA = ["","Січень","Лютий","Березень","Квітень","Травень","Червень",
             "Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"]
DAYS_UA = ["Пн","Вт","Ср","Чт","Пт","Сб","Нд"]

class CalCb(CallbackData, prefix="cal"):
    action: str   # day | prev | next | ignore | cancel
    year:   int
    month:  int
    day:    int = 0

def build_calendar(
    year: int,
    month: int,
    fully_booked: set = None,
    weekday_price: int = 1700,
    weekend_price: int = 2200
) -> InlineKeyboardMarkup:
    fully_booked = fully_booked or set()
    today = date.today()
    min_date = today + timedelta(days=1)       # завтра
    max_date = today + timedelta(days=14)      # через 2 тижні
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
                if d < min_date or d > max_date:
                    text, action = "·", "ignore"
                elif d in fully_booked:
                    text, action = "❌", "ignore"
                else:
                    if is_weekend(d):
                        text = f"🌟{day}"
                    else:
                        text = str(day)
                    action = "day"
                row.append(InlineKeyboardButton(
                    text=text,
                    callback_data=CalCb(action=action, year=year, month=month, day=day).pack()
                ))
        rows.append(row)

    # Легенда під календарем
    rows.append([
        InlineKeyboardButton(
            text=f"Будній: {weekday_price} грн",
            callback_data=CalCb(action="ignore", year=year, month=month).pack()
        ),
        InlineKeyboardButton(
            text=f"🌟 Вихідний: {weekend_price} грн",
            callback_data=CalCb(action="ignore", year=year, month=month).pack()
        )
    ])

    # Навігація
    prev = (date(year, month, 1) - timedelta(days=1))
    nxt  = (date(year, month, 28) + timedelta(days=4)).replace(day=1)
    max_d = max_date.replace(day=1)

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

async def build_client_calendar(session, year: int, month: int) -> InlineKeyboardMarkup:
    from bot.database.queries import get_prices, get_fully_booked_dates
    weekday_price, weekend_price = await get_prices(session)
    fully_booked = await get_fully_booked_dates(session, year, month)
    return build_calendar(year, month, fully_booked, weekday_price, weekend_price)
