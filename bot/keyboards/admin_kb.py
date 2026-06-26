# bot/keyboards/admin_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Returns the main admin control panel keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔔 Нові заявки", callback_data="admin_pending"),
            InlineKeyboardButton(text="📋 Всі бронювання", callback_data="admin_all_1")
        ],
        [
            InlineKeyboardButton(text="📅 На сьогодні", callback_data="admin_today"),
            InlineKeyboardButton(text="📅 На завтра", callback_data="admin_tomorrow")
        ],
        [
            InlineKeyboardButton(text="🔍 Пошук", callback_data="admin_search"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📝 Журнал подій", callback_data="admin_activity_log")
        ]
    ])

def get_booking_details_kb(booking_id: int, status: str, back_callback: str, has_screenshot: bool = False) -> InlineKeyboardMarkup:
    """Returns inline action buttons for managing a specific booking."""
    buttons = []
    
    action_row = []
    if status == "payment_pending_review":
        action_row.append(InlineKeyboardButton(text="✅ Схвалити оплату", callback_data=f"adm_pay_confirm_{booking_id}_{back_callback}"))
        action_row.append(InlineKeyboardButton(text="❌ Відхилити оплату", callback_data=f"adm_pay_reject_{booking_id}_{back_callback}"))
    elif status == "awaiting_payment":
        action_row.append(InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"adm_confirm_{booking_id}_{back_callback}"))
        action_row.append(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"adm_cancel_{booking_id}_{back_callback}"))
    else:
        # If the booking is not cancelled, allow cancelling it
        if status != "cancelled":
            action_row.append(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"adm_cancel_{booking_id}_{back_callback}"))
        
    if action_row:
        buttons.append(action_row)
        
    if has_screenshot:
        buttons.append([
            InlineKeyboardButton(text="📸 Переглянути чек", callback_data=f"adm_show_pay_{booking_id}_{back_callback}")
        ])
        
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_{back_callback}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_all_bookings_pagination_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Returns pagination keyboard for the admin bookings history list."""
    buttons = []
    nav_row = []
    
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_all_{prev_page}"))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin_ignore"))
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_all_{next_page}"))
        buttons.append(nav_row)
        
    buttons.append([InlineKeyboardButton(text="❌ Закрити", callback_data="admin_close_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_pending_booking_actions_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Returns confirmation actions for direct use in chat alerts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"adm_confirm_{booking_id}_pending"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data=f"adm_cancel_{booking_id}_pending")
        ]
    ])

