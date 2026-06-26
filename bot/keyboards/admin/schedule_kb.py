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

def get_day_bookings_kb(target_date: date, bookings: list, back_start_date: date) -> InlineKeyboardMarkup:
    """Keyboards for a single day view details."""
    buttons = []
    
    # Buttons for each active booking of that day
    for b in bookings:
        btn_text = f"🛖 №{b.shelter_num} | {b.client_name} ({b.client_phone})"
        # Back target for detailed view: ab_v:booking_id:back_callback
        back_cb = f"ab_sch_d:{target_date.isoformat()}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"ab_v:{b.id}:{back_cb}")])
        
    # Back button to the weekly schedule view
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад до тижня", 
            callback_data=f"ab_sch:{back_start_date.isoformat()}"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
