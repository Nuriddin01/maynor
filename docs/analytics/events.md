# Analytics events

## Product analytics

- `started_flow`
- `completed_flow`
- `abandoned_flow`
- `recommendation_generated`
- `recommendation_followed`
- `alarm_created`
- `alarm_dismissed`
- `alarm_failed`
- `wake_checkin_completed`
- `premium_screen_viewed`
- `paywall_shown`
- `subscription_started`
- `subscription_renewed`
- `subscription_canceled`

## Required fields

- event id
- user id or null
- name
- occurred at
- properties JSON

## Business metrics basis

- DAU/WAU/MAU from unique active users
- activation from first recommendation + first check-in
- conversion from premium screen to subscription started
- retention from repeated activity windows
- churn from subscription canceled/expired
