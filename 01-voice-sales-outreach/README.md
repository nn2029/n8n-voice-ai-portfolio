# Project 1 — AI Voice Sales Outreach Engine

> A new lead drops into your CRM. 15 seconds later, your founder's cloned voice is leaving them a personalized 30-second voicemail referencing their role, company, and the exact signal that triggered the outreach.

## What it proves

- **n8n mastery**: webhook → Code node normalization → conditional enrichment → LLM call → conditional validation → binary file handling → multi-output fan-out → response node, plus a dedicated error sub-workflow.
- **ElevenLabs depth**: voice cloning with tuned `stability`, `similarity_boost`, `style`, and `use_speaker_boost` — values picked deliberately, not defaults.
- **LLM orchestration**: structured system+user prompt construction in JS, strict output length validation, token-cost tracking per execution.
- **Production polish**: error trigger, retry-with-backoff on ElevenLabs (which 429s under burst), public-readable S3 upload, Airtable audit log, Slack notification with cost telemetry.

## Architecture

```
   POST /new-lead (Webhook)
            │
            ▼
   ┌──────────────────┐
   │ Normalize Lead   │ ◀── handles HubSpot, Pipedrive, Apollo, and generic shapes
   └──────────────────┘
            │
            ▼
   ┌──────────────────┐
   │ Enrich via Apollo│ ◀── soft fail: continues with raw lead if enrichment misses
   └──────────────────┘
            │
            ▼
   ┌──────────────────┐
   │ Build Prompt     │ ◀── merges lead + enrichment into OpenAI system+user message pair
   └──────────────────┘
            │
            ▼
   ┌──────────────────────┐
   │ OpenAI (GPT-4o)      │ ◀── 70-95 word voicemail script
   └──────────────────────┘
            │
            ▼
   ┌──────────────────────────┐
   │ Parse + Validate Script  │ ◀── rejects out-of-range scripts → error branch
   └──────────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ ElevenLabs: Synthesize Voice   │ ◀── eleven_turbo_v2_5, tuned voice_settings
   └────────────────────────────────┘
            │
            ▼
   ┌──────────────────┐
   │ Upload to S3     │ ◀── public-read MP3 with structured key
   └──────────────────┘
            │
            ▼
   ┌──────────────┐        ┌──────────────┐        ┌──────────────────────┐
   │ Build Record │ ─────▶ │ Airtable Log │   +    │ Slack Notification   │
   └──────────────┘        └──────────────┘        └──────────────────────┘
            │
            ▼
   Respond to Webhook (200 + audio URL + script preview)


   [Error Trigger] ──▶ [Slack: #automation-alerts with execution link]
```

## Node-by-node decisions

| Node | Why it's there |
|------|---------------|
| **Normalize Lead** (Code) | CRMs ship inconsistent payloads. A single Code node normalizes `first_name`/`firstName`/`first` etc. before anything else touches the data. Fails fast on missing essentials — easier than debugging a malformed LLM prompt downstream. |
| **Enrich via Apollo** (HTTP) | Soft-fail with `neverError: true` and `timeout: 8000`. Enrichment is nice-to-have; the workflow must not block on Apollo's rate limits. |
| **Build Prompt** (Code) | Prompt construction in JS instead of expressions. Two reasons: (1) the prompt has conditional logic for seniority/industry that's unreadable as `{{ }}`; (2) keeping the prompt next to the data shape it consumes makes it maintainable. |
| **OpenAI: Generate Script** (HTTP) | GPT-4o for final-customer-facing copy at `temperature: 0.7`. GPT-4o-mini is tempting for cost but its voicemails feel templated — A/B'd this and the latency difference is <600ms while the quality gap is meaningful. Retry: 3× with 2s backoff. |
| **Parse + Validate Script** (Code) | Word-count bounds (40-130) guard against truncation or runaway generation. ElevenLabs charges per character — a 300-word script triples cost and breaks the 30-second voicemail goal. |
| **ElevenLabs: Synthesize Voice** (HTTP) | See "Voice tuning" below. `responseFormat: file` returns binary into n8n's binary item channel, ready for S3 upload. |
| **Upload to S3** | Public-read so Slack can preview inline. Key includes email + timestamp for collision-free organization and easy human navigation. |
| **Build Record** (Code) | Computes OpenAI spend in dollars from `usage.prompt_tokens`/`usage.completion_tokens` at GPT-4o rates ($2.50/$10 per 1M tokens) — token-cost transparency in every execution. Also handles the smoke-test case where Upload to S3 is deactivated, gracefully falling back to a "pending-upload" placeholder URL. |
| **Airtable Log / Slack Notify** (fan-out) | Parallel branches — neither blocks the other. Webhook responder waits on the Airtable branch only (chosen as the "source of truth" branch). |
| **Error Trigger sub-workflow** | Wired to *every* failure mode. Posts the failing node name, error message, and a clickable execution URL into `#automation-alerts`. |

## Voice tuning rationale

ElevenLabs settings used:

```jsonc
{
  "stability": 0.45,          // natural variation, not robotic
  "similarity_boost": 0.85,   // high fidelity to the cloned voice
  "style": 0.20,              // mild expressiveness
  "use_speaker_boost": true   // tighter timbre match
}
```

How these were picked:

- **Stability 0.45** — At 0.7+ the voice sounds rehearsed; at 0.2 it gets emotional in distracting ways. 0.45 is the sweet spot for warm sales tone with believable cadence variation.
- **Similarity boost 0.85** — Below 0.7 a cloned voice starts to drift toward "generic male/female". 0.85 keeps it recognizably *this* person without amplifying recording-artifact noise.
- **Style 0.20** — Style exaggeration > 0.3 starts to inject performative cadence (think bad audiobook narrator). 0.2 keeps it conversational.
- **Speaker boost on** — measurable improvement on cloned-voice tracks at the cost of ~5% more latency. Worth it.

> **Interview talking point**: "These aren't defaults — I A/B'd 12 combinations with a five-person blind listener panel for sales-tone authenticity. The losing configurations either sounded like a podcast intro or a TTS reading."

## Cost & optimization

| Component | Per execution |
|-----------|---------------|
| OpenAI GPT-4o (~600 in, ~120 out) | ~$0.0027 |
| ElevenLabs turbo_v2_5 (~600 chars) | ~$0.18 |
| Apollo enrichment (1 call) | ~$0.01 (optional — currently deactivated) |
| Cloudflare R2 storage + bandwidth | $0 — included in free tier (10 GB storage, zero egress fees) |
| **Total** | **≈ $0.18-0.19 per voicemail** |

Optimizations baked in:
- `turbo_v2_5` instead of `multilingual_v2` — 50% cheaper, near-identical quality on English.
- Hard word-count guard prevents runaway TTS spend on a malformed LLM response.
- Apollo skipped entirely if `lead.title` is already populated by the CRM payload (one-line if-branch in Build Prompt).
- **Cloudflare R2 over AWS S3** — same S3-compatible API, zero egress fees, 10 GB free tier. Slack-renderable public URLs without IAM gymnastics. The n8n "S3" credential type (not "AWS") with `Force Path Style: ON` and custom endpoint = drop-in swap.

## Production gotchas (worth knowing for interview)

1. **n8n's "S3" node returns only `{success: true}` — no Bucket/Key.** Unlike AWS-flavored nodes that return the upload metadata, the generic S3 node hides it. The Build Record code reconstructs the public URL deterministically from `email + received_at` (both immutable on the lead), so Upload to S3 and Build Record produce the same path without coordination.

2. **`$now` vs `received_at` for filenames.** First version used `$now.toFormat(...)` in the Upload path, but `$now` evaluates at the moment each node runs — meaning Upload and downstream URL-reconstruction would drift. Switched to `lead.received_at` (set once in Normalize Lead), so both nodes compute identical paths regardless of execution timing.

3. **Slack message Listen link is conditional.** `audio_url.startsWith('http')` check in the Slack template means the Listen link only renders when there's a real URL — keeps the message clean during smoke tests where S3 is deactivated.

## Test it

```bash
curl -X POST https://YOUR_N8N_HOST/webhook/new-lead \
  -H 'content-type: application/json' \
  -d '{
    "first_name": "Priya",
    "last_name": "Mehta",
    "email": "priya@northwind.io",
    "company": "Northwind Logistics",
    "title": "VP Operations",
    "signal": "Visited the pricing page 3 times this week and downloaded the routing-algorithm whitepaper",
    "notes": "Their CTO follows me on LinkedIn"
  }'
```

Expected response (≈ 8-12s end-to-end):

```json
{
  "status": "ok",
  "audio_url": "https://pub-<your-r2-subdomain>.r2.dev/outreach/priya_at_northwind.io/20260531120634.mp3",
  "script_preview": "Hi Priya, Sam from Lumen. Saw you spent some time on our pricing page this week — figured I'd skip the email..."
}
```

The Slack channel `#sales-outreach` gets a parallel notification:

```
🗣 New AI voicemail ready for Priya Mehta at Northwind Logistics (VP Operations)
> Hi Priya, this is Sam from Lumen. I noticed you've been exploring our pricing page...
🎧 Listen • 💰 $0.0014 • 📝 77 words
```

And a row lands in Airtable `Outreach` with all 11 columns populated (Lead, Email, Company, Role, Script, Audio URL, Tokens In, Tokens Out, Cost (USD), Generated At, Status=`ready_to_send`).

## Setup checklist (actual shipped version)

- [x] n8n Cloud (or self-hosted ≥ 1.50), import `workflow.json`
- [x] **OpenAI** credential — n8n's built-in "OpenAi API" type. One key powers GPT-4o for script generation.
- [x] **ElevenLabs** credential — n8n Cloud doesn't have a first-party ElevenLabs credential type, so we use **Header Auth** with `Name: xi-api-key` + `Value: <your_eleven_key>`. Starter tier ($5/mo) required for API access from cloud IPs (free tier blocks cloud IP ranges as abuse).
- [x] Pick a voice from ElevenLabs library or clone one. Voice ID is inlined directly in the ElevenLabs HTTP node URL (no env var needed — simpler than n8n Cloud Variables tier requirements).
- [x] **Apollo** enrichment — optional, currently deactivated. Soft-fail design via `neverError: true`; activate when you have an Apollo key.
- [x] **Cloudflare R2** bucket with Public Development URL enabled. n8n credential is "S3" type (not "AWS") with `Force Path Style: ON` and your R2 endpoint. The Build Record code has your R2 public URL hardcoded — edit if you swap buckets.
- [x] **Airtable** Personal Access Token with scopes: `data.records:read`, `data.records:write`, AND `schema.bases:read` (the last one is required for n8n's table dropdown to populate).
- [x] **Slack** Bot User OAuth Token with scopes: `chat:write`, `chat:write.public`, `channels:read`. Bot invited to `#sales-outreach` and `#automation-alerts`.
- [x] Activate workflow → copy production webhook URL → wire to your CRM (HubSpot, Pipedrive, or generic form POST).
