import enum
from datetime import datetime, date
from sqlalchemy import BigInteger, Integer, String, Date, DateTime, Boolean, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column
from bot.database.engine import Base

class BookingStatus(str, enum.Enum):
    pending   = "pending"    # Очікує підтвердження адміна
    confirmed = "confirmed"  # Підтверджено
    cancelled = "cancelled"  # Скасовано

class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    username:    Mapped[str|None]  = mapped_column(String(50))
    full_name:   Mapped[str|None]  = mapped_column(String(100))
    is_admin:    Mapped[bool]      = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)

class Booking(Base):
    __tablename__ = "bookings"
    id:            Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:       Mapped[int]           = mapped_column(BigInteger)
    shelter_num:   Mapped[int]           = mapped_column(Integer)        # 1..10
    booking_date:  Mapped[date]          = mapped_column(Date)           # Дата (1 ніч)
    client_name:   Mapped[str]           = mapped_column(String(100))    # Введено вручну
    client_phone:  Mapped[str]           = mapped_column(String(20))     # Через кнопку
    status:        Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.pending)
    admin_comment: Mapped[str|None]      = mapped_column(Text)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id:  Mapped[int|None] = mapped_column(Integer, nullable=True)
    user_id:     Mapped[int|None] = mapped_column(BigInteger, nullable=True)
    action_type: Mapped[str]      = mapped_column(String(50)) # 'created', 'confirmed', 'cancelled', 'reminder_sent'
    details:     Mapped[str]      = mapped_column(Text)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
