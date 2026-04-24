from aiogram.fsm.state import State, StatesGroup


class WakeCheckinFlow(StatesGroup):
    duration_minutes = State()
    quality = State()
    felt_after = State()
    helpfulness = State()
    notes = State()
