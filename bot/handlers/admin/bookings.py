# bot/handlers/admin/bookings.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import math

from bot.config import settings
from bot.database.models import BookingStatus
from bot.database.queries import (
    get_bookings_filtered,
    get_booking_full,
    get_latest_payment,
    admin_confirm_booking,
    admin_cancel_booking,
    admin_delete_booking,
    log_activity
)
from bot.keyboards.admin.bookings_kb import (
    get_bookings_list_kb,
    get_tent_filter_kb,
    get_booking_details_kb
)
from bot.states.admin_states import AdminBookingActions
from bot.handlers.admin.main_menu import is_admin

router = Router()

ITEMS_PER_PAGE = 10

def map_status_to_query(status: str) -> str:
    if status == "await":
        return "awaiting_payment"
    if status == "review":
        return "pending"
    if status == "conf":
        return "confirmed"
    if status == "canc":
        return "cancelled"
    return "all"

def map_sort_to_query(sort: str) -> str:
    if sort == "c_desc":
        return "created_desc"
    if sort == "c_asc":
        return "created_asc"
    if sort == "date":
        return "checkin"
    return "created_desc"

async def show_bookings_list_internal(
    message: Message,
    status: str,
    tent: str,
    sort: str,
    page: int,
    session: AsyncSession,
    bot: Bot
):
    q_status = map_status_to_query(status)
    q_tent = int(tent) if tent != "all" else None
    q_sort = map_sort_to_query(sort)
    
    offset = (page - 1) * ITEMS_PER_PAGE
    bookings, total_count = await get_bookings_filtered(
        session, status=q_status, tent_number=q_tent, sort_by=q_sort, limit=ITEMS_PER_PAGE, offset=offset
    )
    
    total_pages = math.ceil(total_count / ITEMS_PER_PAGE) or 1
    
    kb = get_bookings_list_kb(bookings, page, total_pages, status, tent, sort)
    
    lbl_status = "Всі"
    if status == "await": lbl_status = "Очікують оплати"
    elif status == "review": lbl_status = "Перевірка оплати"
    elif status == "conf": lbl_status = "Підтверджені"
    elif status == "canc": lbl_status = "Скасовані"
    
    lbl_tent = "всіх шатер" if tent == "all" else f"шатра №{tent}"
    
    text = (
        f"📋 <b>Список бронювань</b>\n\n"
        f"🔍 Фільтр: <b>{lbl_status}</b> для <b>{lbl_tent}</b>\n"
        f"📊 Всього знайдено: <b>{total_count}</b>\n\n"
        f"Оберіть бронювання для перегляду деталей:"
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

# Entry point 1: Pending bookings shortcut from dashboard
@router.callback_query(F.data == "admin_pending")
async def callback_admin_pending_shortcut(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_bookings_list_internal(callback_query.message, "await", "all", "c_desc", 1, session, bot)

# Entry point 2: All bookings shortcut from dashboard
@router.callback_query(F.data.startswith("admin_all_"))
async def callback_admin_all_shortcut(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    parts = callback_query.data.split("_")
    page = int(parts[-1]) if parts[-1].isdigit() else 1
    await show_bookings_list_internal(callback_query.message, "all", "all", "c_desc", page, session, bot)

# Generic paginated/filtered listing
@router.callback_query(F.data.startswith("ab_l:"))
async def callback_bookings_list_filtered(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    # Format: ab_l:<status>:<tent>:<sort>:<page>
    parts = callback_query.data.split(":")
    status = parts[1]
    tent = parts[2]
    sort = parts[3]
    page = int(parts[4])
    await show_bookings_list_internal(callback_query.message, status, tent, sort, page, session, bot)

# Show tent filter grid
@router.callback_query(F.data.startswith("ab_tf_show:"))
async def callback_bookings_tent_filter_show(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    # Format: ab_tf_show:<status>:<tent>:<sort>:<page>
    parts = callback_query.data.split(":")
    status = parts[1]
    current_tent = parts[2]
    sort = parts[3]
    page = parts[4]
    
    kb = get_tent_filter_kb(status, current_tent, sort, page)
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="🛖 <b>Оберіть шатро для фільтрації списку:</b>",
        reply_markup=kb
    )

# Booking details card
@router.callback_query(F.data.startswith("ab_v:"))
async def callback_booking_details(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    # Format: ab_v:<booking_id>:<back_cb>
    # where back_cb might contain colons: e.g. ab_l:all:all:c_desc:1 or ab_sch_d:2026-06-26
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    b = await get_booking_full(session, booking_id)
    if not b:
        await callback_query.answer("Бронювання не знайдено", show_alert=True)
        return
        
    status_label = "⏳ Очікує оплати"
    if b.status == BookingStatus.payment_pending_review:
        status_label = "🔍 Перевірка оплати"
    elif b.status == BookingStatus.confirmed:
        status_label = "✅ Підтверджено"
    elif b.status == BookingStatus.cancelled:
        status_label = "❌ Скасовано"
        
    comment_text = f"\n📝 <b>Коментар/Причина:</b> <i>{b.admin_comment}</i>" if b.admin_comment else ""
    created_at_str = b.created_at.strftime("%H:%M %d.%m.%Y")
    
    text = (
        f"📌 <b>Деталі заявки #{b.id}</b>\n\n"
        f"🛖 <b>Шатро:</b> Шатро №{b.shelter_num}\n"
        f"📅 <b>Дата:</b> {b.booking_date.strftime('%d.%m.%Y')}\n\n"
        f"👤 <b>Клієнт:</b> {b.client_name}\n"
        f"📞 <b>Телефон:</b> {b.client_phone}\n\n"
        f"🚦 <b>Статус:</b> {status_label}"
        f"{comment_text}\n"
        f"🕐 <b>Подано:</b> {created_at_str}"
    )
    
    payment = await get_latest_payment(session, booking_id)
    has_screenshot = payment is not None and bool(payment.screenshot_file_id)
    
    kb = get_booking_details_kb(b.id, b.status, back_cb, has_screenshot=has_screenshot)
    
    if callback_query.message.photo:
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=text,
            reply_markup=kb
        )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=kb
        )

# Approve / Confirm booking
@router.callback_query(F.data.startswith("ab_ok:"))
async def callback_booking_approve(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    await admin_confirm_booking(session, booking_id, callback_query.from_user.id)
    await callback_query.answer("Бронювання схвалено!")
    
    b = await get_booking_full(session, booking_id)
    if b:
        # Log
        await log_activity(
            session, "confirmed", 
            f"Адмін підтвердив бронь #{b.id} (Шатро №{b.shelter_num}, {b.booking_date.strftime('%d.%m.%Y')}, {b.client_name})",
            booking_id=b.id, user_id=callback_query.from_user.id
        )
        # Notify
        try:
            await bot.send_message(
                chat_id=b.user_id,
                text=(
                    f"✅ <b>Ваше бронювання підтверджено!</b>\n\n"
                    f"🛖 Шатро №{b.shelter_num}\n"
                    f"📅 {b.booking_date.strftime('%d.%m.%Y')}\n\n"
                    f"Чекаємо на вас! З усіх питань звертайтесь за телефоном: {settings.RESORT_PHONE}"
                )
            )
        except Exception:
            pass
            
    # Refresh view
    # Rebuild details view manually or call the callback handler
    # Modifying callback_query.data to trigger ab_v handler
    callback_query.data = f"ab_v:{booking_id}:{back_cb}"
    await callback_booking_details(callback_query, session, bot)

# Cancel booking request (ask for comment)
@router.callback_query(F.data.startswith("ab_no:"))
async def callback_booking_cancel_request(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    await state.set_state(AdminBookingActions.waiting_cancel_reason)
    await state.update_data(
        booking_id=booking_id,
        back_cb=back_cb,
        orig_msg_id=callback_query.message.message_id
    )
    
    cancel_kb = get_booking_details_kb(booking_id, BookingStatus.cancelled, back_cb, False)
    # We display a prompt to write cancellation comment
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f"✍️ <b>Введіть причину скасування для заявки #{booking_id}:</b>",
    )

# Receive cancellation comment
@router.message(AdminBookingActions.waiting_cancel_reason)
async def process_booking_cancel_reason(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        return
        
    data = await state.get_data()
    booking_id = data["booking_id"]
    back_cb = data["back_cb"]
    orig_msg_id = data["orig_msg_id"]
    
    reason = message.text.strip() if message.text else "Скасовано адміністратором"
    
    await admin_cancel_booking(session, booking_id, reason, message.from_user.id)
    await state.clear()
    
    b = await get_booking_full(session, booking_id)
    if b:
        # Log
        await log_activity(
            session, "cancelled",
            f"Адмін скасував бронь #{b.id} (Шатро №{b.shelter_num}) з причиною: {reason}",
            booking_id=b.id, user_id=message.from_user.id
        )
        # Notify
        try:
            await bot.send_message(
                chat_id=b.user_id,
                text=(
                    f"❌ <b>Ваше бронювання скасовано.</b>\n\n"
                    f"🛖 Шатро №{b.shelter_num}\n"
                    f"📅 {b.booking_date.strftime('%d.%m.%Y')}\n"
                    f"📝 <b>Причина:</b> {reason}\n\n"
                    f"З усіх питань звертайтесь за телефоном: {settings.RESORT_PHONE}"
                )
            )
        except Exception:
            pass
            
    await message.answer(f"✅ Бронювання #{booking_id} успішно скасовано.")
    
    # Send updated details card as a new message
    b = await get_booking_full(session, booking_id)
    comment_text = f"\n📝 <b>Коментар/Причина:</b> <i>{b.admin_comment}</i>"
    created_at_str = b.created_at.strftime("%H:%M %d.%m.%Y")
    
    text = (
        f"📌 <b>Деталі заявки #{b.id}</b>\n\n"
        f"🛖 <b>Шатро:</b> Шатро №{b.shelter_num}\n"
        f"📅 <b>Дата:</b> {b.booking_date.strftime('%d.%m.%Y')}\n\n"
        f"👤 <b>Клієнт:</b> {b.client_name}\n"
        f"📞 <b>Телефон:</b> {b.client_phone}\n\n"
        f"🚦 <b>Статус:</b> ❌ Скасовано"
        f"{comment_text}\n"
        f"🕐 <b>Подано:</b> {created_at_str}"
    )
    kb = get_booking_details_kb(b.id, b.status, back_cb, False)
    await message.answer(text=text, reply_markup=kb)

# View screenshot
@router.callback_query(F.data.startswith("ab_ss:"))
async def callback_booking_screenshot(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    payment = await get_latest_payment(session, booking_id)
    if payment and payment.screenshot_file_id:
        # Delete original details message
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        # Show photo
        from bot.keyboards.admin.payments_kb import get_payment_review_kb
        # We can view using the back_cb back to details
        # Let's map back_cb to a details callback so they return to details card
        details_back_cb = f"ab_v:{booking_id}:{back_cb}"
        kb = get_payment_review_kb(booking_id, details_back_cb)
        await bot.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=payment.screenshot_file_id,
            caption=f"📸 Чек про оплату для бронювання #{booking_id}:",
            reply_markup=kb
        )
    else:
        await callback_query.answer("Чек не знайдено.", show_alert=True)

# Delete booking
@router.callback_query(F.data.startswith("ab_del:"))
async def callback_booking_delete(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    # Fetch details to log
    b = await get_booking_full(session, booking_id)
    if b:
        details = f"Адмін видалив бронь #{b.id} (Шатро №{b.shelter_num}, {b.booking_date.strftime('%d.%m.%Y')}, {b.client_name})"
        await admin_delete_booking(session, booking_id)
        await log_activity(session, "deleted", details, user_id=callback_query.from_user.id)
        
    await callback_query.answer("Бронювання назавжди видалено з бази даних.", show_alert=True)
    
    # Return to previous list using the back callback
    # If the back_cb starts with ab_l, we trigger the list renderer
    if back_cb.startswith("ab_l:"):
        callback_query.data = back_cb
        await callback_bookings_list_filtered(callback_query, session, bot)
    else:
        # Default back to main menu
        from bot.handlers.admin.main_menu import callback_admin_menu
        callback_query.data = "admin_menu"
        await callback_admin_menu(callback_query, bot, session, None)

# View client profile from booking details
@router.callback_query(F.data.startswith("ab_client:"))
async def callback_booking_client_profile(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    booking_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    b = await get_booking_full(session, booking_id)
    if not b:
        await callback_query.answer("Бронювання не знайдено.", show_alert=True)
        return
    
    # Redirect to client profile viewer with back_cb pointing back to the booking details
    details_back = f"ab_v:{booking_id}:{back_cb}"
    from bot.handlers.admin.clients import callback_client_profile
    callback_query.data = f"ac_v:{b.user_id}:{details_back}"
    await callback_client_profile(callback_query, session, bot)
