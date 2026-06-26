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
            callback_data=f"ap_ok:{booking_id}:admin_menu"
        )],
        [InlineKeyboardButton(
            text="❌ Відхилити оплату",
            callback_data=f"ap_rj:{booking_id}:admin_menu"
        )]
    ])




def retry_payment_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Button for user to retry payment after rejection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатив(ла) повторно",
            callback_data=f"payment_sent:{booking_id}"
        )]
    ])
