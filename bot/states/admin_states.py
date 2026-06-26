# bot/states/admin_states.py
from aiogram.fsm.state import State, StatesGroup

class AdminBookingActions(StatesGroup):
    waiting_cancel_reason = State()

class AdminPaymentActions(StatesGroup):
    waiting_rejection_reason = State()

class AdminClientActions(StatesGroup):
    waiting_ban_reason = State()

class AdminSearch(StatesGroup):
    waiting_search_query = State()

class AdminBroadcast(StatesGroup):
    waiting_broadcast_text = State()

class AdminSettings(StatesGroup):
    waiting_price_input = State()
    waiting_timeout_input = State()
