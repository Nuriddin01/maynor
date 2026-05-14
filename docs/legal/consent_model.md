# Consent model

## Consent types

| Type | Required | Purpose |
|---|---|---|
| Core consent | Yes | Run bot flows and store minimal product data |
| Privacy consent | Yes | Process data according to privacy policy |
| Marketing consent | No | Send promotional messages and offers |

Marketing consent is separate from core product consent. Refusing marketing consent must not block basic product usage.

## Versioning

Every consent has:

- type
- version
- accepted flag
- accepted timestamp
- revoked timestamp

When legal text changes materially, a new version is created.
