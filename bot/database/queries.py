from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, Booking, BookingStatus, TentBlock
from datetime import date

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None):
    user = await session.get(User, telegram_id)
    if not user:
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
    return user

async def get_booked_shelters_on_date(session: AsyncSession, booking_date: date) -> set[int]:
    """Які шатра вже зайняті або заблоковані на цю дату."""
    result = await session.execute(
        select(Booking.shelter_num).where(
            Booking.booking_date == booking_date,
            Booking.status.in_([BookingStatus.awaiting_payment, BookingStatus.payment_pending_review, BookingStatus.confirmed])
        )
    )
    booked = set(row[0] for row in result.fetchall())
    blocked = await get_blocked_tent_numbers_for_date(session, booking_date)
    return booked | blocked

async def get_fully_booked_dates(session: AsyncSession, year: int, month: int) -> set[date]:
    """Дати, коли всі 10 шатер зайняті або заблоковані — для відображення на календарі як недоступні."""
    from collections import defaultdict
    import calendar
    from_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    to_date = date(year, month, last_day)
    
    tent_count_per_date = defaultdict(set)
    
    # 1. Bookings in month
    bookings_res = await session.execute(
        select(Booking.booking_date, Booking.shelter_num).where(
            Booking.booking_date >= from_date,
            Booking.booking_date <= to_date,
            Booking.status.in_([BookingStatus.awaiting_payment, BookingStatus.payment_pending_review, BookingStatus.confirmed])
        )
    )
    for b_date, s_num in bookings_res.fetchall():
        tent_count_per_date[b_date].add(s_num)
        
    # 2. Blocks in month
    blocks = await get_blocks_for_month(session, year, month)
    for bl in blocks:
        tent_count_per_date[bl.block_date].add(bl.tent_number)
        
    return {d for d, tents in tent_count_per_date.items() if len(tents) >= 10}

async def is_shelter_available(session: AsyncSession, shelter_num: int, booking_date: date) -> bool:
    result = await session.execute(
        select(Booking).where(
            Booking.shelter_num == shelter_num,
            Booking.booking_date == booking_date,
            Booking.status.in_([BookingStatus.awaiting_payment, BookingStatus.payment_pending_review, BookingStatus.confirmed])
        )
    )
    return result.scalar_one_or_none() is None

async def create_booking(session: AsyncSession, user_id: int, shelter_num: int, booking_date: date, client_name: str, client_phone: str, amount: int = 1700) -> Booking:
    from datetime import datetime, timedelta
    from bot.config import settings
    timeout_str = await get_setting(session, "payment_timeout_hours", str(settings.PAYMENT_TIMEOUT_HOURS))
    timeout_hours = int(timeout_str) if timeout_str.isdigit() else settings.PAYMENT_TIMEOUT_HOURS
    deadline = datetime.utcnow() + timedelta(hours=timeout_hours)
    b = Booking(
        user_id=user_id,
        shelter_num=shelter_num,
        booking_date=booking_date,
        client_name=client_name,
        client_phone=client_phone,
        status=BookingStatus.awaiting_payment,
        amount=amount,
        payment_deadline=deadline
    )
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
        select(Booking).where(Booking.status == BookingStatus.payment_pending_review).order_by(Booking.created_at)
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
            Booking.status.in_([BookingStatus.awaiting_payment, BookingStatus.payment_pending_review, BookingStatus.confirmed])
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

async def create_payment(session: AsyncSession, booking_id: int, amount: float, card: str, comment: str):
    from bot.database.models import Payment
    payment = Payment(
        booking_id=booking_id,
        amount=amount,
        monobank_card=card,
        payment_comment=comment,
        status="pending"
    )
    session.add(payment)
    await session.commit()
    return payment

async def save_payment_screenshot(session: AsyncSession, booking_id: int, file_id: str):
    from bot.database.models import Payment
    result = await session.execute(
        select(Payment).where(Payment.booking_id == booking_id)
                       .order_by(Payment.created_at.desc())
    )
    payment = result.scalars().first()
    if payment:
        payment.screenshot_file_id = file_id
        payment.status = "screenshot_sent"
    await session.commit()

async def confirm_payment(session: AsyncSession, booking_id: int, confirmed_by: int):
    from bot.database.models import Payment
    from datetime import datetime
    result = await session.execute(
        select(Payment).where(Payment.booking_id == booking_id)
                       .order_by(Payment.created_at.desc())
    )
    payment = result.scalars().first()
    if payment:
        payment.status = "confirmed"
        payment.confirmed_at = datetime.utcnow()
        payment.confirmed_by = confirmed_by
    await session.commit()

async def reject_payment(session: AsyncSession, booking_id: int, reason: str):
    from bot.database.models import Payment
    result = await session.execute(
        select(Payment).where(Payment.booking_id == booking_id)
                       .order_by(Payment.created_at.desc())
    )
    payment = result.scalars().first()
    if payment:
        payment.status = "rejected"
        payment.rejection_reason = reason
    await session.commit()

async def get_expired_payment_bookings(session: AsyncSession) -> list[Booking]:
    from datetime import datetime
    result = await session.execute(
        select(Booking).where(
            Booking.status == BookingStatus.awaiting_payment,
            Booking.payment_deadline <= datetime.utcnow()
        )
    )
    return list(result.scalars().all())

async def get_admin_stats(session: AsyncSession) -> dict:
    from bot.database.models import Payment
    
    # 1. Total users
    total_users_res = await session.execute(select(func.count(User.telegram_id)))
    total_users = total_users_res.scalar() or 0
    
    # 2. Total bookings count
    total_bookings_res = await session.execute(select(func.count(Booking.id)))
    total_bookings = total_bookings_res.scalar() or 0
    
    # 3. Bookings by status
    status_counts = {
        BookingStatus.awaiting_payment: 0,
        BookingStatus.payment_pending_review: 0,
        BookingStatus.confirmed: 0,
        BookingStatus.cancelled: 0,
    }
    
    status_res = await session.execute(
        select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
    )
    for status, count in status_res.all():
        if status in status_counts:
            status_counts[status] = count
            
    # 4. Total revenue (sum of confirmed payments)
    revenue_res = await session.execute(
        select(func.sum(Payment.amount)).where(Payment.status == "confirmed")
    )
    total_revenue = revenue_res.scalar() or 0
    
    return {
        "total_users": total_users,
        "total_bookings": total_bookings,
        "awaiting_payment": status_counts[BookingStatus.awaiting_payment],
        "payment_pending_review": status_counts[BookingStatus.payment_pending_review],
        "confirmed": status_counts[BookingStatus.confirmed],
        "cancelled": status_counts[BookingStatus.cancelled],
        "total_revenue": float(total_revenue)
    }

async def search_bookings(session: AsyncSession, query: str) -> list[Booking]:
    from sqlalchemy import or_
    query_clean = query.strip()
    if not query_clean:
        return []
        
    conditions = []
    
    # Search by Booking ID
    if query_clean.isdigit():
        conditions.append(Booking.id == int(query_clean))
    elif query_clean.startswith("#") and query_clean[1:].isdigit():
        conditions.append(Booking.id == int(query_clean[1:]))
        
    # Search by shelter number (if single digit 1-10)
    if query_clean.isdigit() and 1 <= int(query_clean) <= 10:
        conditions.append(Booking.shelter_num == int(query_clean))
        
    # Search by client name (case-insensitive)
    conditions.append(Booking.client_name.ilike(f"%{query_clean}%"))
    
    # Search by phone number (comparing digit substrings)
    phone_digits = "".join(filter(str.isdigit, query_clean))
    if phone_digits:
        conditions.append(Booking.client_phone.like(f"%{phone_digits}%"))
        
    result = await session.execute(
        select(Booking).where(or_(*conditions)).order_by(Booking.booking_date.desc()).limit(50)
    )
    return list(result.scalars().all())

async def get_bookings_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Booking.id)))
    return result.scalar() or 0

async def get_all_bookings_paginated(session: AsyncSession, offset: int, limit: int) -> list[Booking]:
    result = await session.execute(
        select(Booking).order_by(Booking.booking_date.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())

async def get_setting(session: AsyncSession, key: str, default: str = None) -> str:
    from bot.database.models import Setting
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default

async def set_setting(session: AsyncSession, key: str, value: str):
    from bot.database.models import Setting
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        row = Setting(key=key, value=value)
        session.add(row)
    await session.commit()

async def get_booking_price(session: AsyncSession, booking_date: date) -> int:
    price_str = await get_setting(session, "booking_price")
    if price_str and price_str.isdigit():
        return int(price_str)
    is_weekend = booking_date.weekday() in (5, 6)
    from bot.config import settings
    return settings.WEEKEND_PRICE if is_weekend else settings.WEEKDAY_PRICE

async def count_bookings_by_status(session: AsyncSession, status: str) -> int:
    from bot.database.models import Booking, BookingStatus
    from sqlalchemy import select, func
    
    status_enum = None
    if status == "awaiting_payment":
        status_enum = BookingStatus.awaiting_payment
    elif status == "payment_pending_review":
        status_enum = BookingStatus.payment_pending_review
    elif status == "confirmed":
        status_enum = BookingStatus.confirmed
    elif status == "cancelled":
        status_enum = BookingStatus.cancelled
        
    if not status_enum:
        return 0
        
    result = await session.execute(
        select(func.count(Booking.id)).where(Booking.status == status_enum)
    )
    return result.scalar() or 0

async def get_statistics(session: AsyncSession, period: str) -> dict:
    from datetime import datetime, time, timedelta
    from bot.database.models import Booking, BookingStatus, Payment, User
    from sqlalchemy import select, func, and_
    
    now = datetime.utcnow()
    today_start = datetime.combine(date.today(), time.min)
    
    if period == "today":
        start_date = today_start
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime.min
        
    booking_filter = Booking.created_at >= start_date if start_date != datetime.min else True
    
    total = (await session.execute(select(func.count(Booking.id)).where(booking_filter))).scalar() or 0
    confirmed = (await session.execute(select(func.count(Booking.id)).where(and_(booking_filter, Booking.status == BookingStatus.confirmed)))).scalar() or 0
    cancelled = (await session.execute(select(func.count(Booking.id)).where(and_(booking_filter, Booking.status == BookingStatus.cancelled)))).scalar() or 0
    pending = (await session.execute(select(func.count(Booking.id)).where(and_(booking_filter, Booking.status == BookingStatus.payment_pending_review)))).scalar() or 0
    
    revenue = (await session.execute(
        select(func.sum(Payment.amount))
        .join(Booking)
        .where(and_(booking_filter, Payment.status == "confirmed"))
    )).scalar() or 0
    
    payments_rejected = (await session.execute(
        select(func.count(Payment.id))
        .join(Booking)
        .where(and_(booking_filter, Payment.status == "rejected"))
    )).scalar() or 0
    
    unique_clients = (await session.execute(
        select(func.count(func.distinct(Booking.user_id)))
        .where(and_(booking_filter, Booking.status == BookingStatus.confirmed))
    )).scalar() or 0
    
    subq = (
        select(Booking.user_id)
        .where(Booking.status == BookingStatus.confirmed)
        .group_by(Booking.user_id)
        .having(func.count(Booking.id) >= 2)
        .subquery()
    )
    repeat_clients = (await session.execute(select(func.count(subq.c.user_id)))).scalar() or 0
    
    if period == "today":
        days = 1
    elif period == "week":
        days = 7
    elif period == "month":
        days = 30
    else:
        min_date_res = await session.execute(select(func.min(Booking.booking_date)))
        max_date_res = await session.execute(select(func.max(Booking.booking_date)))
        min_date = min_date_res.scalar()
        max_date = max_date_res.scalar()
        if min_date and max_date:
            days = max(1, (max_date - min_date).days + 1)
        else:
            days = 1
            
    total_slots = days * 10
    
    if period == "today":
        date_filter = Booking.booking_date == date.today()
    elif period == "week":
        date_filter = Booking.booking_date >= date.today() - timedelta(days=6)
    elif period == "month":
        date_filter = Booking.booking_date >= date.today() - timedelta(days=29)
    else:
        date_filter = True
        
    occupied_slots = (await session.execute(
        select(func.count(Booking.id)).where(and_(date_filter, Booking.status == BookingStatus.confirmed))
    )).scalar() or 0
    
    occupancy_rate = int((occupied_slots / total_slots) * 100) if total_slots > 0 else 0
    if occupancy_rate > 100:
        occupancy_rate = 100
        
    top_dates_res = await session.execute(
        select(Booking.booking_date, func.count(Booking.id))
        .where(and_(date_filter, Booking.status == BookingStatus.confirmed))
        .group_by(Booking.booking_date)
        .order_by(func.count(Booking.id).desc())
        .limit(3)
    )
    top_dates = [(row[0].strftime("%d.%m"), row[1]) for row in top_dates_res.all()]
    
    tent_ranking_res = await session.execute(
        select(Booking.shelter_num, func.count(Booking.id))
        .where(and_(date_filter, Booking.status == BookingStatus.confirmed))
        .group_by(Booking.shelter_num)
        .order_by(func.count(Booking.id).desc())
        .limit(3)
    )
    tent_ranking = [(row[0], row[1]) for row in tent_ranking_res.all()]
    
    return {
        "total": total,
        "confirmed": confirmed,
        "cancelled": cancelled,
        "pending": pending,
        "revenue": float(revenue),
        "payments_rejected": payments_rejected,
        "unique_clients": unique_clients,
        "repeat_clients": repeat_clients,
        "occupancy_rate": occupancy_rate,
        "top_dates": top_dates,
        "tent_ranking": tent_ranking
    }

async def get_bookings_filtered(
    session: AsyncSession,
    status: str = 'all',
    tent_number: int = None,
    sort_by: str = 'created_desc',
    limit: int = 10,
    offset: int = 0
) -> tuple[list[Booking], int]:
    from bot.database.models import Booking, BookingStatus
    from sqlalchemy import select, func, and_
    
    stmt = select(Booking)
    count_stmt = select(func.count(Booking.id))
    
    conditions = []
    if status != 'all':
        if status == 'pending':
            conditions.append(Booking.status == BookingStatus.payment_pending_review)
        elif status == 'confirmed':
            conditions.append(Booking.status == BookingStatus.confirmed)
        elif status == 'cancelled':
            conditions.append(Booking.status == BookingStatus.cancelled)
        elif status == 'awaiting_payment':
            conditions.append(Booking.status == BookingStatus.awaiting_payment)
            
    if tent_number is not None and 1 <= tent_number <= 10:
        conditions.append(Booking.shelter_num == tent_number)
        
    if conditions:
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))
        
    if sort_by == 'created_desc':
        stmt = stmt.order_by(Booking.created_at.desc())
    elif sort_by == 'created_asc':
        stmt = stmt.order_by(Booking.created_at.asc())
    elif sort_by == 'checkin':
        stmt = stmt.order_by(Booking.booking_date.asc())
        
    stmt = stmt.offset(offset).limit(limit)
    
    bookings_res = await session.execute(stmt)
    bookings = list(bookings_res.scalars().all())
    
    total = (await session.execute(count_stmt)).scalar() or 0
    
    return bookings, total

async def get_booking_full(session: AsyncSession, booking_id: int) -> Booking | None:
    from bot.database.models import Booking
    return await session.get(Booking, booking_id)

async def get_latest_payment(session: AsyncSession, booking_id: int):
    from bot.database.models import Payment
    from sqlalchemy import select
    res = await session.execute(
        select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
    )
    return res.scalars().first()

async def get_all_clients(session: AsyncSession) -> list:
    from bot.database.models import User, Booking
    from sqlalchemy import select, func
    
    stmt = (
        select(User, func.count(Booking.id))
        .join(Booking, Booking.user_id == User.telegram_id, isouter=True)
        .group_by(User.telegram_id)
        .order_by(func.count(Booking.id).desc())
    )
    res = await session.execute(stmt)
    return [(row[0], row[1]) for row in res.all()]

async def get_client_profile(session: AsyncSession, user_id: int) -> dict | None:
    from bot.database.models import User, Booking, BookingStatus, Payment
    from sqlalchemy import select, func, and_
    
    user = await session.get(User, user_id)
    if not user:
        return None
        
    bookings_res = await session.execute(
        select(Booking).where(Booking.user_id == user_id).order_by(Booking.booking_date.desc())
    )
    bookings = list(bookings_res.scalars().all())
    
    total_bookings = len(bookings)
    confirmed_count = sum(1 for b in bookings if b.status == BookingStatus.confirmed)
    cancelled_count = sum(1 for b in bookings if b.status == BookingStatus.cancelled)
    
    revenue_res = await session.execute(
        select(func.sum(Payment.amount))
        .join(Booking)
        .where(and_(Booking.user_id == user_id, Payment.status == "confirmed"))
    )
    total_spent = revenue_res.scalar() or 0
    
    first_booking = bookings[-1].booking_date if bookings else None
    last_booking = bookings[0].booking_date if bookings else None
    
    return {
        "user": user,
        "bookings": bookings,
        "total_bookings": total_bookings,
        "confirmed_count": confirmed_count,
        "cancelled_count": cancelled_count,
        "total_spent": float(total_spent),
        "first_booking": first_booking,
        "last_booking": last_booking
    }

async def ban_client(session: AsyncSession, user_id: int, reason: str):
    from bot.database.models import User
    from datetime import datetime
    user = await session.get(User, user_id)
    if user:
        user.is_banned = True
        user.ban_reason = reason
        user.banned_at = datetime.utcnow()
        await session.commit()

async def unban_client(session: AsyncSession, user_id: int):
    from bot.database.models import User
    user = await session.get(User, user_id)
    if user:
        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        await session.commit()

async def get_banned_clients(session: AsyncSession) -> list:
    from bot.database.models import User
    res = await session.execute(select(User).where(User.is_banned == True).order_by(User.banned_at.desc()))
    return list(res.scalars().all())

async def get_all_active_clients(session: AsyncSession) -> list[int]:
    from bot.database.models import Booking, BookingStatus
    from sqlalchemy import select
    res = await session.execute(
        select(Booking.user_id)
        .where(Booking.status == BookingStatus.confirmed)
        .group_by(Booking.user_id)
    )
    return [row[0] for row in res.fetchall()]

async def get_bookings_for_export(session: AsyncSession, year: int, month: int) -> list:
    from bot.database.models import Booking
    from sqlalchemy import select, and_, func
    res = await session.execute(
        select(Booking).where(
            and_(
                func.strftime('%Y', Booking.booking_date) == str(year),
                func.strftime('%m', Booking.booking_date) == f"{month:02d}"
            )
        ).order_by(Booking.booking_date.asc())
    )
    return list(res.scalars().all())

async def get_schedule_for_date(session: AsyncSession, target_date) -> dict:
    from bot.database.models import Booking, BookingStatus
    from sqlalchemy import select, and_
    
    res = await session.execute(
        select(Booking).where(
            and_(
                Booking.booking_date == target_date,
                Booking.status != BookingStatus.cancelled
            )
        ).order_by(Booking.shelter_num)
    )
    bookings = list(res.scalars().all())
    
    # Map attributes to comply with prompt's bk.tent_number, bk.full_name, etc.
    for b in bookings:
        b.tent_number = b.shelter_num
        b.check_in_date = b.booking_date
        b.full_name = b.client_name
        b.phone = b.client_phone
        
    occupied_nums = [b.shelter_num for b in bookings]
    free = [i for i in range(1, 11) if i not in occupied_nums]
    
    return {
        "occupied_bookings": bookings,
        "free": free
    }

async def admin_confirm_booking(session: AsyncSession, booking_id: int, admin_id: int):
    from bot.database.models import Booking, BookingStatus, Payment
    b = await session.get(Booking, booking_id)
    if b:
        b.status = BookingStatus.confirmed
        res = await session.execute(
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
        )
        payment = res.scalars().first()
        if payment:
            payment.status = "confirmed"
            from datetime import datetime
            payment.confirmed_at = datetime.utcnow()
            payment.confirmed_by = admin_id
        await session.commit()

async def admin_cancel_booking(session: AsyncSession, booking_id: int, reason: str, admin_id: int):
    from bot.database.models import Booking, BookingStatus, Payment
    b = await session.get(Booking, booking_id)
    if b:
        b.status = BookingStatus.cancelled
        b.admin_comment = reason
        b.cancelled_by = admin_id
        
        res = await session.execute(
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
        )
        payment = res.scalars().first()
        if payment:
            payment.status = "rejected"
            payment.rejection_reason = reason
        await session.commit()

async def admin_delete_booking(session: AsyncSession, booking_id: int):
    from bot.database.models import Booking
    b = await session.get(Booking, booking_id)
    if b:
        await session.delete(b)
        await session.commit()

# --- DYNAMIC PRICING ---
async def get_prices(session: AsyncSession) -> tuple[int, int]:
    """Повертає (weekday_price, weekend_price) з БД."""
    weekday = await get_setting(session, 'price_weekday', '1700')
    weekend = await get_setting(session, 'price_weekend', '2200')
    return int(weekday), int(weekend)

# --- TENT BLOCKING ---
async def block_tent(
    session: AsyncSession, tent_number: int, block_date: date,
    created_by: int, reason: str = None
) -> bool:
    """
    Блокує шатро на дату. Повертає True якщо успішно, False якщо вже є активне бронювання.
    """
    # Перевірити чи є підтверджене/активне бронювання
    existing = await session.execute(
        select(Booking).where(
            Booking.shelter_num == tent_number,
            Booking.booking_date == block_date,
            Booking.status.in_([BookingStatus.awaiting_payment, BookingStatus.payment_pending_review, BookingStatus.confirmed])
        )
    )
    if existing.scalars().first():
        return False  # Не можна заблокувати — є активне бронювання

    try:
        block = TentBlock(
            tent_number=tent_number,
            block_date=block_date,
            reason=reason,
            created_by=created_by
        )
        session.add(block)
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        return False  # Вже заблоковано

async def unblock_tent(session: AsyncSession, tent_number: int, block_date: date) -> bool:
    """Знімає блокування шатра на дату."""
    result = await session.execute(
        select(TentBlock).where(
            TentBlock.tent_number == tent_number,
            TentBlock.block_date == block_date
        )
    )
    block = result.scalar_one_or_none()
    if block:
        await session.delete(block)
        await session.commit()
        return True
    return False

async def get_blocks_for_date(session: AsyncSession, target_date: date) -> list[TentBlock]:
    """Всі заблоковані шатра на конкретну дату."""
    result = await session.execute(
        select(TentBlock).where(TentBlock.block_date == target_date)
    )
    return list(result.scalars().all())

async def get_blocks_for_month(session: AsyncSession, year: int, month: int) -> list[TentBlock]:
    """Всі блокування на місяць (для відображення в адмін-календарі)."""
    import calendar
    from_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    to_date = date(year, month, last_day)
    result = await session.execute(
        select(TentBlock).where(
            TentBlock.block_date >= from_date,
            TentBlock.block_date <= to_date
        ).order_by(TentBlock.block_date, TentBlock.tent_number)
    )
    return list(result.scalars().all())

async def is_tent_blocked(session: AsyncSession, tent_number: int, block_date: date) -> bool:
    """Перевірити чи шатро заблоковано на дату."""
    result = await session.execute(
        select(TentBlock).where(
            TentBlock.tent_number == tent_number,
            TentBlock.block_date == block_date
        )
    )
    return result.scalars().first() is not None

async def get_blocked_tent_numbers_for_date(session: AsyncSession, target_date: date) -> set[int]:
    """Швидко отримати множину номерів заблокованих шатер на дату."""
    blocks = await get_blocks_for_date(session, target_date)
    return {b.tent_number for b in blocks}

async def get_available_tents_for_date(session: AsyncSession, target_date: date) -> list[int]:
    """
    Повертає список номерів вільних шатер (1-10) на дату.
    Враховує: підтверджені/активні бронювання + ручні блокування адміна.
    """
    all_tents = set(range(1, 11))

    # Зайняті через бронювання
    booked = await session.execute(
        select(Booking.shelter_num).where(
            Booking.booking_date == target_date,
            Booking.status.in_([BookingStatus.confirmed, BookingStatus.awaiting_payment, BookingStatus.payment_pending_review])
        )
    )
    booked_tents = {row[0] for row in booked.fetchall()}

    # Заблоковані вручну адміном
    blocked_tents = await get_blocked_tent_numbers_for_date(session, target_date)

    occupied = booked_tents | blocked_tents
    return sorted(list(all_tents - occupied))

async def is_date_fully_booked(session: AsyncSession, target_date: date) -> bool:
    """Для calendar_kb — ❌ якщо всі 10 шатер недоступні."""
    available = await get_available_tents_for_date(session, target_date)
    return len(available) == 0


