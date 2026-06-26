from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def payment_instructions_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Returns keyboard with options for user after creating a booking awaiting payment."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатив(ла)",
            callback_data=f"payment_sent:{booking_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Скасувати бронювання",
            callback_data=f"cancel_booking:{booking_id}"
        )]
    ])

def admin_payment_review_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Returns actions for admin review of payment screenshot."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Підтвердити оплату",
            callback_data=f"admin_confirm_payment:{booking_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Відхилити оплату",
            callback_data=f"admin_reject_payment:{booking_id}"
        )]
    ])

def reject_reason_kb(booking_id: int, back_callback: str) -> InlineKeyboardMarkup:
    """Predefined rejection reasons for admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сума не співпадає", callback_data="reject_reason:amount")],
        [InlineKeyboardButton(text="📝 Коментар не вірний", callback_data="reject_reason:comment")],
        [InlineKeyboardButton(text="📸 Скріншот нечіткий", callback_data="reject_reason:screenshot")],
        [InlineKeyboardButton(text="✏️ Інша причина", callback_data="reject_reason:other")],
        [InlineKeyboardButton(text="⬅️ Назад (Не відхиляти)", callback_data=f"adm_view_{booking_id}_{back_callback}")]
    ])

def retry_payment_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Button for user to retry payment after rejection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатив(ла) повторно",
            callback_data=f"payment_sent:{booking_id}"
        )]
    ])
