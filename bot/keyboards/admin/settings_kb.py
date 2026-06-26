# bot/keyboards/admin/settings_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date

def get_settings_kb() -> InlineKeyboardMarkup:
    """Settings menu options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Змінити ціну", callback_data="as_price"),
            InlineKeyboardButton(text="⏱️ Змінити таймаут", callback_data="as_timeout")
        ],
        [
            InlineKeyboardButton(text="📊 Експорт в Excel (CSV)", callback_data="as_export_menu"),
            InlineKeyboardButton(text="✉️ Масова розсилка", callback_data="as_broadcast")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")
        ]
    ])

def get_export_menu_kb() -> InlineKeyboardMarkup:
    """Quick monthly report exports and custom picker."""
    today = date.today()
    current_month_str = today.strftime("%m.%Y")
    
    # Calculate previous month
    if today.month == 1:
        prev_month = 12
        prev_year = today.year - 1
    else:
        prev_month = today.month - 1
        prev_year = today.year
    prev_month_str = f"{prev_month:02d}.{prev_year}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"📊 Поточний місяць ({current_month_str})", callback_data=f"ase_quick:{today.year}:{today.month}"),
        ],
        [
            InlineKeyboardButton(text=f"📊 Попередній місяць ({prev_month_str})", callback_data=f"ase_quick:{prev_year}:{prev_month}"),
        ],
        [
            InlineKeyboardButton(text="📅 Вибрати інший місяць...", callback_data="ase_custom")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад до налаштувань", callback_data="admin_settings")
        ]
    ])

def get_export_custom_months_kb(year: int) -> InlineKeyboardMarkup:
    """Grid of 12 months for a specific year."""
    months_ua = [
        "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
        "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
    ]
    
    buttons = []
    # Month buttons in 3 columns
    row = []
    for idx, name in enumerate(months_ua, 1):
        row.append(InlineKeyboardButton(text=name, callback_data=f"ase_quick:{year}:{idx}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    # Year switching row
    buttons.append([
        InlineKeyboardButton(text=f"◀️ {year - 1}", callback_data=f"ase_yr:{year - 1}"),
        InlineKeyboardButton(text=f"🟢 {year}", callback_data="ignore"),
        InlineKeyboardButton(text=f"{year + 1} ▶️", callback_data=f"ase_yr:{year + 1}")
    ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до експорту", callback_data="as_export_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
