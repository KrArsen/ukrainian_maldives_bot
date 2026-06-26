# bot/handlers/admin/schedule.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from bot.database.queries import get_schedule_for_date, get_bookings_on_date
from bot.keyboards.admin.schedule_kb import get_weekly_schedule_kb, get_day_bookings_kb
from bot.handlers.admin.main_menu import is_admin

router = Router()

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
        booked_count = len(sched["occupied"])
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

# Dashboard entry
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

# Day detailed view
@router.callback_query(F.data.startswith("ab_sch_d:"))
async def callback_schedule_day_details(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    date_str = callback_query.data.split(":")[1]
    target_date = date.fromisoformat(date_str)
    
    bookings = await get_bookings_on_date(session, target_date)
    
    # Calculate back_start_date (Monday of the target week)
    back_start_date = target_date - timedelta(days=target_date.weekday())
    
    kb = get_day_bookings_kb(target_date, bookings, back_start_date)
    
    booked_nums = [b.shelter_num for b in bookings]
    free_nums = [i for i in range(1, 11) if i not in booked_nums]
    
    lines = [
        f"📅 <b>Бронювання на {target_date.strftime('%d.%m.%Y (%a)')}:</b>\n",
        f"🛖 Зайнято шатер: <b>{len(bookings)}/10</b>\n"
    ]
    
    from bot.database.models import BookingStatus
    if bookings:
        for b in bookings:
            status_icon = "⏳"
            if b.status == BookingStatus.payment_pending_review:
                status_icon = "🔍"
            elif b.status == BookingStatus.confirmed:
                status_icon = "✅"
            lines.append(f"{status_icon} <b>Шатро №{b.shelter_num}</b> — {b.client_name} ({b.client_phone})")
    else:
        lines.append("<i>Бронювань немає</i>")
        
    if free_nums:
        free_str = ", ".join(f"№{n}" for n in free_nums)
        lines.append(f"\n🟢 Вільні шатра: <b>{free_str}</b>")
    else:
        lines.append("\n🔴 Вільних шатер немає")
        
    lines.append("\nОберіть шатро для детального керування:")
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="\n".join(lines),
        reply_markup=kb
    )
