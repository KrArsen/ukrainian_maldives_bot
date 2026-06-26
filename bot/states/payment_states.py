from aiogram.fsm.state import State, StatesGroup

class PaymentStates(StatesGroup):
    waiting_screenshot = State()      # Очікуємо скріншот від користувача
    waiting_reject_reason = State()   # Адмін вводить причину відхилення
