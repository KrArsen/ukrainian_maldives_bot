# bot/states/admin_states.py
from aiogram.fsm.state import State, StatesGroup

class AdminPropertyStates(StatesGroup):
    ADD_NAME = State()
    ADD_DESCRIPTION = State()
    ADD_CAPACITY = State()
    ADD_PRICE_NIGHT = State()
    ADD_PRICE_WEEKEND = State()
    ADD_AMENITIES = State()
    ADD_PHOTOS = State()
    
    EDIT_FIELD = State() # Generic editing state

class AdminBroadcastStates(StatesGroup):
    ENTER_MESSAGE = State() # Text + optional media

class AdminBookingStates(StatesGroup):
    ADD_COMMENT = State()
    SEND_MESSAGE = State()
