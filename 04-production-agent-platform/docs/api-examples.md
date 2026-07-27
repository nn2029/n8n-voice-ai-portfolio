# API examples

## Seed the demo tenant and agents

```bash
curl -X POST http://localhost:8000/v1/demo/seed
```

## Run an approval-gated document agent

Use the returned tenant and document-agent IDs:

```bash
curl -X POST http://localhost:8000/v1/agents/AGENT_ID/execute \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "TENANT_ID",
    "idempotency_key": "proposal-001",
    "payload": {
      "subject": "Customer renewal proposal",
      "recipient": "Northwind Logistics"
    }
  }'
```

Repeat the request with the same idempotency key and confirm the same execution ID returns.

## Approve the execution

```bash
curl -X POST http://localhost:8000/v1/executions/EXECUTION_ID/approve \
  -H 'content-type: application/json' \
  -d '{"actor":"portfolio-reviewer","note":"Approved after review"}'
```

## Start and use a voice call

```bash
curl -X POST http://localhost:8000/v1/voice/calls \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"TENANT_ID","provider_call_id":"demo-call-1","caller_phone":"+2348001234567"}'
```

```bash
curl -X POST http://localhost:8000/v1/voice/calls/CALL_ID/turn \
  -H 'content-type: application/json' \
  -d '{
    "transcript":"Please book me for August 5 at 10am",
    "intent":"book",
    "contact_name":"Portfolio Reviewer",
    "start_at":"2026-08-05T10:00:00Z",
    "duration_minutes":30
  }'
```

## Test bounded escalation

```bash
curl -X POST http://localhost:8000/v1/voice/calls/CALL_ID/turn \
  -H 'content-type: application/json' \
  -d '{
    "transcript":"There is a fire and immediate danger",
    "intent":"unknown",
    "simulate_transfer_failure":true
  }'
```
