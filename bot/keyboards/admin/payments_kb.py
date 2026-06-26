# bot/keyboards/admin/payments_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_payments_list_kb(payments: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """List of pending payments screenshots for approval."""
    buttons = []
    
    for p in payments:
        b = p.booking # Booking is loaded
        if not b:
            continue
        date_str = b.booking_date.strftime("%d.%m")
        btn_text = f"🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name}"
        # Callback: ap_v:booking_id:page
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"ap_v:{b.id}:{page}")])
        
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        
        buttons.append([
            InlineKeyboardButton(text="◀️", callback_data=f"admin_payments_{prev_page}"),
            InlineKeyboardButton(text=f"Стор. {page}/{total_pages}", callback_data="ignore"),
            InlineKeyboardButton(text="▶️", callback_data=f"admin_payments_{next_page}")
        ])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_review_kb(booking_id: int, back_cb: str) -> InlineKeyboardMarkup:
    """Actions when viewing a payment screenshot."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Схвалити оплату", callback_data=f"ap_ok:{booking_id}:{back_cb}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"ap_rj:{booking_id}:{back_cb}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)
        ]
    ])

def get_payment_rejection_reasons_kb(booking_id: int, back_cb: str) -> InlineKeyboardMarkup:
    """Predefined reasons for payment rejection to save time."""
    # Prefix: ap_r:reason_key:booking_id:back_cb
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Не видно дату/суму", callback_data=f"ap_r:date_sum:{booking_id}:{back_cb}")],
        [InlineKeyboardButton(text="❌ Обрізаний або розмитий скріншот", callback_data=f"ap_r:blurry:{booking_id}:{back_cb}")],
        [InlineKeyboardButton(text="❌ Невірна сума оплати", callback_data=f"ap_r:amount:{booking_id}:{back_cb}")],
        [InlineKeyboardButton(text="❌ Чек дублюється (вже надісланий раніше)", callback_data=f"ap_r:dup:{booking_id}:{back_cb}")],
        [InlineKeyboardButton(text="✍️ Своя причина...", callback_data=f"ap_r:custom:{booking_id}:{back_cb}")],
        [InlineKeyboardButton(text="⬅️ Назад до перевірки", callback_data=f"ap_v:{booking_id}:{back_cb}")]
    ])
