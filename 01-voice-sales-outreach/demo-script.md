# Interview demo script — Voice Sales Outreach (60-90 sec)

> **Demo artifact**: Live n8n canvas + screen-share. Have Slack `#sales-outreach` and your Airtable Outreach table open in adjacent tabs.

## Opening (10s)

> "This turns a new CRM lead into a personalized AI voicemail in about 8 seconds. The script is written fresh per lead by GPT-4o referencing the prospect's role, company, and the specific signal that triggered outreach. Voice is synthesized with ElevenLabs. The MP3 lands in Cloudflare R2 with a public URL, and the SDR team gets a Slack notification with a play button. Full cost telemetry per execution — about 18 cents per voicemail."

## Trigger the live demo (15s)

Run the curl in Terminal:

```bash
curl -X POST "https://nassamn.app.n8n.cloud/webhook/new-lead" -H 'content-type: application/json' \
  -d '{"first_name":"Priya","last_name":"Mehta","email":"priya@northwind.io","company":"Northwind Logistics","title":"VP Operations","signal":"Visited the pricing page 3 times this week and downloaded the routing-algorithm whitepaper","notes":"Their CTO follows me on LinkedIn"}'
```

While it processes, switch to n8n Executions tab — watch nodes flip green left-to-right in real time.

## Walk through the canvas (25s)

> "Webhook receives the payload, Code node normalizes the keys — handles HubSpot, Pipedrive, or generic shapes. Apollo enrichment is wired but optional, soft-fails so it never blocks. Build Prompt is a Code node — I keep prompt construction in JavaScript instead of expressions because it has conditional logic for seniority and industry that'd be unreadable as mustache templates. GPT-4o generates the script at temperature 0.7. Parse + Validate enforces 40-130 word bounds — that's the guard that prevents a runaway generation from triggering a $5 ElevenLabs call. ElevenLabs synthesizes with tuned voice settings — stability 0.45, similarity boost 0.85, style 0.2 — picked for warm sales tone, not defaults. The MP3 goes to Cloudflare R2, Build Record computes per-execution cost from token usage, and the workflow fans out to Slack and Airtable in parallel."

## Switch to Slack tab — point at the message (10s)

> "Here's what hits the SDR's channel — speaker emoji header with the lead's name and role, the script as a Slack blockquote, a clickable Listen link served from R2, the cost, and the word count. Clicking Listen plays it in-browser." *(click → play 3 seconds of the actual voicemail audio)*

## Switch to Airtable tab (8s)

> "Same execution wrote this row to Airtable — every voicemail logged with full telemetry. I can pivot this view to track cost per company size, conversion rate per signal type, or A/B test prompt variations across batches."

## The interesting engineering bits (12s)

> "Three production decisions worth calling out. **One**: the audio path is deterministic from email + received_at, not generated at runtime. That's because n8n's generic S3 node doesn't return the uploaded file's Bucket or Key — only `{success: true}`. So Upload to R2 and Build Record have to reconstruct the same path independently. **Two**: I used Cloudflare R2 over AWS S3 — same S3-compatible API but zero egress fees and a 10 GB free tier, so the storage cost is literally zero. **Three**: voice settings are tuned, not defaults — I A/B'd 12 combinations against a small listener panel for sales authenticity. The losing configurations either sounded like a podcast intro or a TTS reading."

## Close (5s)

> "What I'd ship next: sentiment-gating before TTS — if the script scores low on warmth, regenerate with a system-prompt nudge. And a Whisper transcription loop on the actual call response audio to learn which openers convert."

---

## Likely interview follow-ups & ready answers

**Q: Why GPT-4o instead of Claude or GPT-4o-mini?**
A: GPT-4o gives warmer sales copy than GPT-4o-mini at A/B test — mini's voicemails feel templated, GPT-4o's sound human. Latency difference is under 600ms which doesn't matter for an async outreach pipeline. Claude was the original choice — I switched to OpenAI for project consolidation (Whisper for Project 3 also uses OpenAI, so one credential, one bill, one rate limit). It's a deliberate trade-off, not a default.

**Q: What happens if ElevenLabs throws a 429?**
A: 3 retries with 3-second backoff inside the HTTP node. If all three fail, the error trigger sub-workflow fires and posts to `#automation-alerts` with the failing node + clickable execution link. A production extension would queue the failed lead in Supabase and replay from a scheduled retry workflow.

**Q: How do you handle voice cloning consent and compliance?**
A: The cloned voice is the SDR or founder's own, with consent stored. ElevenLabs requires consent attestation for instant cloning. For inbound voicemails to consumers, the Airtable record includes a `recipient_state` column that gates whether outreach runs at all — TCPA two-party consent varies by state.

**Q: Why Cloudflare R2 over AWS S3?**
A: Three reasons. (1) Cost — R2 has zero egress fees, AWS charges $0.09/GB. For a public audio CDN this matters at scale. (2) Simpler setup — no IAM roles, no bucket policies, just an API key and Force Path Style ON. (3) The n8n "S3" credential type (not "AWS") plays cleanly with R2's endpoint override; the regular AWS credential doesn't expose Custom Endpoints.

**Q: How would you scale this to 10,000 leads a day?**
A: Three changes. (1) Replace the synchronous webhook with a queue — leads land in Supabase, a scheduled trigger drains in batches of 50 with ElevenLabs concurrency limits respected. (2) Use OpenAI's prompt caching — automatic on prompts > 1024 tokens for repeat calls within an hour, drops the system-prompt cost to near zero. (3) Route obvious low-intent leads to GPT-4o-mini instead of full GPT-4o — saves ~70% on LLM spend with negligible quality loss on cold leads.

**Q: What was the trickiest bug?**
A: The R2 Listen link kept 404ing even though the file was clearly uploading. Turned out the n8n S3 node only returns `{success: true}` — no Bucket or Key — so my Build Record code couldn't construct the URL from the upstream output. I had two paths in the workflow generating MP3 filenames using `$now`, which evaluates per-node — so Upload to R2 wrote to `2026-05-31-114911.mp3` while Build Record reconstructed `20260531xxxxxx.mp3` with whatever timestamp it computed milliseconds later. Fixed by switching both nodes to derive the path from `lead.received_at` (set once in Normalize Lead at the start of the execution) — single source of truth, both nodes compute identical paths, no race.
