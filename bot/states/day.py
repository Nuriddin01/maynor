from aiogram.fsm.state import State, StatesGroup


class DayFlow(StatesGroup):
    slept_last_night = State()
    current_energy = State()
    current_sleepiness = State()
    current_stress = State()
    free_time = State()
    intention = State()
    wants_alarm = State()
