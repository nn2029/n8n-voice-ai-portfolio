# Production Agent Platform

A working portfolio-grade platform that implements both previously specified systems:

1. a multi-tenant AI automation control plane; and
2. a voice operations agent with CRM, appointment booking, grounded FAQ responses, human handoff, provider-event deduplication, and post-call operations.

The repository runs in deterministic mock mode without paid provider keys. OpenAI and Anthropic adapters are available when credentials are configured. Models only recommend structured actions; authorised services execute actions after policy and approval checks.

## What is implemented

### Automation control plane

- tenant-scoped agent definitions and executions;
- email triage, CRM update, document generation, and daily-report agent types;
- idempotency keys for duplicate-safe trigger handling;
- queued, running, waiting-approval, completed, failed, cancelled, and replayed flows;
- human approval for customer-facing or policy-sensitive actions;
- OpenAI, Anthropic, and deterministic mock provider routing with ordered fallback;
- trace IDs, audit events, provider, latency, cost, failure reason, replay, and cancellation;
- importable n8n reference workflows.

### Voice operations

- provider call creation with duplicate-safe call IDs;
- grounded FAQ responses with source-aware confidence;
- emergency, low-confidence, and unsupported-request escalation;
- conflict-safe appointment booking through a database uniqueness constraint;
- CRM contact upsert;
- human transfer with a bounded take-message fallback when transfer fails;
- provider webhook deduplication;
- call transcript, tool history, summary, latency, cost, and outcome metrics;
- importable post-call n8n workflow.

## Local run

```bash
cp .env.example .env
docker compose up --build
```

- API: `http://localhost:8000/docs`
- Operations UI: `http://localhost:3000`
- n8n: `http://localhost:5678`

The FastAPI service also runs without Docker using SQLite:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Validation

```bash
cd backend
pytest -q
python -m compileall app tests

cd ../frontend
npm install
npm run build
```

Tests cover duplicate-safe executions, human approval, replay, booking conflicts, provider callback deduplication, emergency escalation, failed-transfer fallback, and tenant-boundary enforcement.

## Honest scope boundary

This is a complete, runnable portfolio implementation, not a claim that it has operated under real customer traffic. The deterministic mode is fully testable. Live provider calls require the relevant accounts and credentials. Production rollout would still require managed secret storage, tenant authentication and RBAC, migration tooling, backups, rate limiting, structured telemetry export, load testing, provider acceptance testing, and legal/privacy review for the chosen voice use case.
