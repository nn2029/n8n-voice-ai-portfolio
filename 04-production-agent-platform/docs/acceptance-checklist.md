# Acceptance checklist

## Multi-tenant automation control plane

- [x] Tenant-scoped agent definitions
- [x] Email triage, CRM update, document generation, and daily report agents
- [x] Deterministic mock mode
- [x] OpenAI and Anthropic adapters
- [x] Redis-backed queue with in-memory fallback
- [x] PostgreSQL production configuration with SQLite local mode
- [x] Idempotent execution keys
- [x] Human approval, rejection, cancellation, replay, and failed-execution listing
- [x] Trace IDs, audit events, provider, latency, and model-cost metadata
- [x] Importable n8n workflows
- [x] Next.js operations console
- [x] Tests for idempotency, approvals, replay, and tenant boundaries

## Voice operations agent

- [x] Duplicate-safe provider call creation
- [x] Grounded FAQ confidence and escalation
- [x] CRM contact upsert
- [x] Conflict-safe booking
- [x] Calendar service adapter with deterministic fallback
- [x] Emergency and unsupported-intent handoff
- [x] Failed-transfer take-message fallback
- [x] Provider callback deduplication
- [x] Transcript, tool history, summary, latency, cost, and outcome state
- [x] Importable post-call workflow
- [x] Tests for booking conflicts, duplicate callbacks, and transfer failure

## Explicitly deferred before real customer traffic

- [ ] Identity, tenant authentication, and RBAC
- [ ] Managed migrations, backups, restore drills, and high availability
- [ ] Dedicated asynchronous worker deployment with visibility timeouts
- [ ] Webhook signature verification
- [ ] Real CRM, email, telephony, and calendar acceptance tests
- [ ] Load and concurrency testing
- [ ] Formal privacy, retention, consent, security, and legal review
