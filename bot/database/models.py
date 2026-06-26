import enum
from datetime import datetime, date
from sqlalchemy import BigInteger, Integer, String, Date, DateTime, Boolean, Enum, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database.engine import Base

class BookingStatus(str, enum.Enum):
    awaiting_payment       = "awaiting_payment"        # Очікує оплати
    payment_pending_review = "payment_pending_review"  # Скріншот надіслано, чекає перевірки
    confirmed              = "confirmed"               # Підтверджено
    cancelled              = "cancelled"               # Скасовано

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
    status:        Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.awaiting_payment)
    admin_comment: Mapped[str|None]      = mapped_column(Text)
    payment_deadline: Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", cascade="all, delete-orphan")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id:  Mapped[int|None] = mapped_column(Integer, nullable=True)
    user_id:     Mapped[int|None] = mapped_column(BigInteger, nullable=True)
    action_type: Mapped[str]      = mapped_column(String(50)) # 'created', 'confirmed', 'cancelled', 'reminder_sent'
    details:     Mapped[str]      = mapped_column(Text)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    monobank_card: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_comment: Mapped[str] = mapped_column(String(100), nullable=False)
    screenshot_file_id: Mapped[str|None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending") # pending | screenshot_sent | confirmed | rejected
    rejection_reason: Mapped[str|None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int|None] = mapped_column(BigInteger, nullable=True)

    booking: Mapped["Booking"] = relationship(back_populates="payments")
