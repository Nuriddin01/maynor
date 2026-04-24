# Security Model
- Confidentiality: минимизация данных, no token logging, alarm code redaction in logs.
- Integrity: input validation, strict ranges, explicit state flows.
- Availability: scheduler restore on restart, bounded alarm retries.
- Authentication: reliance on Telegram user identity.
- Access Control: per-user data isolation via telegram_id/user_id binding.
- Encryption recommendations: TLS in transit, encrypted backup storage at rest.
- Threats: account takeover, data leakage via logs, alarm spam abuse.
- Incident notes: document event timeline from audit_logs, rotate bot token, notify users.
