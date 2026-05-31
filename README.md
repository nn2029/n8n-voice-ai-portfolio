# n8n + ElevenLabs Automation Portfolio

Three production-grade n8n workflows demonstrating end-to-end AI voice automation: LLM orchestration (OpenAI GPT-4o with JSON mode + function calling), high-fidelity voice synthesis (ElevenLabs), STT (Whisper), and multi-platform API integration.

Built to demonstrate the exact stack and patterns called out in the JD: workflow architecture, voice synthesis tuning, LLM orchestration, complex data handling, and monitoring/optimization.

---

## Portfolio at a glance

| # | Project | Status | What it proves | Stack |
|---|---------|---|---------------|-------|
| 1 | **AI Voice Sales Outreach Engine** | ✅ Live | Voice synthesis tuning, personalized LLM messaging, full CRM/webhook orchestration | n8n, OpenAI GPT-4o, ElevenLabs, Cloudflare R2, Airtable, Slack |
| 2 | **AI Podcast / Audio Newsletter Factory** | 📐 Designed | Multi-voice synthesis with per-persona tuning, JSON-mode LLM output, byte-level MP3 stitching | n8n, OpenAI GPT-4o (JSON mode), ElevenLabs (2 voices), R2 |
| 3 | **Voice-Driven CRM Assistant** | ✅ Live | Full STT → LLM → action → TTS conversational loop, OpenAI function calling with strict schemas, short-term memory | n8n, Whisper, OpenAI GPT-4o (function calling), Supabase, ElevenLabs, Slack |

Each project folder contains:
- `workflow.json` — importable into n8n (Workflows → Import from File)
- `README.md` — architecture, node-by-node walkthrough, design decisions, production gotchas, cost notes
- `demo-script.md` — 60-90 second interview talking points with prepped follow-up answers

See [`ARTIFACTS.md`](ARTIFACTS.md) for the exact screenshots/recordings to capture for portfolio submission.

---

## How to use this portfolio

### For the interview

1. **Lead with the architecture diagram** in each README — shows you think in systems, not steps.
2. **Demo Project 1 live** by running the curl in Terminal and watching nodes flip green in n8n's Executions tab. Then play the actual MP3 from Slack. 30 seconds of demo communicates more than 5 minutes of talking.
3. **Demo Project 3 live** by recording 3 voice notes in sequence (see `03-voice-crm-assistant/demo-script.md`) — the "her" pronoun resolution between turn 1 and turn 2 is the conversational-memory money shot.
4. **Talk about cost/token optimization** — every workflow logs per-execution spend. See the "Cost & optimization" section in each README. This separates a senior automator from a tutorial follower.
5. **Talk about the bugs you hit** — see "Production gotchas" sections. Each gotcha is a "tell me about a bug you debugged" answer that proves you've actually built this, not just imported a template.

### To reproduce yourself

1. **n8n** — Cloud or self-hosted, version ≥ 1.50
2. **API keys / accounts to set up**:
   - **OpenAI** ($5 min) — powers GPT-4o for all 3 projects + Whisper STT for Project 3. Use n8n's built-in "OpenAi API" credential type.
   - **ElevenLabs** Starter ($5/mo) — free tier blocks API access from cloud IP ranges. Use Header Auth credential (Name: `xi-api-key`, Value: your key) — n8n Cloud doesn't have a first-party ElevenLabs credential type.
   - **Cloudflare R2** (free) — bucket with Public Development URL enabled. Use n8n's "S3" credential type (NOT "AWS"), with custom endpoint + Force Path Style ON.
   - **Slack** (free) — Bot User OAuth Token via api.slack.com/apps. Scopes: `chat:write`, `chat:write.public`, `files:read`, `files:write`, `channels:read`.
   - **Airtable** (free, Project 1) — Personal Access Token with `data.records:read`, `data.records:write`, `schema.bases:read`.
   - **Supabase** (free, Project 3) — project with the 3 tables (SQL in P3 README), use legacy `service_role` JWT (NOT new `sb_secret_...`).

3. **Import each `workflow.json`** via n8n's Workflows → "+" → Import from File
4. **Wire credentials** on each HTTP / first-party node (the imported JSONs reference credentials by name; pick the right one from the dropdown on each node)
5. **Activate / Publish** the workflow → copy the production webhook URL → wire to the right trigger (CRM webhook for P1, Slack Event Subscription for P3)
6. Run the test payload (each README's "Test it" section)

---

## Engineering decisions worth defending

- **OpenAI everything** instead of mixing providers. Original draft used Claude for generation. Consolidated to OpenAI for one credential, one bill, one rate limit. Trade-off: weaker "I can use both" narrative, but easier ops. Function calling reliability was the tiebreaker for Project 3.
- **Cloudflare R2 over AWS S3.** Zero egress fees + 10 GB free tier = $0 storage cost. Same S3 API; n8n's "S3" credential supports custom endpoints (the "AWS" credential type doesn't).
- **ElevenLabs voice settings are tuned per persona, not defaults.** Project 1 uses `stability: 0.45, similarity_boost: 0.85, style: 0.20` for warm sales tone. Project 3 uses `stability: 0.55, style: 0.10` for assistant calm. Picked from listening tests, not docs.
- **Deterministic file paths** based on immutable upstream data (`lead.received_at` in P1) instead of `$now()` — different nodes can independently reconstruct the same path without coordination. Critical because n8n's generic S3 node returns only `{success: true}`, not the upload URL.
- **OpenAI function calling over single-shot intent classification** (P3). Strict JSON schemas enforced at the API boundary mean the model literally cannot return a malformed tool call. Mixed responses (text preamble + tool call) handled natively. No regex parsing.
- **Header Auth credential pattern** for ElevenLabs (n8n Cloud has no first-party ElevenLabs cred type). Generic and portable; same pattern works for any API n8n doesn't have a dedicated node for.
- **"Always Output Data" on empty Supabase queries** (P3). Default n8n behavior halts the workflow when a query returns zero rows — fatal for a first-time-user conversational assistant. Filtering empty placeholder rows downstream is the second half of that fix.

---

## Production gotchas I solved (interview ammo)

Each project's README has a "Production gotchas" section. The highlights across all three:

1. **Slack `file_shared` doesn't include mime type** — undocumented; my upfront audio filter was rejecting every event. Fix: filter downstream after `files.info`.
2. **Slack fires `file_shared` 2-5 times per voice note** — file lifecycle (recording → upload → transcription → channel share) each triggers a separate event. Need idempotency by file_id to avoid duplicate Supabase rows.
3. **n8n's "S3" node returns only `{success: true}`** — no Bucket/Key for downstream nodes to read. Reconstruct paths deterministically.
4. **n8n Cloud's Supabase node halts on 0 rows by default** — need to enable "Always Output Data" + handle the resulting `[{}]` placeholder in downstream code.
5. **OpenAI function calling `arguments` is a JSON-encoded string**, not an object. `JSON.parse()` it. Anthropic returns it pre-parsed.
6. **ElevenLabs free tier blocked from cloud IP ranges** — abuse detection. Starter $5/mo unlocks. Worth knowing before you start debugging your auth headers for an hour.
7. **n8n Cloud has no first-party ElevenLabs credential type** — community node. Use generic Header Auth with `xi-api-key`.
8. **Airtable PAT needs `schema.bases:read` scope** for n8n's table dropdown to populate — easy to miss when granting only `data.records:*`.

---

## What this portfolio proves against the JD bullets

| JD requirement | Demonstrated in |
|---|---|
| n8n mastery (nodes, expressions, JS) | All 3 projects. Code nodes with non-trivial JS (prompt building, response parsing, deterministic path reconstruction, idempotency). Switch/IF routing. Error trigger sub-workflows. |
| ElevenLabs expert | Per-persona voice tuning explained with rationale. Header Auth credential pattern. Multiple model selection (`turbo_v2_5`). |
| LLM orchestration (OpenAI / Claude / local) | OpenAI GPT-4o across all 3 projects with three distinct API features: standard chat (P1), JSON mode (P2), function calling with strict schemas (P3). |
| Audio engineering (stability, clarity, style) | P1 and P3 use tuned voice_settings, each per use case. P2's whole point is per-persona tuning lookup. |
| API management (CRMs, DBs, social) | Webhook + Slack OAuth + R2/S3 + Airtable PAT + Supabase service_role + ElevenLabs Header Auth, all wired in n8n. |
| Monitoring & optimization | Per-execution cost telemetry computed from `usage.prompt_tokens` / `usage.completion_tokens`. Logged to Airtable for pivot analysis. Error trigger → `#automation-alerts` with clickable execution link. |
| JavaScript/Node.js for custom functions | Heavy use of Code nodes — Build Prompt, Parse + Validate, Build OpenAI Request (with tool definitions), Build Spoken Reply. |
| JSON, Regex, nested data | Slack event payload parsing, OpenAI tool_call argument JSON.parse, Whisper hallucination regex detection, lead payload normalization. |
| Vector DBs / LangChain | Mentioned as roadmap extension in P3 README (pgvector for long-term memory). Not in current scope. |
