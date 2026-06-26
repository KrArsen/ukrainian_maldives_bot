# bot/keyboards/admin/clients_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_clients_list_kb(clients: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Renders clients list with pagination."""
    buttons = []
    
    for user, booking_count in clients:
        # Show username or full name
        name = user.full_name or user.username or f"ID: {user.telegram_id}"
        ban_marker = " 🛑 BANNED" if user.is_banned else ""
        btn_text = f"{name} (Бронювань: {booking_count}){ban_marker}"
        # Callback: ac_v:telegram_id:page
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"ac_v:{user.telegram_id}:{page}")])
        
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=f"admin_clients_{prev_page}"),
            InlineKeyboardButton(text=f"Стор. {page}/{total_pages}", callback_data="ignore"),
            InlineKeyboardButton(text="▶️", callback_data=f"admin_clients_{next_page}")
        ])
        
    # Blacklist button to filter only banned users
    buttons.append([
        InlineKeyboardButton(text="🛑 Показати чорний список", callback_data="ac_blacklist_1")
    ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_blacklist_kb(banned_users: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Renders list of only banned clients."""
    buttons = []
    
    for user in banned_users:
        name = user.full_name or user.username or f"ID: {user.telegram_id}"
        btn_text = f"🛑 {name}"
        # View banned client: same profile viewer
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"ac_v:{user.telegram_id}:bl_{page}")])
        
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=f"ac_blacklist_{prev_page}"),
            InlineKeyboardButton(text=f"Стор. {page}/{total_pages}", callback_data="ignore"),
            InlineKeyboardButton(text="▶️", callback_data=f"ac_blacklist_{next_page}")
        ])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до клієнтів", callback_data="admin_clients_1")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_client_profile_kb(telegram_id: int, is_banned: bool, back_cb: str) -> InlineKeyboardMarkup:
    """Actions on a client's profile card."""
    buttons = []
    
    if is_banned:
        buttons.append([InlineKeyboardButton(text="🟢 Розбанити клієнта", callback_data=f"ac_unb:{telegram_id}:{back_cb}")])
    else:
        buttons.append([InlineKeyboardButton(text="🛑 Забанити клієнта", callback_data=f"ac_ban:{telegram_id}:{back_cb}")])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
