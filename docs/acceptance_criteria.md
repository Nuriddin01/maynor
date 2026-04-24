# Acceptance Criteria
- Night/day/power nap flows завершаются без crash и сохраняют session request.
- Wake check-in сохраняет запись sleep entry.
- Alarm создается через минуты и по HH:MM, повторы ограничены.
- /stop_alarm CODE корректно останавливает будильник с валидным кодом.
- History показывает последние 10 записей.
- Stats показывают 7/30-day averages и инсайты.
- Settings позволяют менять timezone/language/audio/reminders/default nap/time format.
- В текстах присутствует wellbeing-дисклеймер.
- ICE Prioritization: alarms(9), core flows(10), stats(8), premium stub(5), weekly insights future(4).
