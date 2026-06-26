# bot/states/booking_states.py
from aiogram.fsm.state import State, StatesGroup

class BookingFSM(StatesGroup):
    choosing_shelter = State()  # Крок 1
    choosing_date    = State()  # Крок 2
    entering_name    = State()  # Крок 3
    sharing_phone    = State()  # Крок 4
    confirming       = State()  # Крок 5

class AdminFSM(StatesGroup):
    waiting_cancel_reason = State()
