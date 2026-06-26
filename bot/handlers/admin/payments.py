# bot/handlers/admin/payments.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import math

from bot.config import settings
from bot.database.models import BookingStatus, Booking
from bot.database.queries import (
    get_pending_bookings,
    get_latest_payment,
    admin_confirm_booking,
    admin_cancel_booking,
    reject_payment,
    log_activity,
    get_booking_full
)
from bot.keyboards.admin.payments_kb import (
    get_payments_list_kb,
    get_payment_review_kb,
    get_payment_rejection_reasons_kb
)
from bot.states.admin_states import AdminPaymentActions
from bot.handlers.admin.main_menu import is_admin

router = Router()

ITEMS_PER_PAGE = 10

# Helper to map rejection reason key to Ukrainian text
REJECTION_REASONS = {
    "date_sum": "Не видно дату або суму операції.",
    "blurry": "Скріншот обрізаний або розмитий.",
    "amount": "Невірна сума оплати.",
    "dup": "Чек дублюється (вже був надісланий раніше)."
}

async def show_payments_list_internal(
    message: Message,
    page: int,
    session: AsyncSession,
    bot: Bot
):
    bookings = await get_pending_bookings(session)
    total = len(bookings)
    total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
    
    if page > total_pages:
        page = total_pages
        
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_bookings = bookings[start:end]
    
    # Resolve payments for these bookings
    payments = []
    for b in page_bookings:
        payment = await get_latest_payment(session, b.id)
        if payment:
            payment.booking = b
            payments.append(payment)
            
    kb = get_payments_list_kb(payments, page, total_pages)
    
    text = (
        f"💳 <b>Перевірка оплат (всього очікує: {total})</b>\n\n"
        f"Оберіть платіж для перегляду скріншота та підтвердження:"
    )
    
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=kb
        )
    except Exception:
        await message.answer(text=text, reply_markup=kb)

@router.callback_query(F.data.startswith("admin_payments_"))
async def callback_admin_payments_list(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split("_")
    page = int(parts[-1]) if parts[-1].isdigit() else 1
    await show_payments_list_internal(callback_query.message, page, session, bot)

# View single payment screenshot
@router.callback_query(F.data.startswith("ap_v:"))
async def callback_view_payment(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    # Format: ap_v:<booking_id>:<back_cb>
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    payment = await get_latest_payment(session, booking_id)
    b = await get_booking_full(session, booking_id)
    
    if not payment or not payment.screenshot_file_id or not b:
        await callback_query.answer("Чек або бронювання не знайдено.", show_alert=True)
        return
        
    # Delete list message to avoid cluttering
    try:
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
    except Exception:
        pass
        
    kb = get_payment_review_kb(booking_id, back_cb)
    
    caption = (
        f"📸 <b>Перевірка оплати для броні #{b.id}</b>\n\n"
        f"🛖 Шатро №{b.shelter_num} | 📅 {b.booking_date.strftime('%d.%m.%Y')}\n"
        f"👤 Клієнт: {b.client_name} ({b.client_phone})\n"
        f"💳 Сума переказу: {payment.amount} грн\n"
        f"💳 Карта: {payment.monobank_card}\n"
        f"💬 Коментар клієнта: {payment.payment_comment or 'відсутній'}"
    )
    
    await bot.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=payment.screenshot_file_id,
        caption=caption,
        reply_markup=kb,
        parse_mode="HTML"
    )

# Approve Payment
@router.callback_query(F.data.startswith("ap_ok:"))
async def callback_approve_payment(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    await admin_confirm_booking(session, booking_id, callback_query.from_user.id)
    await callback_query.answer("Оплату схвалено, бронь підтверджено!")
    
    b = await get_booking_full(session, booking_id)
    if b:
        await log_activity(
            session, "confirmed",
            f"Адмін схвалив оплату для броні #{b.id} (Шатро №{b.shelter_num}, {b.client_name})",
            booking_id=b.id, user_id=callback_query.from_user.id
        )
        # Notify
        try:
            await bot.send_message(
                chat_id=b.user_id,
                text=(
                    f"✅ <b>Вашу оплату схвалено! Бронювання підтверджено.</b>\n\n"
                    f"🛖 Шатро №{b.shelter_num}\n"
                    f"📅 {b.booking_date.strftime('%d.%m.%Y')}\n\n"
                    f"Чекаємо на вас! З усіх питань звертайтесь за телефоном: {settings.RESORT_PHONE}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass
            
    # Delete current message (photo or text)
    try:
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
    except Exception:
        pass
        
    # Redirect back using shared helper
    await _redirect_after_payment_action(callback_query, back_cb, session, bot)

# Show rejection options
@router.callback_query(F.data.startswith("ap_rj:"))
async def callback_reject_payment_options(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    kb = get_payment_rejection_reasons_kb(booking_id, back_cb)
    
    # If current message is a photo — edit caption; if text — edit text
    if callback_query.message.photo or callback_query.message.document:
        try:
            await bot.edit_message_caption(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                caption="⚠️ <b>Оберіть або введіть причину відхилення оплати:</b>",
                reply_markup=kb,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
    # Fallback: edit text or send new message
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="⚠️ <b>Оберіть або введіть причину відхилення оплати:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text="⚠️ <b>Оберіть або введіть причину відхилення оплати:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )

# Perform Rejection (pre-defined or setup FSM for custom)
@router.callback_query(F.data.startswith("ap_r:"))
async def callback_reject_payment_action(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    reason_key = parts[1]
    booking_id = int(parts[2])
    back_cb = ":".join(parts[3:])
    
    if reason_key == "custom":
        await state.set_state(AdminPaymentActions.waiting_rejection_reason)
        await state.update_data(
            booking_id=booking_id,
            back_cb=back_cb,
            orig_msg_id=callback_query.message.message_id
        )
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=f"✍️ <b>Введіть свою причину відхилення оплати для заявки #{booking_id}:</b>"
        )
    else:
        reason_text = REJECTION_REASONS.get(reason_key, "Оплата відхилена адміністратором.")
        await finalize_payment_rejection_internal(
            callback_query.message, booking_id, reason_text, back_cb, session, bot
        )

# Receive custom rejection comment
@router.message(AdminPaymentActions.waiting_rejection_reason)
async def process_custom_rejection_text(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        return
        
    data = await state.get_data()
    booking_id = data["booking_id"]
    back_cb = data["back_cb"]
    orig_msg_id = data["orig_msg_id"]
    
    reason_text = message.text.strip() if message.text else "Некоректний скріншот оплати."
    await state.clear()
    
    # Try to delete the photo screen
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=orig_msg_id)
    except Exception:
        pass
        
    await finalize_payment_rejection_internal(
        message, booking_id, reason_text, back_cb, session, bot
    )

async def finalize_payment_rejection_internal(
    message: Message,
    booking_id: int,
    reason: str,
    back_cb: str,
    session: AsyncSession,
    bot: Bot
):
    # Reject in DB
    await reject_payment(session, booking_id, reason)
    
    # Revert booking status to awaiting_payment
    b = await session.get(Booking, booking_id)
    if b:
        b.status = BookingStatus.awaiting_payment
        await session.commit()
        
        # Log
        await log_activity(
            session, "payment_rejected",
            f"Адмін відхилив оплату для броні #{b.id} (Шатро №{b.shelter_num}, {b.client_name}). Причина: {reason}",
            booking_id=b.id, user_id=message.from_user.id
        )
        
        # Notify user (formatted card details)
        date_str = b.booking_date.strftime("%d.%m.%Y")
        comment = f"{b.client_name} {date_str}"
        cleaned_card = "".join(filter(str.isdigit, settings.MONOBANK_CARD))
        formatted_card = " ".join(cleaned_card[i:i+4] for i in range(0, len(cleaned_card), 4))
        
        from bot.keyboards.payment_kb import retry_payment_kb
        try:
            user_text = (
                "❌ <b>Оплату не підтверджено!</b>\n\n"
                f"<b>Причина відхилення:</b> <i>{reason}</i>\n\n"
                "Будь ласка, здійсніть оплату повторно та надішліть новий скріншот.\n\n"
                f"💳 <b>Карта Monobank:</b> <code>{formatted_card}</code>\n"
                f"👤 <b>Отримувач:</b> {settings.MONOBANK_CARD_OWNER}\n"
                f"📝 <b>Коментар до платежу:</b> <code>{comment}</code>"
            )
            await bot.send_message(
                chat_id=b.user_id,
                text=user_text,
                parse_mode="HTML",
                reply_markup=retry_payment_kb(booking_id)
            )
        except Exception:
            pass
            
    # Delete photo/current rejection prompt message if possible
    try:
        await message.delete()
    except Exception:
        pass
        
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Оплату для бронювання #{booking_id} відхилено. Клієнту надіслано сповіщення."
    )
    
    # Redirect back using shared helper
    # We need a fake CallbackQuery since finalize runs from Message context too
    fake_cb = CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=back_cb
    )
    await _redirect_after_payment_action(fake_cb, back_cb, session, bot)


async def _redirect_after_payment_action(
    callback_query: CallbackQuery,
    back_cb: str,
    session: AsyncSession,
    bot: Bot
):
    """Shared redirect logic after approving or rejecting a payment."""
    if back_cb == "admin_menu" or not back_cb:
        from bot.keyboards.admin.main_kb import get_admin_main_kb
        from bot.database.queries import count_bookings_by_status
        pending_bookings = await count_bookings_by_status(session, "awaiting_payment")
        pending_payments = await count_bookings_by_status(session, "payment_pending_review")
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
            reply_markup=get_admin_main_kb(pending_bookings, pending_payments),
            parse_mode="HTML"
        )
    elif back_cb.startswith("admin_payments_") or back_cb.isdigit():
        page = int(back_cb.split("_")[-1]) if not back_cb.isdigit() else int(back_cb)
        if not page or page < 1:
            page = 1
        msg = await bot.send_message(chat_id=callback_query.message.chat.id, text="Завантаження списку...")
        await show_payments_list_internal(msg, page, session, bot)
    elif back_cb.startswith("ab_v:") or back_cb.startswith("ab_l:"):
        from bot.handlers.admin.bookings import callback_booking_details, callback_bookings_list_filtered
        msg = await bot.send_message(chat_id=callback_query.message.chat.id, text="Завантаження...")
        fake_cb = CallbackQuery(
            id="0",
            from_user=callback_query.from_user,
            chat_instance="0",
            message=msg,
            data=back_cb
        )
        if back_cb.startswith("ab_v:"):
            await callback_booking_details(fake_cb, session, bot)
        else:
            await callback_bookings_list_filtered(fake_cb, session, bot)
    else:
        # Fallback: send admin menu
        from bot.keyboards.admin.main_kb import get_admin_main_kb
        from bot.database.queries import count_bookings_by_status
        pending_bookings = await count_bookings_by_status(session, "awaiting_payment")
        pending_payments = await count_bookings_by_status(session, "payment_pending_review")
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
            reply_markup=get_admin_main_kb(pending_bookings, pending_payments),
            parse_mode="HTML"
        )
