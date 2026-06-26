# bot/handlers/admin/settings.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import csv
import io
import asyncio
from datetime import date

from bot.config import settings as bot_settings
from bot.database.models import User, BookingStatus, Booking
from bot.database.queries import (
    get_setting,
    set_setting,
    get_bookings_for_export,
    log_activity,
    get_prices
)
from bot.keyboards.admin.settings_kb import (
    get_settings_kb,
    get_export_menu_kb,
    get_export_custom_months_kb
)
from bot.states.admin_states import AdminSettings, AdminBroadcast
from bot.handlers.admin.main_menu import is_admin

router = Router()

async def show_settings_dashboard(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    weekday_price, weekend_price = await get_prices(session)
    timeout_str = await get_setting(session, "payment_timeout_hours")
    timeout_val = f"<b>{timeout_str} год</b>" if timeout_str else f"{bot_settings.PAYMENT_TIMEOUT_HOURS} год (за замовчуванням)"
    
    text = (
        f"⚙️ <b>Налаштування системи</b>\n\n"
        f"💰 Будні ціна: <b>{weekday_price} грн</b>\n"
        f"🌟 Вихідні ціна: <b>{weekend_price} грн</b>\n"
        f"⏱️ Таймаут оплати: {timeout_val}\n\n"
        f"Оберіть дію:"
    )
    
    kb = get_settings_kb(weekday_price, weekend_price)
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb
    )

@router.callback_query(F.data == "admin_settings")
async def callback_settings(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_settings_dashboard(callback_query, session, bot)

# --- Weekday Price Configuration ---
@router.callback_query(F.data == "admin_set_weekday_price")
async def set_weekday_price(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(callback.from_user.id, session):
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(AdminSettings.waiting_weekday_price)
    await callback.message.answer("💰 Введіть нову ціну для буднів (грн):")

@router.message(AdminSettings.waiting_weekday_price)
async def save_weekday_price(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
    if not message.text.isdigit() or int(message.text) < 100:
        await message.answer("⚠️ Введіть коректну суму (число від 100):")
        return
    await set_setting(session, 'price_weekday', message.text)
    await log_activity(session, "setting_change", f"Адмін змінив будню ціну: {message.text} грн", user_id=message.from_user.id)
    await message.answer(f"✅ Ціна для буднів оновлена: <b>{message.text} грн</b>.")
    await state.clear()
    
    # Reload dashboard
    msg = await message.answer("Завантаження...")
    fake_cb = CallbackQuery(
        id="0", from_user=message.from_user, chat_instance="0", message=msg, data="admin_settings"
    )
    await show_settings_dashboard(fake_cb, session, bot)

# --- Weekend Price Configuration ---
@router.callback_query(F.data == "admin_set_weekend_price")
async def set_weekend_price(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(callback.from_user.id, session):
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(AdminSettings.waiting_weekend_price)
    await callback.message.answer("🌟 Введіть нову ціну для вихідних (грн):")

@router.message(AdminSettings.waiting_weekend_price)
async def save_weekend_price(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
    if not message.text.isdigit() or int(message.text) < 100:
        await message.answer("⚠️ Введіть коректну суму (число від 100):")
        return
    await set_setting(session, 'price_weekend', message.text)
    await log_activity(session, "setting_change", f"Адмін змінив вихідну ціну: {message.text} грн", user_id=message.from_user.id)
    await message.answer(f"✅ Ціна для вихідних оновлена: <b>{message.text} грн</b>.")
    await state.clear()
    
    # Reload dashboard
    msg = await message.answer("Завантаження...")
    fake_cb = CallbackQuery(
        id="0", from_user=message.from_user, chat_instance="0", message=msg, data="admin_settings"
    )
    await show_settings_dashboard(fake_cb, session, bot)

# --- Timeout Tuning ---
@router.callback_query(F.data == "as_timeout")
async def callback_timeout_change_request(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    await state.set_state(AdminSettings.waiting_timeout_input)
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=(
            "⏱️ <b>Зміна таймауту оплати</b>\n\n"
            "Введіть час очікування оплати в годинах (ціле число від 1 до 168, наприклад: <code>24</code>)."
        )
    )

@router.message(AdminSettings.waiting_timeout_input)
async def process_timeout_input(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
        
    text = message.text.strip()
    if text.isdigit():
        hours = int(text)
        if hours < 1 or hours > 168:
            await message.answer("❌ Введіть число годин в межах від 1 до 168 (1 тиждень):")
            return
        await set_setting(session, "payment_timeout_hours", text)
        await log_activity(session, "setting_change", f"Адмін встановив таймаут оплати: {hours} год", user_id=message.from_user.id)
        await message.answer(f"✅ Встановлено таймаут оплати: <b>{hours} год</b>.")
        await state.clear()
    else:
        await message.answer("❌ Будь ласка, введіть ціле число годин:")
        return
        
    # Send dashboard again
    msg = await message.answer("Завантаження...")
    fake_cb = CallbackQuery(
        id="0", from_user=message.from_user, chat_instance="0", message=msg, data="admin_settings"
    )
    await show_settings_dashboard(fake_cb, session, bot)

# --- CSV Report Export ---
@router.callback_query(F.data == "as_export_menu")
async def callback_export_menu(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="📊 <b>Експорт замовлень в Excel (CSV)</b>\n\nОберіть період звіту:",
        reply_markup=get_export_menu_kb()
    )

@router.callback_query(F.data == "ase_custom")
async def callback_export_custom_year(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    current_year = date.today().year
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"📅 <b>Виберіть місяць для експорту ({current_year}):</b>",
        reply_markup=get_export_custom_months_kb(current_year)
    )

@router.callback_query(F.data.startswith("ase_yr:"))
async def callback_export_year_switch(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    year = int(callback_query.data.split(":")[1])
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"📅 <b>Виберіть місяць для експорту ({year}):</b>",
        reply_markup=get_export_custom_months_kb(year)
    )

@router.callback_query(F.data.startswith("ase_quick:"))
async def callback_export_run(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    year = int(parts[1])
    month = int(parts[2])
    
    bookings = await get_bookings_for_export(session, year, month)
    
    if not bookings:
        await callback_query.answer("Не знайдено замовлень за вказаний період.", show_alert=True)
        return
        
    output = io.StringIO()
    # UTF-8 BOM to prevent Excel display errors on Ukrainian characters
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow([
        "ID замовлення", "Дата бронювання", "Номер шатра", "Ім'я клієнта",
        "Телефон", "Статус", "Дата подачі", "Коментар адміністратора"
    ])
    
    for b in bookings:
        status_lbl = "Очікує оплати"
        if b.status == BookingStatus.confirmed: status_lbl = "Підтверджено"
        elif b.status == BookingStatus.cancelled: status_lbl = "Скасовано"
        elif b.status == BookingStatus.payment_pending_review: status_lbl = "На перевірці"
        
        writer.writerow([
            b.id,
            b.booking_date.strftime("%d.%m.%Y"),
            f"Шатро №{b.shelter_num}",
            b.client_name,
            b.client_phone,
            status_lbl,
            b.created_at.strftime("%d.%m.%Y %H:%M"),
            b.admin_comment or ""
        ])
        
    bytes_data = output.getvalue().encode('utf-8')
    file_input = BufferedInputFile(bytes_data, filename=f"maldivi_bookings_{month:02d}_{year}.csv")
    
    await bot.send_document(
        chat_id=callback_query.message.chat.id,
        document=file_input,
        caption=f"📊 <b>Звіт про бронювання за {month:02d}.{year}</b>\n\nВсього записів: {len(bookings)}"
    )

# --- Global Broadcast Message ---
@router.callback_query(F.data == "as_broadcast")
async def callback_broadcast_request(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    await state.set_state(AdminBroadcast.waiting_broadcast_text)
    
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=(
            "✉️ <b>Масова розсилка клієнтам</b>\n\n"
            "Введіть текст повідомлення. Ви можете прикріпити фото/відео/документ до цього повідомлення - бот надішле копію кожному користувачу."
        )
    )

@router.message(AdminBroadcast.waiting_broadcast_text)
async def process_broadcast_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
        
    await state.clear()
    
    # Select all active (non-banned) users
    res = await session.execute(select(User.telegram_id).where(User.is_banned == False))
    users = res.scalars().all()
    
    if not users:
        await message.answer("❌ У базі даних немає зареєстрованих користувачів.")
        return
        
    status_msg = await message.answer(f"⏳ Розпочинаю розсилку для <b>{len(users)}</b> користувачів...")
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            # Use copy_message to perfectly preserve formatting, photos, markup, etc.
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except Exception:
            failed += 1
            
        # Flood control delay (0.05 seconds per message)
        await asyncio.sleep(0.05)
        
    # Log
    await log_activity(
        session, "broadcast",
        f"Адмін зробив розсилку для {len(users)} користувачів (Успішно: {success}, Помилок: {failed})",
        user_id=message.from_user.id
    )
    
    await status_msg.edit_text(
        text=(
            f"✉️ <b>Масова розсилка завершена!</b>\n\n"
            f"• Успішно надіслано: <b>{success}</b>\n"
            f"• Помилок доставки: <b>{failed}</b>"
        )
    )
