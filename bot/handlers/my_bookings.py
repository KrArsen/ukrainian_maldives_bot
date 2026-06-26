# bot/handlers/my_bookings.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BookingStatus
from bot.database.queries import get_user_bookings

router = Router()

@router.message(F.text == "📋 Мої бронювання")
@router.message(Command("mybookings"))
async def cmd_my_bookings(message: Message, session: AsyncSession):
    """Displays user's booking history."""
    bookings = await get_user_bookings(session, message.from_user.id)
    if not bookings:
        await message.answer("У вас ще немає бронювань. Натисніть 📅 Забронювати! 😊")
        return
        
    lines = ["📋 <b>Мої бронювання:</b>\n"]
    for b in bookings:
        # Determine status icon and label
        status_label = "⏳ Очікує"
        if b.status == BookingStatus.confirmed:
            status_label = "✅ Підтверджено"
        elif b.status == BookingStatus.cancelled:
            status_label = "❌ Скасовано"
            
        date_str = b.booking_date.strftime("%d.%m.%Y")
        lines.append(f"🛖 Шатро №{b.shelter_num}  |  📅 {date_str}  |  {status_label}")
        
    lines.append(f"\nВсього: {len(bookings)}")
    
    await message.answer(text="\n".join(lines))
