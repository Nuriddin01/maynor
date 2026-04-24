from aiogram.fsm.state import State, StatesGroup


class SettingsFlow(StatesGroup):
    waiting_timezone = State()
