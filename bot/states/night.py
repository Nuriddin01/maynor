from aiogram.fsm.state import State, StatesGroup


class NightFlow(StatesGroup):
    slept_last_night = State()
    sleep_quality = State()
    current_sleepiness = State()
    current_stress = State()
    free_time = State()
    wants_alarm = State()
