from aiogram.fsm.state import State, StatesGroup


class PowerNapFlow(StatesGroup):
    slept_last_night = State()
    current_sleepiness = State()
    free_time = State()
    wants_alarm = State()
