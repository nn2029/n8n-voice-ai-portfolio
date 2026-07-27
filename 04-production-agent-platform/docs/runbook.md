# Operations Runbook

## Start and smoke test

1. Copy `.env.example` to `.env` and set a strong `N8N_ENCRYPTION_KEY`.
2. Run `docker compose up --build`.
3. Open `/health` and confirm `status=ok`.
4. Create a tenant, then an agent, then execute it from `/docs`.
5. For an approval-gated agent, verify `waiting_approval`, approve it, and confirm the audit sequence.
6. Start two voice calls and try the same appointment slot; the second must receive a conflict.

## Failure drills

- Repeat the same execution idempotency key and verify the same execution is returned.
- Repeat the same voice provider event ID and verify `duplicate=true`.
- Remove model credentials and verify mock fallback still completes.
- Submit emergency language with `simulate_transfer_failure=true`; verify the call enters `handoff_failed` and returns `take_message`.
- Stop PostgreSQL in Docker and confirm the API fails closed rather than claiming an action completed.

## Production hardening checklist

- managed Postgres and Redis;
- Alembic migrations;
- authenticated tenant context and RBAC;
- secrets manager and credential rotation;
- real queue workers with retries, cancellation, dead-letter queues, and visibility timeouts;
- OpenTelemetry traces, structured logs, alerts, and dashboards;
- provider webhook signature verification;
- calendar/CRM adapters with idempotency and reconciliation;
- rate limits, abuse controls, retention policy, backups, restore testing, and incident response;
- load, concurrency, provider acceptance, and recovery testing;
- legal/privacy review for recordings, transcripts, consent, retention, and human transfer.
