# Optional ntfy notifications

Notifications are disabled by default. Prefer a protected self-hosted HTTPS ntfy server with an
access-controlled topic and a dedicated publishing token. Do not put a token in source control.

Set only these deployment secrets/settings when explicitly enabling the adapter:

```text
NTFY_ENABLED=true
NTFY_BASE_URL=https://ntfy.example.com
NTFY_TOPIC=personal-intelligence
NTFY_TOKEN_FILE=/run/secrets/ntfy_token
```

The adapter publishes only fixed concise notices for a ready briefing, a detected actionable email,
or an operational failure. It never publishes email subjects/bodies, briefing content, source text,
provider errors, or credentials. Each logical notice has a durable key and ntfy sequence ID, so a
retry updates the same notification rather than creating another one.

`ntfy.sh` is not the default. It requires `NTFY_ALLOW_PUBLIC_TOPIC=true`, a 24+ character topic,
and explicit risk acceptance. A delivery failure is recorded safely after briefing persistence and
does not fail ingestion or scheduling.
