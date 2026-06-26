# bot/handlers/admin/schedule.py
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from bot.database.queries import (
    get_schedule_for_date,
    get_bookings_on_date,
    get_prices,
    get_blocks_for_date,
    block_tent,
    unblock_tent,
    log_activity
)
from bot.keyboards.admin.schedule_kb import get_weekly_schedule_kb, schedule_day_kb
from bot.states.admin_states import AdminBlockStates
from bot.handlers.admin.main_menu import is_admin

router = Router()

def skip_reason_kb() -> InlineKeyboardMarkup:
    """Button to skip block reason."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Без причини", callback_data="block_no_reason")]
    ])

async def show_weekly_schedule_internal(
    callback_query: CallbackQuery,
    start_date: date,
    session: AsyncSession,
    bot: Bot
):
    day_stats = []
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        sched = await get_schedule_for_date(session, day_date)
        # Sched returns occupied_bookings list and free list
        booked_count = len(sched["occupied_bookings"])
        day_stats.append((day_date, booked_count))
        
    kb = get_weekly_schedule_kb(start_date, day_stats)
    
    text = (
        f"📅 <b>Графік бронювань (Тиждень з {start_date.strftime('%d.%m.%Y')})</b>\n\n"
        f"🟢 — Вільні місця є\n"
        f"🟡 — Частково зайнято\n"
        f"🔴 — Всі 10 шатер заброньовано\n\n"
        f"Оберіть день для перегляду розподілу:"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb
    )

# Dashboard entry - Weekly list
@router.callback_query(F.data == "admin_sched")
async def callback_schedule_dashboard(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_weekly_schedule_internal(callback_query, date.today(), session, bot)

# Weekly pagination
@router.callback_query(F.data.startswith("ab_sch:"))
async def callback_schedule_pagination(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    date_str = callback_query.data.split(":")[1]
    start_date = date.fromisoformat(date_str)
    await show_weekly_schedule_internal(callback_query, start_date, session, bot)

# --- DAILY SCHEDULER VIEW (Part 2) ---
async def show_schedule_for_date(callback_query: CallbackQuery, session: AsyncSession, target_date: date, bot: Bot):
    from bot.services.pricing import get_price_for_date, is_weekend
    
    weekday_price, weekend_price = await get_prices(session)
    price = get_price_for_date(target_date, weekday_price, weekend_price)
    price_type = "вихідний день 🌟" if is_weekend(target_date) else "будній день"
    
    # Bookings on date
    bookings_data = await get_schedule_for_date(session, target_date)
    bookings = bookings_data["occupied_bookings"]
    
    # Blocks on date
    blocks = await get_blocks_for_date(session, target_date)
    blocked_nums = {b.tent_number: b for b in blocks}
    
    booked_nums = {b.shelter_num: b for b in bookings}
    all_occupied = set(booked_nums.keys()) | set(blocked_nums.keys())
    free_nums = [n for n in range(1, 11) if n not in all_occupied]
    
    text = (
        f"📅 <b>Розклад на {target_date.strftime('%d.%m.%Y (%A)')}</b>\n"
        f"💰 Ціна: <b>{price} грн</b> ({price_type})\n\n"
    )
    
    if not all_occupied:
        text += "🟢 Всі шатра вільні!\n"
    else:
        occupied_list = []
        for n in sorted(all_occupied):
            if n in blocked_nums:
                occupied_list.append(f"№{n} 🔒")
              # Note: shelter_num is booked
            else:
                occupied_list.append(f"№{n}")
        text += f"🔴 Зайняті: {', '.join(occupied_list)}\n"
        
    if free_nums:
        text += f"🟢 Вільні: {', '.join(f'№{n}' for n in free_nums)}\n"
        
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    
    status_map = {
        "confirmed": "✅ підтверджено",
        "awaiting_payment": "⏳ очікує оплати",
        "payment_pending_review": "💳 оплата на перевірці",
        "cancelled": "❌ скасовано"
    }
    
    for n in sorted(all_occupied):
        if n in blocked_nums:
            b = blocked_nums[n]
            reason_str = f"\n   📝 {b.reason}" if b.reason else ""
            text += f"🏕 №{n} — 🔒 <b>ЗАБЛОКОВАНО</b> адміном{reason_str}\n"
        elif n in booked_nums:
            bk = booked_nums[n]
            # bk.full_name is mapped to client_name
            text += f"🏕 №{n} — {bk.full_name} | {status_map.get(bk.status.value if hasattr(bk.status, 'value') else bk.status, bk.status)}\n"
            
    kb = schedule_day_kb(target_date, bookings, blocked_nums, free_nums)
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML"
    )

# Dashboard entry - Daily list
@router.callback_query(F.data == "admin_schedule")
async def callback_schedule_today(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_schedule_for_date(callback_query, session, date.today(), bot)

# Daily detailed view (triggered by date pagination/selection)
@router.callback_query(F.data.startswith("ab_sch_d:"))
async def callback_schedule_day_details(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    date_str = callback_query.data.split(":")[1]
    target_date = date.fromisoformat(date_str)
    await show_schedule_for_date(callback_query, session, target_date, bot)

# --- MANUAL TENT BLOCKING ACTION ---
@router.callback_query(F.data.startswith("admin_block_tent:"))
async def block_tent_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(callback.from_user.id, session):
        await callback.answer()
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    tent_number = int(parts[1])
    date_str = parts[2]
    block_date = date.fromisoformat(date_str)
    
    await state.update_data(
        block_tent_number=tent_number,
        block_date=date_str
    )
    await state.set_state(AdminBlockStates.waiting_reason)
    
    await callback.message.answer(
        f"🔒 <b>Блокування Шатра №{tent_number} на {block_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Вкажіть причину (наприклад: <i>Технічне обслуговування</i>).\n"
        f"Або натисніть кнопкою нижче, щоб залишити без причини:",
        reply_markup=skip_reason_kb()
    )

# Receive block reason text
@router.message(AdminBlockStates.waiting_reason)
async def save_block_with_reason(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
        
    data = await state.get_data()
    await _execute_block(
        message, state, session, bot,
        data["block_tent_number"], data["block_date"],
        reason=message.text.strip() if message.text else None
    )

# Skip block reason callback
@router.callback_query(F.data == "block_no_reason", StateFilter(AdminBlockStates.waiting_reason))
async def save_block_no_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback.from_user.id, session):
        await callback.answer()
        return
    await callback.answer()
    
    data = await state.get_data()
    await _execute_block(
        callback.message, state, session, bot,
        data["block_tent_number"], data["block_date"],
        reason=None
    )

async def _execute_block(message_or_obj, state, session, bot, tent_number, date_str, reason):
    block_date = date.fromisoformat(date_str)
    admin_id = message_or_obj.chat.id # chat ID is always the admin user ID in private chat
    
    success = await block_tent(session, tent_number, block_date, admin_id, reason)
    await state.clear()
    
    if success:
        reason_text = f"\nПричина: <i>{reason}</i>" if reason else ""
        await message_or_obj.answer(
            f"🔒 Шатро №{tent_number} заблоковано на {block_date.strftime('%d.%m.%Y')}"
            f"{reason_text}\n\n"
            f"Клієнти не зможуть забронювати це шатро на цю дату."
        )
        await log_activity(
            session, "tent_blocked",
            f"Адмін заблокував Шатро №{tent_number} на {block_date.strftime('%d.%m.%Y')}. Причина: {reason or 'немає'}",
            user_id=admin_id
        )
    else:
        await message_or_obj.answer(
            f"⚠️ Не вдалось заблокувати Шатро №{tent_number}.\n"
            f"Можлива причина: на цю дату вже є активне або підтверджене бронювання.\n"
            f"Скасуйте бронювання, перш ніж блокувати шатро."
        )
        
    # Send daily schedule again
    # We send a new message since the admin typed text / interacted
    msg = await message_or_obj.answer("Завантаження розкладу...")
    fake_cb = CallbackQuery(
        id="0",
        from_user=message_or_obj.from_user if hasattr(message_or_obj, 'from_user') else None,
        chat_instance="0",
        message=msg,
        data=f"ab_sch_d:{date_str}"
    )
    await show_schedule_for_date(fake_cb, session, block_date, bot)

# --- UNBLOCKING ---
@router.callback_query(F.data.startswith("admin_unblock_tent:"))
async def callback_unblock_tent(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    parts = callback_query.data.split(":")
    tent_number = int(parts[1])
    date_str = parts[2]
    block_date = date.fromisoformat(date_str)
    
    success = await unblock_tent(session, tent_number, block_date)
    
    if success:
        await callback_query.answer(
            f"🔓 Шатро №{tent_number} розблоковано на {block_date.strftime('%d.%m.%Y')}",
            show_alert=True
        )
        await log_activity(
            session, "tent_unblocked",
            f"Адмін розблокував Шатро №{tent_number} на {block_date.strftime('%d.%m.%Y')}",
            user_id=callback_query.from_user.id
        )
    else:
        await callback_query.answer("⚠️ Блокування не знайдено.", show_alert=True)
        
    # Refresh daily schedule
    await show_schedule_for_date(callback_query, session, block_date, bot)
