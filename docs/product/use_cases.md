# Use cases

## UC-1 Night sleep preparation

Goal: receive a short protocol for falling asleep.

Actors: user, bot, recommendation service.

Preconditions: user accepted required consent.

Main flow:

1. user chooses night sleep
2. bot asks slept minutes, quality, sleepiness, stress, free time, alarm, audio
3. recommendation service creates decision trace and protocol
4. bot sends concise steps and disclaimer
5. analytics event is saved

Alternative:

- invalid number -> bot asks again
- consent missing -> bot asks to accept required consent

## UC-2 Power nap

Goal: recover in 10-20 minutes.

Main flow:

1. user chooses power nap
2. bot asks current sleepiness and available time
3. recommendation service selects 10/15/20 minutes
4. alarm is created with idempotency key
5. follow-up check-in is offered

## UC-3 Delete data

Goal: remove user data.

Main flow:

1. user requests deletion
2. system confirms identity boundary through Telegram/admin context
3. user records, entries, recommendations and consents are removed
4. audit log records deletion event
