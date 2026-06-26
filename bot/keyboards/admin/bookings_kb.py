# bot/keyboards/admin/bookings_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.database.models import BookingStatus, Booking

# Status mapping for display
STATUS_LABELS = {
    "all": "📝 Всі",
    "await": "⏳ Очік. оплат",
    "review": "🔍 Перевірка",
    "conf": "✅ Схвалені",
    "canc": "❌ Скасовані"
}

def get_bookings_list_kb(
    bookings: list,
    page: int,
    total_pages: int,
    status: str,
    tent: str,
    sort: str
) -> InlineKeyboardMarkup:
    buttons = []
    
    # 1. Booking list buttons
    for b in bookings:
        status_icon = "⏳"
        if b.status == BookingStatus.payment_pending_review:
            status_icon = "🔍"
        elif b.status == BookingStatus.confirmed:
            status_icon = "✅"
        elif b.status == BookingStatus.cancelled:
            status_icon = "❌"
            
        date_str = b.booking_date.strftime("%d.%m")
        btn_text = f"🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name} ({status_icon})"
        
        # Details callback: ab_v:booking_id:status:tent:sort:page
        cb_details = f"ab_v:{b.id}:{status}:{tent}:{sort}:{page}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_details)])
        
    # 2. Pagination row
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        
        cb_prev = f"ab_l:{status}:{tent}:{sort}:{prev_page}"
        cb_next = f"ab_l:{status}:{tent}:{sort}:{next_page}"
        
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=cb_prev),
            InlineKeyboardButton(text=f"Стор. {page}/{total_pages}", callback_data="ignore"),
            InlineKeyboardButton(text="▶️", callback_data=cb_next)
        ])
        
    # 3. Status Filters Row
    # We display a row of status buttons. To keep it clean, we can show them in a grid
    status_row_1 = [
        InlineKeyboardButton(
            text=f"🟢 {STATUS_LABELS['all']}" if status == "all" else STATUS_LABELS['all'],
            callback_data=f"ab_l:all:{tent}:{sort}:1"
        ),
        InlineKeyboardButton(
            text=f"🟢 {STATUS_LABELS['await']}" if status == "await" else STATUS_LABELS['await'],
            callback_data=f"ab_l:await:{tent}:{sort}:1"
        ),
        InlineKeyboardButton(
            text=f"🟢 {STATUS_LABELS['review']}" if status == "review" else STATUS_LABELS['review'],
            callback_data=f"ab_l:review:{tent}:{sort}:1"
        )
    ]
    status_row_2 = [
        InlineKeyboardButton(
            text=f"🟢 {STATUS_LABELS['conf']}" if status == "conf" else STATUS_LABELS['conf'],
            callback_data=f"ab_l:conf:{tent}:{sort}:1"
        ),
        InlineKeyboardButton(
            text=f"🟢 {STATUS_LABELS['canc']}" if status == "canc" else STATUS_LABELS['canc'],
            callback_data=f"ab_l:canc:{tent}:{sort}:1"
        )
    ]
    buttons.append(status_row_1)
    buttons.append(status_row_2)
    
    # 4. Sorting & Tent Selector Row
    sort_label = "🆕 Спочатку нові" if sort == "c_desc" else ("⏳ Старі" if sort == "c_asc" else "📅 По даті заїзду")
    tent_label = "🛖 Шатра: Всі" if tent == "all" else f"🛖 Шатро: №{tent}"
    
    # Toggle sorting
    next_sort = "c_asc" if sort == "c_desc" else ("date" if sort == "c_asc" else "c_desc")
    
    buttons.append([
        InlineKeyboardButton(text=f"🔄 {sort_label}", callback_data=f"ab_l:{status}:{tent}:{next_sort}:1"),
        InlineKeyboardButton(text=tent_label, callback_data=f"ab_tf_show:{status}:{tent}:{sort}:{page}")
    ])
    
    # 5. Back to menu button
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tent_filter_kb(status: str, current_tent: str, sort: str, page: str) -> InlineKeyboardMarkup:
    """Builds a 1-10 grid of tent number selections for filtering."""
    buttons = []
    
    # Grid of 1-10
    row = []
    for i in range(1, 11):
        lbl = f"🛖 №{i}"
        if current_tent == str(i):
            lbl = f"🟢 №{i}"
        row.append(InlineKeyboardButton(text=lbl, callback_data=f"ab_l:{status}:{i}:{sort}:1"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    # All tents button
    all_lbl = "🟢 Всі шатра" if current_tent == "all" else "🛖 Всі шатра"
    buttons.append([InlineKeyboardButton(text=all_lbl, callback_data=f"ab_l:{status}:all:{sort}:1")])
    
    # Back to list
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до списку", callback_data=f"ab_l:{status}:{current_tent}:{sort}:{page}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_booking_details_kb(
    booking_id: int,
    status: BookingStatus,
    back_cb: str,
    has_screenshot: bool = False
) -> InlineKeyboardMarkup:
    buttons = []
    
    # Action row depending on status
    action_row = []
    if status == BookingStatus.payment_pending_review:
        action_row.append(InlineKeyboardButton(text="✅ Схвалити", callback_data=f"ab_ok:{booking_id}:{back_cb}"))
        action_row.append(InlineKeyboardButton(text="❌ Відхилити", callback_data=f"ap_rj:{booking_id}:{back_cb}"))
    elif status == BookingStatus.awaiting_payment:
        action_row.append(InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"ab_ok:{booking_id}:{back_cb}"))
        action_row.append(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"ab_no:{booking_id}:{back_cb}"))
    elif status == BookingStatus.confirmed:
        action_row.append(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"ab_no:{booking_id}:{back_cb}"))
        
    if action_row:
        buttons.append(action_row)
        
    # Screenshot row
    if has_screenshot:
        buttons.append([InlineKeyboardButton(text="📸 Переглянути чек", callback_data=f"ab_ss:{booking_id}:{back_cb}")])
        
    # Client Profile & Delete row
    # To view client profile: client profile callback
    buttons.append([
        InlineKeyboardButton(text="👤 Клієнт", callback_data=f"ab_client:{booking_id}:{back_cb}"),
        InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"ab_del:{booking_id}:{back_cb}")
    ])
    
    # Back button
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
