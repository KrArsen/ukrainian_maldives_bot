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
    log_activity,
    create_payment,
    get_prices
)
from bot.keyboards.booking_kb import (
    get_free_shelters_kb,
    get_phone_keyboard,
    get_confirmation_kb
)
from bot.keyboards.calendar_kb import CalCb, build_client_calendar
from bot.keyboards.main_menu import get_main_menu
from bot.services.pricing import get_price_for_date, get_price_label

router = Router()

async def start_booking(chat_id: int, state: FSMContext, session: AsyncSession, bot: Bot):
    """Starts the booking FSM by prompting the user to select a date first."""
    await state.clear()
    await state.set_state(BookingFSM.choosing_date)
    
    today = date.today()
    kb = await build_client_calendar(session, today.year, today.month)
    
    await bot.send_message(
        chat_id=chat_id,
        text="📅 <b>Бронювання шатра</b>\n\nКрок 1: Оберіть дату заїзду 👇",
        reply_markup=kb
    )

@router.message(F.text == "📅 Забронювати")
@router.message(Command("booking"))
async def cmd_booking(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    await start_booking(message.chat.id, state, session, bot)

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

# --- CALENDAR NAVIGATION ---
@router.callback_query(StateFilter(BookingFSM.choosing_date), CalCb.filter(F.action == "prev"))
async def process_calendar_prev(callback_query: CallbackQuery, callback_data: CalCb, session: AsyncSession, bot: Bot):
    await callback_query.answer()
    kb = await build_client_calendar(session, callback_data.year, callback_data.month)
    await callback_query.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(StateFilter(BookingFSM.choosing_date), CalCb.filter(F.action == "next"))
async def process_calendar_next(callback_query: CallbackQuery, callback_data: CalCb, session: AsyncSession, bot: Bot):
    await callback_query.answer()
    kb = await build_client_calendar(session, callback_data.year, callback_data.month)
    await callback_query.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(StateFilter(BookingFSM.choosing_date), CalCb.filter(F.action == "cancel"))
async def process_calendar_cancel(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await cancel_booking_callback(callback_query, state, bot)

# --- DATE SELECTED FROM CALENDAR ---
@router.callback_query(StateFilter(BookingFSM.choosing_date), CalCb.filter(F.action == "day"))
async def process_calendar_day(
    callback_query: CallbackQuery,
    callback_data: CalCb,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot
):
    await callback_query.answer()
    booking_date = date(callback_data.year, callback_data.month, callback_data.day)
    
    # Query booked/blocked shatras on this date
    booked_shelters = await get_booked_shelters_on_date(session, booking_date)
    free_shelters = [i for i in range(1, 11) if i not in booked_shelters]
    
    date_formatted = booking_date.strftime("%d.%m.%Y (%A)")
    
    # Calculate price dynamically from DB settings
    weekday_price, weekend_price = await get_prices(session)
    price = get_price_for_date(booking_date, weekday_price, weekend_price)
    price_label = get_price_label(booking_date, weekday_price, weekend_price)
    
    await state.update_data(
        booking_date=booking_date.isoformat(),
        amount=price,
        price_label=price_label
    )
    
    if not free_shelters:
        kb = await build_client_calendar(session, callback_data.year, callback_data.month)
        await callback_query.message.edit_text(
            text=f"⚠️ На жаль, на <b>{booking_date.strftime('%d.%m.%Y')}</b> немає вільних шатер.\n\nОберіть іншу дату 👇",
            reply_markup=kb
        )
        return
        
    await state.set_state(BookingFSM.choosing_shelter)
    await callback_query.message.edit_text(
        text=(
            f"📅 Обрана дата: <b>{date_formatted}</b>\n"
            f"{price_label}\n\n"
            f"Крок 2: Оберіть вільне шатро 👇"
        ),
        reply_markup=get_free_shelters_kb(free_shelters)
    )

# Handle Change Date callback
@router.callback_query(StateFilter(BookingFSM.choosing_shelter), F.data == "change_date")
async def process_change_date(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await callback_query.answer()
    await state.set_state(BookingFSM.choosing_date)
    today = date.today()
    kb = await build_client_calendar(session, today.year, today.month)
    await callback_query.message.edit_text(
        text="📅 <b>Бронювання шатра</b>\n\nКрок 1: Оберіть дату заїзду 👇",
        reply_markup=kb
    )

# Step 2: Shelter selected
@router.callback_query(StateFilter(BookingFSM.choosing_shelter), F.data.startswith("book_shelter_"))
async def process_shelter_selected(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    shelter_num = int(callback_query.data.split("_")[-1])
    await state.update_data(shelter_num=shelter_num)
    
    await state.set_state(BookingFSM.entering_name)
    
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
    amount = data["amount"]
    price_label = data["price_label"]
    
    confirm_text = (
        "🏖 <b>Підтвердіть бронювання</b>\n\n"
        f"🛖 Шатро №{data['shelter_num']}\n"
        f"📅 Дата: {date_ua_format}\n"
        f"👤 Ім'я: {data['client_name']}\n"
        f"📞 Телефон: {data['client_phone']}\n"
        f"👥 2 дорослих\n\n"
        f"💰 <b>До сплати:</b> {amount} грн\n"
        f"   ({price_label})"
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
    amount = data["amount"]
    
    # Save booking to database (defaults to awaiting_payment status)
    booking = await create_booking(
        session=session,
        user_id=callback_query.from_user.id,
        shelter_num=data["shelter_num"],
        booking_date=booking_date,
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        amount=amount
    )
    
    # Create payment record
    comment = f"{booking.client_name} {date_ua_format}"
    await create_payment(
        session=session,
        booking_id=booking.id,
        amount=float(amount),
        card=settings.MONOBANK_CARD,
        comment=comment
    )
    
    await log_activity(
        session=session,
        action_type="created",
        details=f"Користувач {booking.client_name} ({booking.client_phone}) забронював Шатро №{booking.shelter_num} на {date_ua_format} (ID: {booking.id}), сума: {amount} грн, статус: очікує оплати",
        booking_id=booking.id,
        user_id=callback_query.from_user.id
    )
    
    # Delete confirmation summary card
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass
        
    cleaned_card = "".join(filter(str.isdigit, settings.MONOBANK_CARD))
    formatted_card = " ".join(cleaned_card[i:i+4] for i in range(0, len(cleaned_card), 4))
    
    payment_text = (
        "💳 <b>Для підтвердження бронювання необхідно сплатити:</b>\n\n"
        f"🛖 <b>Шатро №{booking.shelter_num}</b>\n"
        f"📅 <b>Дата:</b> {date_ua_format}\n"
        f"💰 <b>Сума до сплати:</b> {amount} грн\n\n"
        f"💳 <b>Карта Monobank:</b> <code>{formatted_card}</code>\n"
        f"👤 <b>Отримувач:</b> {settings.MONOBANK_CARD_OWNER}\n\n"
        "⚠️ <b>ВАЖЛИВО:</b> При переказі обов'язково вкажіть у коментарі:\n"
        f"📝 <code>{comment}</code>\n\n"
        f"⚠️ <b>Також потрібно буде прикріпити скріншот оплати.</b>\n"
        "Після оплати натисніть кнопку нижче 👇"
    )
    
    from bot.keyboards.payment_kb import payment_instructions_kb
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=payment_text,
        reply_markup=payment_instructions_kb(booking.id),
        parse_mode="HTML"
    )
    
    await state.clear()
