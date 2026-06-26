from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.config import settings
from bot.states.payment_states import PaymentStates
from bot.database.models import Booking, BookingStatus, User
from bot.database.queries import (
    save_payment_screenshot,
    log_activity,
    get_booking_price
)
from bot.keyboards.payment_kb import (
    admin_payment_review_kb,
    retry_payment_kb
)
from bot.keyboards.main_menu import get_main_menu

router = Router()

# --- USER CLICKED "Я оплатив(ла)" ---
@router.callback_query(F.data.startswith("payment_sent:"))
async def user_payment_sent(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[1])
    await state.update_data(booking_id=booking_id)
    await state.set_state(PaymentStates.waiting_screenshot)
    
    await callback.message.answer(
        "📸 Надішліть скріншот підтвердження оплати\n"
        "(фото або документ з Monobank)"
    )
    await callback.answer()

# --- USER SENDS SCREENSHOT ---
@router.message(StateFilter(PaymentStates.waiting_screenshot), F.photo | F.document)
async def receive_screenshot(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    booking_id = data.get("booking_id")
    
    if not booking_id:
        await message.answer("⚠️ Помилка сесії. Будь ласка, почніть бронювання спочатку.")
        await state.clear()
        return

    # Extract file_id
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id

    # Fetch booking
    booking = await session.get(Booking, booking_id)
    if not booking:
        await message.answer("⚠️ Бронювання не знайдено.")
        await state.clear()
        return

    # Update database status
    await save_payment_screenshot(session, booking_id, file_id)
    booking.status = BookingStatus.payment_pending_review
    await session.commit()

    date_str = booking.booking_date.strftime("%d.%m.%Y")
    
    await log_activity(
        session=session,
        action_type="payment_submitted",
        details=f"Клієнт {booking.client_name} надіслав скріншот оплати для броні #{booking_id} (Шатро №{booking.shelter_num}, {date_str})",
        booking_id=booking_id,
        user_id=message.from_user.id
    )

    # Respond to client
    await message.answer(
        "✅ Дякуємо! Ваш платіж на перевірці.\n\n"
        "⏳ Адміністратор перевірить оплату протягом кількох годин. "
        "Ви отримаєте сповіщення про підтвердження.\n\n"
        f"📋 <b>Деталі бронювання:</b>\n"
        f"🛖 Шатро №{booking.shelter_num} | 📅 {date_str}\n"
        f"👤 {booking.client_name}",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

    # Get all admin IDs from both config (.env) and database
    db_admins_res = await session.execute(select(User.telegram_id).where(User.is_admin == True))
    all_admin_ids = set(settings.ADMIN_IDS) | {row[0] for row in db_admins_res.fetchall()}

    # Read price from booking amount saved in DB
    price = booking.amount

    # Send screenshot with details to all admins
    admin_caption = (
        f"🔔 <b>НОВА ОПЛАТА НА ПЕРЕВІРЦІ</b>\n\n"
        f"📋 <b>Бронювання:</b> #{booking.id}\n"
        f"🛖 <b>Шатро:</b> Шатро №{booking.shelter_num}\n"
        f"📅 <b>Дата:</b> {date_str}\n"
        f"👤 <b>Клієнт:</b> {booking.client_name}\n"
        f"📞 <b>Телефон:</b> {booking.client_phone}\n"
        f"💰 <b>Сума до сплати:</b> {price} грн\n\n"
        f"📝 <b>Коментар для Monobank:</b> <code>{booking.client_name} {date_str}</code>"
    )

    for admin_id in all_admin_ids:
        try:
            if message.photo:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_payment_review_kb(booking_id)
                )
            else:
                await bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_payment_review_kb(booking_id)
                )
        except Exception:
            pass

    await state.clear()

# --- USER CANCELS BOOKING ---
@router.callback_query(F.data.startswith("cancel_booking:"))
async def user_cancel_booking(callback: CallbackQuery, session: AsyncSession):
    booking_id = int(callback.data.split(":")[1])
    
    booking = await session.get(Booking, booking_id)
    if booking:
        if booking.status in (BookingStatus.awaiting_payment, BookingStatus.payment_pending_review):
            booking.status = BookingStatus.cancelled
            await session.commit()
            
            await log_activity(
                session=session,
                action_type="cancelled",
                details=f"Клієнт скасував неоплачене бронювання #{booking_id} (Шатро №{booking.shelter_num}, {booking.booking_date.strftime('%d.%m.%Y')})",
                booking_id=booking_id,
                user_id=callback.from_user.id
            )
            
            await callback.message.answer(
                "❌ Бронювання скасовано.",
                reply_markup=get_main_menu()
            )
            try:
                await callback.message.delete()
            except Exception:
                pass
        else:
            await callback.answer("Цією кнопкою можна скасувати лише бронювання, що очікують оплати.", show_alert=True)
    else:
        await callback.answer("Бронювання не знайдено.", show_alert=True)

