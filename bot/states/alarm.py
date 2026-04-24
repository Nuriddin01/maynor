from aiogram.fsm.state import State, StatesGroup


class AlarmFlow(StatesGroup):
    waiting_minutes = State()
    waiting_clock_time = State()


class SettingsFlow(StatesGroup):
    waiting_timezone = State()
