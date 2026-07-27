# 90-second portfolio demo

1. Open the operations UI and show the empty execution and call metrics.
2. In FastAPI docs, create a tenant and a `document_generation` agent with `requires_approval=true`.
3. Execute it twice using the same idempotency key. Show that the same execution ID returns and the state is `waiting_approval`.
4. Approve it and open `/v1/audit` to show queued, running, approval requested, approval approved, and completed events under one trace ID.
5. Start two voice calls. Book 10:00 for the first caller, then attempt 10:00 for the second. Show the database-backed conflict response.
6. Send emergency language with a simulated transfer failure. Show that the system does not improvise: it records `handoff_failed` and returns the bounded `take_message` action.
7. End by opening the architecture pack and explaining the core rule: models recommend actions, authorised services execute them.
