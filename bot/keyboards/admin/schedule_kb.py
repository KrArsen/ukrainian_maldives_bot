# bot/keyboards/admin/schedule_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, timedelta

# Ukrainian weekday names
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

def get_weekly_schedule_kb(start_date: date, day_stats: list) -> InlineKeyboardMarkup:
    """
    day_stats is a list of tuples: (day_date, booked_count)
    """
    buttons = []
    
    # 1. Day buttons
    for day_date, booked_count in day_stats:
        weekday_lbl = WEEKDAYS[day_date.weekday()]
        date_lbl = day_date.strftime("%d.%m")
        
        # Determine status indicator
        if booked_count >= 10:
            indicator = "🔴 Повна"
        elif booked_count > 0:
            indicator = f"🟡 Зайнято {booked_count}/10"
        else:
            indicator = "🟢 Вільна"
            
        btn_text = f"📅 {date_lbl} {weekday_lbl} | {indicator}"
        cb_data = f"ab_sch_d:{day_date.isoformat()}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])
        
    # 2. Navigation row
    prev_week = start_date - timedelta(days=7)
    next_week = start_date + timedelta(days=7)
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Минулий тиждень", callback_data=f"ab_sch:{prev_week.isoformat()}"),
        InlineKeyboardButton(text="Наступний тиждень ▶️", callback_data=f"ab_sch:{next_week.isoformat()}")
    ])
    
    # 3. Back to menu
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def schedule_day_kb(
    target_date: date,
    booked_bookings: list,
    blocked_dict: dict,   # {tent_number: TentBlock}
    free_nums: list
) -> InlineKeyboardMarkup:
    keyboard = []

    # Booking details buttons (linking directly to our modular booking viewer)
    for bk in booked_bookings:
        date_iso = target_date.isoformat()
        keyboard.append([
            InlineKeyboardButton(
                text=f"📋 №{bk.tent_number} {bk.full_name}",
                callback_data=f"ab_v:{bk.id}:ab_sch_d:{date_iso}"
            )
        ])

    # Unblock buttons
    for tent_num, block in blocked_dict.items():
        date_iso = target_date.isoformat()
        keyboard.append([
            InlineKeyboardButton(
                text=f"🔓 Розблокувати №{tent_num}",
                callback_data=f"admin_unblock_tent:{tent_num}:{date_iso}"
            )
        ])

    # Grid of buttons to block free tents
    if free_nums:
        keyboard.append([
            InlineKeyboardButton(text="🔒 Заблокувати шатро:", callback_data="ignore")
        ])
        row = []
        for n in free_nums:
            date_iso = target_date.isoformat()
            row.append(InlineKeyboardButton(
                text=f"№{n}",
                callback_data=f"admin_block_tent:{n}:{date_iso}"
            ))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    # Day-by-day navigation
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    keyboard.append([
        InlineKeyboardButton(
            text="◀ -1 день",
            callback_data=f"ab_sch_d:{prev_date.isoformat()}"
        ),
        InlineKeyboardButton(
            text="📆 Сьогодні",
            callback_data=f"ab_sch_d:{date.today().isoformat()}"
        ),
        InlineKeyboardButton(
            text="+1 день ▶",
            callback_data=f"ab_sch_d:{next_date.isoformat()}"
        ),
    ])
    
    # Back to week view and main menu
    monday = target_date - timedelta(days=target_date.weekday())
    keyboard.append([
        InlineKeyboardButton(text="📅 Тиждень", callback_data=f"ab_sch:{monday.isoformat()}"),
        InlineKeyboardButton(text="◀ Головне меню", callback_data="admin_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
