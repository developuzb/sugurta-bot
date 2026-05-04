from aiogram.fsm.state import State, StatesGroup


class ReminderState(StatesGroup):
    expiry_date = State()      # Sug'urta tugash sanasi (matn)
    phone = State()            # Telefon raqam
    remind_days = State()      # Eslatish kunlari (3/2/1)