# bot/handlers/booking.py
from datetime import date, datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.states.booking_states import BookingFSM
from bot.database.models import BookingStatus
from bot.database.queries import (
    create_booking,
    get_booked_shelters_on_date,
    log_activity
)
from bot.keyboards.booking_kb import (
    get_booking_dates_kb,
    get_free_shelters_kb,
    get_phone_keyboard,
    get_confirmation_kb
)
from bot.keyboards.main_menu import get_main_menu

router = Router()

async def start_booking(chat_id: int, state: FSMContext, bot: Bot):
    """Starts the booking FSM by prompting the user to select a date first."""
    await state.clear()
    await state.set_state(BookingFSM.choosing_date)
    await bot.send_message(
        chat_id=chat_id,
        text="📅 <b>Бронювання шатра</b>\n\nКрок 1: Оберіть дату заїзду на найближчі 2 тижні 👇",
        reply_markup=get_booking_dates_kb()
    )

@router.message(F.text == "📅 Забронювати")
@router.message(Command("booking"))
async def cmd_booking(message: Message, state: FSMContext, bot: Bot):
    await start_booking(message.chat.id, state, bot)

# Cancel click inside booking FSM
@router.callback_query(F.data == "cancel_booking_flow")
async def cancel_booking_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer("Бронювання скасовано.")
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass
    await state.clear()
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text="❌ Бронювання скасовано.",
        reply_markup=get_main_menu()
    )

# Step 1: Date selected
@router.callback_query(StateFilter(BookingFSM.choosing_date), F.data.startswith("book_date_"))
async def process_date_selected(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await callback_query.answer()
    selected_date_str = callback_query.data.split("_")[-1]
    booking_date = date.fromisoformat(selected_date_str)
    
    await state.update_data(booking_date=selected_date_str)
    
    # Query booked shatras on this date
    booked_shelters = await get_booked_shelters_on_date(session, booking_date)
    free_shelters = [i for i in range(1, 11) if i not in booked_shelters]
    
    date_formatted = booking_date.strftime("%d.%m.%Y")
    
    if not free_shelters:
        # If all 10 shatras are booked
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"⚠️ На жаль, на <b>{date_formatted}</b> немає вільних шатер.\n\nОберіть іншу дату 👇",
            reply_markup=get_booking_dates_kb()
        )
        return
        
    await state.set_state(BookingFSM.choosing_shelter)
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=(
            f"📅 Обрана дата: <b>{date_formatted}</b>\n\n"
            f"Крок 2: Оберіть вільне шатро 👇"
        ),
        reply_markup=get_free_shelters_kb(free_shelters)
    )

# Handle Change Date callback
@router.callback_query(StateFilter(BookingFSM.choosing_shelter), F.data == "change_date")
async def process_change_date(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    await state.set_state(BookingFSM.choosing_date)
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="📅 <b>Бронювання шатра</b>\n\nКрок 1: Оберіть дату заїзду на найближчі 2 тижні 👇",
        reply_markup=get_booking_dates_kb()
    )

# Step 2: Shelter selected
@router.callback_query(StateFilter(BookingFSM.choosing_shelter), F.data.startswith("book_shelter_"))
async def process_shelter_selected(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    shelter_num = int(callback_query.data.split("_")[-1])
    await state.update_data(shelter_num=shelter_num)
    
    await state.set_state(BookingFSM.entering_name)
    
    # Delete the inline keyboard message and prompt for name
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass
        
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text="👤 Крок 3: Введіть ваше ім'я та прізвище (мінімум 2 символи):",
        reply_markup=ReplyKeyboardRemove()
    )

# Step 3: Entering Name
@router.message(StateFilter(BookingFSM.entering_name))
async def process_entering_name(message: Message, state: FSMContext):
    name = message.text.strip() if message.text else ""
    if len(name) < 2:
        await message.answer("⚠️ Ім'я має бути не менше 2 символів. Введіть ще раз:")
        return
        
    await state.update_data(client_name=name)
    await state.set_state(BookingFSM.sharing_phone)
    
    await message.answer(
        text="📞 Крок 4: Поділіться вашим номером телефону за допомогою кнопки нижче 👇",
        reply_markup=get_phone_keyboard()
    )

# Step 4: Phone sharing (Contact or text)
@router.message(StateFilter(BookingFSM.sharing_phone), F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(client_phone=phone)
    await show_confirmation_summary(message, state)

@router.message(StateFilter(BookingFSM.sharing_phone))
async def process_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip() if message.text else ""
    # Basic validation for digits count
    cleaned = "".join(filter(str.isdigit, phone))
    if len(cleaned) < 9:
        await message.answer("⚠️ Некоректний формат телефону. Будь ласка, поділіться контактом через кнопку або введіть вірний номер 👇")
        return
        
    await state.update_data(client_phone=phone)
    await show_confirmation_summary(message, state)

async def show_confirmation_summary(message: Message, state: FSMContext):
    """Renders final booking summary."""
    await state.set_state(BookingFSM.confirming)
    data = await state.get_data()
    
    booking_date = date.fromisoformat(data["booking_date"])
    date_ua_format = booking_date.strftime("%d.%m.%Y")
    
    confirm_text = (
        "🏖 <b>Підтвердіть бронювання</b>\n\n"
        f"🛖 Шатро №{data['shelter_num']}\n"
        f"📅 Дата: {date_ua_format}\n"
        f"👤 Ім'я: {data['client_name']}\n"
        f"📞 Телефон: {data['client_phone']}\n"
        "👥 2 дорослих"
    )
    
    await message.answer(
        text=confirm_text,
        reply_markup=get_confirmation_kb()
    )

# Step 5: Final confirmation callback
@router.callback_query(StateFilter(BookingFSM.confirming), F.data == "confirm_booking_final")
async def process_booking_confirmed(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await callback_query.answer()
    data = await state.get_data()
    
    booking_date = date.fromisoformat(data["booking_date"])
    date_ua_format = booking_date.strftime("%d.%m.%Y")
    
    # Save booking to database
    booking = await create_booking(
        session=session,
        user_id=callback_query.from_user.id,
        shelter_num=data["shelter_num"],
        booking_date=booking_date,
        client_name=data["client_name"],
        client_phone=data["client_phone"]
    )
    await session.commit()
    
    await log_activity(
        session=session,
        action_type="created",
        details=f"Користувач {booking.client_name} ({booking.client_phone}) забронював Шатро №{booking.shelter_num} на {date_ua_format} (ID: {booking.id})",
        booking_id=booking.id,
        user_id=callback_query.from_user.id
    )
    
    # Delete confirmation summary card
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass
        
    # Send success response to client
    success_text = (
        "✅ <b>Заявку прийнято!</b>\n\n"
        f"🛖 Шатро №{booking.shelter_num}\n"
        f"📅 {date_ua_format}\n"
        f"👤 {booking.client_name}\n\n"
        "⏳ Очікуйте підтвердження від адміністратора."
    )
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=success_text,
        reply_markup=get_main_menu()
    )
    
    # Send alert to all Admin IDs
    created_at_str = booking.created_at.strftime("%H:%M %d.%m.%Y")
    admin_text = (
        f"🔔 <b>Нова заявка #{booking.id}</b>\n\n"
        f"🛖 Шатро №{booking.shelter_num}\n"
        f"📅 {date_ua_format}\n"
        f"👤 {booking.client_name}\n"
        f"📞 {booking.client_phone}\n"
        f"🕐 {created_at_str}"
    )
    
    # Setup actions keyboard for admin alert
    from bot.keyboards.admin_kb import get_pending_booking_actions_kb
    admin_kb = get_pending_booking_actions_kb(booking.id)
    
    # Get all admin IDs from both config (.env) and database
    from bot.database.models import User
    from sqlalchemy import select
    db_admins_res = await session.execute(select(User.telegram_id).where(User.is_admin == True))
    all_admin_ids = set(settings.ADMIN_IDS) | {row[0] for row in db_admins_res.fetchall()}
    
    for admin_id in all_admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_kb)
        except Exception:
            pass
            
    await state.clear()

