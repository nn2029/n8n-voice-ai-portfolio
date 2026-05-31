# Project 3 — Voice-Driven CRM Assistant

> Drop a voice note in Slack. The assistant transcribes it with Whisper, decides whether to create a contact, log an activity, query the database, or just answer a question — using **OpenAI GPT-4o function calling** with three strict-schema tools. It runs the action against Supabase, then replies with a spoken confirmation in your cloned voice. Every turn is logged for short-term memory so it can handle "log a call with him too" right after "create a contact for Priya at Northwind."

## What it proves

- **Full conversational loop**: STT (Whisper) → reasoning (GPT-4o with function calling) → action (Supabase) → TTS (ElevenLabs) → delivery (Slack file upload).
- **OpenAI function calling** — three tools with strict JSON schemas (`tool_choice: auto`), dispatched via a Switch node, results threaded back into a spoken reply. Arguments arrive as a JSON string per the OpenAI spec — handled with a parse-and-validate Code node.
- **Short-term conversational memory** via Supabase: last 10 turns per user replayed into the LLM's message array.
- **Defensive input handling** — Slack URL verification handshake, mime-type gating, transcript validation, Whisper hallucination detection.
- **Production polish** — error sub-workflow, retries on every external call, separate response paths for verification / ignored / accepted.

## Architecture

```
[Slack Events API: file_shared] ──▶ POST webhook
        │
        ▼
   ┌─────────────────────┐
   │ Route Slack Event   │ ◀── handles: url_verification | non-audio | real event
   └─────────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
[Echo     [Skip-or-Accept branch]
challenge]      │
                ▼ (audio file received → respond 200 immediately so Slack doesn't retry)
        ┌──────────────────────┐
        │ Slack: Get File Info │
        └──────────────────────┘
                │
                ▼
        ┌────────────────────────┐
        │ Download Audio (Bearer)│
        └────────────────────────┘
                │
                ▼
        ┌─────────────────┐
        │ Whisper STT     │
        └─────────────────┘
                │
                ▼
        ┌──────────────────────┐
        │ Validate Transcript  │ ◀── min/max duration, hallucination check
        └──────────────────────┘
                │
                ▼
        ┌──────────────────────────┐
        │ Supabase: Load 10 turns  │ ◀── per-user short-term memory
        └──────────────────────────┘
                │
                ▼
        ┌────────────────────┐
        │ Build OpenAI Req   │ ◀── system + 3 function defs + memory + new user turn
        └────────────────────┘
                │
                ▼
        ┌─────────────────────────┐
        │ OpenAI Function Calling │
        └─────────────────────────┘
                │
                ▼
        ┌────────────────────┐
        │ Parse Response     │ ◀── tool_use block? or text block?
        └────────────────────┘
                │
                ▼
        ┌────────────────────┐
        │ Switch (tool name) │
        └────────────────────┘
        │       │       │       │
        ▼       ▼       ▼       ▼
   [create [log    [query  [no tool —
    contact] activity] contact] direct reply]
        │       │       │       │
        └───────┴───────┴───────┘
                │
                ▼
        ┌────────────────────┐
        │ Build Spoken Reply │ ◀── crafts the < 30-word spoken confirmation
        └────────────────────┘
                │
                ▼
        ┌────────────────────────┐
        │ ElevenLabs Synthesize  │ ◀── assistant voice tuning
        └────────────────────────┘
                │
                ▼
        ┌──────────────────────────┐
        │ Slack: Upload Audio Reply│
        └──────────────────────────┘
                │
                ▼
        ┌──────────────────────────────┐
        │ Supabase: Save Convo Turn    │ ◀── feeds next call's memory
        └──────────────────────────────┘

[Error Trigger] ──▶ [#automation-alerts]
```

## Why OpenAI function calling over single-shot classification

A naive design would prompt: "Output `{action: 'create_contact', ...}` JSON." That works for a demo and breaks the moment a user says something the prompt didn't anticipate ("actually scrap that and just tell me what time it is").

OpenAI function calling solves three problems at once:

1. **Structured input validation** — the `parameters` JSON Schema on each `tools[].function` is enforced at the API boundary. The model *cannot* return a `create_contact` call missing a `name`.
2. **Mixed responses** — a single completion can contain `message.content` (text preamble) *and* `message.tool_calls[]`. Both are surfaced; the text is used as the spoken preamble ("Sure, logging that — call with Priya about Q3 routing").
3. **No-tool path** — if the user just asks a question, the model returns only `message.content` with `finish_reason: 'stop'`. No brittle "is this a tool call?" regex needed.

> **Implementation gotcha**: OpenAI returns `tool_calls[i].function.arguments` as a **JSON-encoded string**, not an object. The Parse OpenAI Response node `JSON.parse()`s it. Anthropic returns the equivalent as an already-parsed object — easy to miss when porting between providers.

## Voice tuning for assistants

This project uses *one* voice with **distinct settings from sales** (Project #1):

```jsonc
{
  "stability": 0.55,         // steadier than sales (0.45) — assistants should sound calm
  "similarity_boost": 0.80,
  "style": 0.10,             // very low — theatrical assistants are annoying
  "use_speaker_boost": true
}
```

Same voice file, different feel — sales sells, assistants serve.

## Short-term memory design

A single Supabase table:

```sql
create table voice_conversations (
  id bigserial primary key,
  user_id text not null,
  user_transcript text not null,
  assistant_response text,
  tool_called text,
  tokens_in int, tokens_out int,
  created_at timestamptz default now()
);
create index on voice_conversations (user_id, created_at desc);
```

The `Supabase: Load Recent Context` node pulls the last 10 turns (`ORDER BY created_at DESC LIMIT 10`) and the Code node flips them oldest-first before threading into the OpenAI `messages` array. 10 turns is the sweet spot — covers most "follow up on that" intent without bloating the prompt context.

A production version would add:
- **TTL on memory** — anything > 24h shouldn't influence current turn.
- **Conversation IDs** — explicit reset signal ("forget that") or natural session breaks.
- **Vector memory for long-term** — pinecone/pgvector for "did I ever talk to anyone at Initech?"

## Cost per turn

| Component | Per turn (≈ 8s audio, 200-word reply) |
|-----------|----------------------------------------|
| Whisper-1 | ~$0.0008 (~$0.006/min × 8s) |
| OpenAI GPT-4o (~800 in, ~150 out) | ~$0.0035 |
| Supabase read + write | <$0.0001 |
| ElevenLabs turbo (~120 chars) | ~$0.036 |
| **Total** | **≈ $0.04 per turn** |

> 25 turns per dollar. A power user doing 50 actions a day costs ~$2/day.

Optimizations baked in:
- `whisper-1` instead of `gpt-4o-mini-transcribe` — Whisper is 10× cheaper for English.
- Memory limited to 10 turns (vs unbounded) caps GPT-4o input cost at ~$0.0035/turn even for power users.
- `turbo_v2_5` over `multilingual_v2` — half the cost on short replies.

## Test it

Easiest path: in the Slack app you set up, post a voice note in a channel the bot's in. Within 4-6 seconds you should hear a spoken reply.

Try these in sequence to exercise the memory:
1. "Create a contact for Priya Mehta, VP Operations at Northwind Logistics."
2. "Log a call with her about Q3 routing pricing."
3. "Who do I know at Northwind?"

The third call has no contact name in the audio — GPT-4o resolves "Northwind" via the conversation memory.

## Production gotchas (worth knowing for interview)

These are the real issues hit during build — each is a good "tell me about a bug you debugged" interview answer.

### 1. Slack `file_shared` event has NO mime type

Documented as carrying a `file` object, but in practice Slack sends only `file_id` in the event payload. My first version of `Route Slack Event` filtered out non-audio mimes upfront — but `event.file.mimetype` was always undefined, so every event was skipped. Fix: removed the mime check from the routing node; rely on Whisper's audio-only validation downstream. Saves an extra `files.info` call when you don't actually need to filter (Whisper rejects non-audio gracefully).

### 2. Slack fires `file_shared` 2-5 times per single voice note

A single voice note in Slack triggers the event multiple times as the file moves through Slack's lifecycle (recording started → upload complete → auto-transcription done → shared in channel). Each fire is an independent execution. Without idempotency, you get duplicate Supabase rows for every voice note.

**Idempotency fix** (drop-in Code node, place right after `Slack: Get File Info`):

```javascript
// Skip if we've already processed this file_id in the last hour.
const file_id = $input.first().json.id;
const sb = $('Supabase: Load Recent Context').all();
const already = sb.some(r => r.json && r.json.tool_called === `file:${file_id}`);
if (already) {
  return [{ json: { __skip: true, reason: `Already processed ${file_id}` } }];
}
return [{ json: { ...$input.first().json, file_id_tag: `file:${file_id}` } }];
```

Then modify `Supabase: Save Conversation Turn` to write `tool_called: file:${file_id}` (instead of just the bare tool name) so subsequent runs detect the duplicate. Adds one IF node + one expression edit; eliminates duplicate processing.

### 3. n8n Cloud's Supabase node halts on 0 rows by default

For a brand-new user, `voice_conversations` query returns `[]` and n8n stops the workflow there. Fix: enable **Always Output Data** in the node's Settings tab. Then handle the empty case in `Build OpenAI Request` by filtering rows missing `user_transcript` (Always Output Data emits a single `{}` placeholder, not a true empty array — caught me on the first run).

### 4. OpenAI `tool_calls[i].function.arguments` is a JSON-encoded STRING

Not an object. The Parse OpenAI Response node `JSON.parse()`s it. Anthropic returns the equivalent already-parsed; OpenAI doesn't. Easy port-between-providers gotcha.

### 5. Slack file upload "channel_not_found" with valid channel ID

The newer n8n Slack node version wants `channelId` as a plain string, not an array. Original code had `[$json.channel_id]` (legacy format). Dropped the brackets → works.

## Setup checklist (actual shipped version)

- [x] n8n Cloud (or self-hosted ≥ 1.50), import `workflow.json`
- [x] **Slack app**: create at api.slack.com/apps, add Bot scopes (`chat:write`, `chat:write.public`, `files:read`, `files:write`, `channels:read`), install to workspace, subscribe Event Subscriptions to `file_shared` (point Request URL at n8n production webhook), reinstall app after adding the event.
- [x] **Slack credential** in n8n: Slack API type, paste Bot User OAuth Token (`xoxb-...`).
- [x] **OpenAI** credential — single credential covers both Whisper transcription and GPT-4o function calling.
- [x] **ElevenLabs** credential — Header Auth type (Name: `xi-api-key`, Value: your key). Voice ID inlined in the URL (no env var). Starter tier required for API access from cloud IPs.
- [x] **Supabase** project: create the 3 tables via the SQL in this README, get **legacy `service_role`** JWT key (NOT the new `sb_secret_...` format — n8n's Supabase node was built for the legacy format), wire into n8n's Supabase credential.
- [x] **Tables wired in each Supabase node** via "From list" (not "By ID" — that requires the literal `tbl_id`). Filter on `Load Recent Context` set to `user_id = {{ $json.user_id }}`. Settings → **Always Output Data: ON** on `Load Recent Context`.
- [x] Activate workflow → copy production webhook URL → paste into Slack Event Subscriptions Request URL → wait for green verified ✓ → reinstall app to workspace.

## Test sequence (proves the conversational loop)

In Slack `#sales-outreach` (or any channel the bot is in), drop voice notes in sequence:

1. **"Create a contact for Priya Mehta, VP Operations at Northwind Logistics."**
   → Bot replies in ~6s with audio: *"Created contact for Priya Mehta at Northwind Logistics."*
   → New row in Supabase `contacts` table.

2. **"Log a call with her about Q3 routing pricing."**
   → Bot replies: *"Logged a call for Priya Mehta."*
   → New row in Supabase `activities` table.
   → **The "her" pronoun resolution proves memory works** — only possible because GPT-4o saw turn #1 in its messages array.

3. **"Who do I know at Northwind?"**
   → Bot replies: *"Found Priya Mehta at Northwind Logistics."*
   → Reads from Supabase via `query_contact` tool.
