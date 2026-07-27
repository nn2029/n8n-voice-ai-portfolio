# Live provider setup

The deterministic mode needs no paid accounts. Live integrations are opt-in and stay behind service adapters.

## OpenAI or Anthropic

Set one or both provider keys in `.env`. Agent definitions may select `openai`, `anthropic`, `mock`, or `auto`. `auto` uses configured providers in a deterministic order and falls back to mock mode when neither is available.

## Google Calendar

The platform deliberately does not hand Google credentials to a model or n8n workflow. Configure `CALENDAR_TOOL_URL` to point at a small authenticated calendar service that accepts:

```json
{
  "title": "Voice-booked appointment",
  "start_at": "2026-08-05T10:00:00+00:00",
  "end_at": "2026-08-05T10:30:00+00:00"
}
```

The request includes an `Idempotency-Key` header. The adapter expects an `event_id` or `id` in the response. `CALENDAR_TOOL_TOKEN` is sent as a bearer token when configured.

## Voice provider

Vapi, Retell, Twilio, or another provider can call the FastAPI tool endpoints. Create the platform call first, then send structured turn requests to `/v1/voice/calls/{call_id}/turn`. Provider lifecycle callbacks should pass through the included n8n workflow and `/v1/voice/provider-events`, which deduplicates by provider event ID.

## n8n

Import the JSON files under `workflows/`. The Docker stack sets `AGENT_API_URL=http://api:8000`. No credentials are embedded in the exported workflows.

## Production note

Before handling real callers or customer records, add webhook signature verification, tenant authentication, RBAC, consent and recording notices, retention controls, secret management, and provider-specific acceptance tests.
