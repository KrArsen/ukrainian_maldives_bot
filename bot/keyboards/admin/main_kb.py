# bot/keyboards/admin/main_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_kb(pending_bookings: int = 0, pending_payments: int = 0) -> InlineKeyboardMarkup:
    btn_pending = f"🔔 Нові ({pending_bookings})" if pending_bookings > 0 else "🔔 Нові"
    btn_payments = f"💳 Оплати ({pending_payments})" if pending_payments > 0 else "💳 Оплати"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn_pending, callback_data="admin_pending"),
            InlineKeyboardButton(text=btn_payments, callback_data="admin_payments_1")
        ],
        [
            InlineKeyboardButton(text="📋 Всі бронювання", callback_data="admin_all_1"),
            InlineKeyboardButton(text="📅 Графік", callback_data="admin_sched")
        ],
        [
            InlineKeyboardButton(text="🔍 Пошук", callback_data="admin_search"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats_menu")
        ],
        [
            InlineKeyboardButton(text="👥 Клієнти", callback_data="admin_clients_1"),
            InlineKeyboardButton(text="⚙️ Налаштування", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="❌ Закрити", callback_data="admin_close_panel")
        ]
    ])
