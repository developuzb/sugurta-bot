from aiogram.fsm.state import StatesGroup, State
from aiogram import Router

router = Router()

class InsuranceState(StatesGroup):
    vehicle = State()
    region = State()
    subregion = State()
    insurance_type = State()
    duration = State()   # 🔥 QO‘SHILDI
    phone = State()      # (senda ishlatilgan, lekin yo‘q bo‘lishi mumkin)