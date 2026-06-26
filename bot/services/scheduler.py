# bot/services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, timedelta
from aiogram import Bot
from bot.database.engine import async_session
from bot.database.queries import get_bookings_on_date, log_activity
from bot.config import settings

def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot):

    @scheduler.scheduled_job("cron", hour=9, minute=0, timezone="Europe/Kyiv")
    async def daily_admin_report():
        today = date.today()
        async with async_session() as session:
            bookings = await get_bookings_on_date(session, today)
            # Get all admin IDs from both config (.env) and database
            from bot.database.models import User
            from sqlalchemy import select
            db_admins_res = await session.execute(select(User.telegram_id).where(User.is_admin == True))
            all_admin_ids = set(settings.ADMIN_IDS) | {row[0] for row in db_admins_res.fetchall()}
            
        if not bookings:
            text = f"📅 На сьогодні ({today.strftime('%d.%m.%Y')}) бронювань немає."
        else:
            booked = [str(b.shelter_num) for b in bookings]
            free   = [str(i) for i in range(1, 11) if str(i) not in booked]
            lines  = [f"📅 <b>Бронювання на {today.strftime('%d.%m.%Y')}:</b>\n"]
            for b in bookings:
                icon = "✅" if b.status.value == "confirmed" else "⏳"
                lines.append(f"{icon} Шатро №{b.shelter_num} — {b.client_name} — {b.client_phone}")
            if free:
                lines.append(f"\nВільні: №{', №'.join(free)}")
            text = "\n".join(lines)
            
        for admin_id in all_admin_ids:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception:
                pass


    @scheduler.scheduled_job("cron", hour=18, minute=0, timezone="Europe/Kyiv")
    async def remind_tomorrow():
        tomorrow = date.today() + timedelta(days=1)
        async with async_session() as session:
            bookings = await get_bookings_on_date(session, tomorrow)
            for b in bookings:
                if b.status.value == "confirmed":
                    try:
                        await bot.send_message(
                            b.user_id,
                            f"⏰ <b>Нагадування!</b>\n\n"
                            f"Завтра ваш заїзд до «Українських Мальдівів»!\n\n"
                            f"🛖 Шатро №{b.shelter_num}\n"
                            f"📅 {tomorrow.strftime('%d.%m.%Y')}\n\n"
                            f"Час заїзду: з 14:00\n"
                            f"📍 {settings.RESORT_ADDRESS}\n\n"
                            f"Чекаємо вас! 🌊",
                            parse_mode="HTML"
                        )
                        # Log activity
                        await log_activity(
                            session=session,
                            action_type="reminder_sent",
                            details=f"Надіслано нагадування про заїзд {b.client_name} (Шатро №{b.shelter_num}, {tomorrow.strftime('%d.%m.%Y')}, ID: {b.id})",
                            booking_id=b.id,
                            user_id=b.user_id
                        )
                    except Exception:
                        pass
