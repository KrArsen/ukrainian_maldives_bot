from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, Booking, BookingStatus
from datetime import date

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None):
    user = await session.get(User, telegram_id)
    if not user:
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
    return user

async def get_booked_shelters_on_date(session: AsyncSession, booking_date: date) -> set[int]:
    """Які шатра вже зайняті на цю дату."""
    result = await session.execute(
        select(Booking.shelter_num).where(
            Booking.booking_date == booking_date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed])
        )
    )
    return set(row[0] for row in result.fetchall())

async def get_fully_booked_dates(session: AsyncSession, year: int, month: int) -> set[date]:
    """Дати, коли всі 10 шатер зайняті — для відображення на календарі як недоступні."""
    result = await session.execute(
        select(Booking.booking_date)
        .where(
            func.strftime('%Y', Booking.booking_date) == str(year),
            func.strftime('%m', Booking.booking_date) == f"{month:02d}",
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed])
        )
        .group_by(Booking.booking_date)
        .having(func.count(Booking.shelter_num) >= 10)
    )
    return set(row[0] for row in result.fetchall())

async def is_shelter_available(session: AsyncSession, shelter_num: int, booking_date: date) -> bool:
    result = await session.execute(
        select(Booking).where(
            Booking.shelter_num == shelter_num,
            Booking.booking_date == booking_date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed])
        )
    )
    return result.scalar_one_or_none() is None

async def create_booking(session: AsyncSession, user_id: int, shelter_num: int, booking_date: date, client_name: str, client_phone: str) -> Booking:
    b = Booking(user_id=user_id, shelter_num=shelter_num, booking_date=booking_date,
                client_name=client_name, client_phone=client_phone)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b

async def get_user_bookings(session: AsyncSession, user_id: int) -> list[Booking]:
    result = await session.execute(
        select(Booking).where(Booking.user_id == user_id).order_by(Booking.booking_date.desc())
    )
    return list(result.scalars().all())

async def get_pending_bookings(session: AsyncSession) -> list[Booking]:
    result = await session.execute(
        select(Booking).where(Booking.status == BookingStatus.pending).order_by(Booking.created_at)
    )
    return list(result.scalars().all())

async def get_all_bookings(session: AsyncSession) -> list[Booking]:
    result = await session.execute(
        select(Booking).order_by(Booking.booking_date.desc()).limit(50)
    )
    return list(result.scalars().all())

async def get_bookings_on_date(session: AsyncSession, target_date: date) -> list[Booking]:
    result = await session.execute(
        select(Booking).where(
            Booking.booking_date == target_date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed])
        ).order_by(Booking.shelter_num)
    )
    return list(result.scalars().all())

async def confirm_booking(session: AsyncSession, booking_id: int) -> Booking|None:
    b = await session.get(Booking, booking_id)
    if b:
        b.status = BookingStatus.confirmed
        await session.commit()
    return b

async def cancel_booking(session: AsyncSession, booking_id: int, admin_comment: str = "") -> Booking|None:
    b = await session.get(Booking, booking_id)
    if b:
        b.status = BookingStatus.cancelled
        b.admin_comment = admin_comment
        await session.commit()
    return b

async def log_activity(session: AsyncSession, action_type: str, details: str, booking_id: int | None = None, user_id: int | None = None):
    """Logs an activity event in the database."""
    from bot.database.models import ActivityLog
    log = ActivityLog(action_type=action_type, details=details, booking_id=booking_id, user_id=user_id)
    session.add(log)
    await session.commit()

async def get_recent_activity(session: AsyncSession, limit: int = 20) -> list:
    """Retrieves the most recent activity log entries."""
    from bot.database.models import ActivityLog
    result = await session.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
