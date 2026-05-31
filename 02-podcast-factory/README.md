# Project 2 — AI Podcast / Audio Newsletter Factory

> Every morning at 6am, this workflow ranks the day's top AI stories across three feeds, writes a 5-minute two-host podcast script with **GPT-4o in JSON mode**, synthesizes each speaker's lines through ElevenLabs with **per-persona voice tuning**, stitches the segments via byte-level MP3 concatenation, and publishes the episode to S3 + Slack. Fully unattended.

## What it proves

- **Multi-voice ElevenLabs depth** — two distinct personas (Alex + Jordan), each with deliberately different `stability` / `similarity_boost` / `style` settings tuned to their character. This is the specific kind of "fine-tune ElevenLabs settings" work the JD calls out.
- **Complex content pipeline** — multi-source RSS ingestion, keyword scoring, recency boosting, dedupe.
- **Binary handling in n8n** — fan-out audio synthesis, ordered re-aggregation, byte-level MP3 stitching in a single Code node via `Buffer.concat` + n8n's first-party binary helpers. Works on n8n Cloud, no `Execute Command` or filesystem needed — output is byte-identical to ffmpeg `-c copy` stream-copy.
- **JSON-structured LLM output via OpenAI JSON mode** — `response_format: { type: 'json_object' }` guarantees parseable output at the API boundary, eliminating the regex-extraction step required when using free-form generation. Per-turn validation runs before any TTS spend is committed.
- **Scheduled + idempotent** — cron-triggered, tmp-file cleanup, error sub-workflow.

## Architecture

```
[Cron: 6am daily]
        │
        ▼
   ┌──────────┐
   │  Config  │  ◀── feeds, topic filter, max_stories
   └──────────┘
        │
        ▼
   ┌────────────────┐
   │ Fan Out Sources│
   └────────────────┘
        │
        ▼
   ┌──────────┐
   │ Read RSS │  ◀── pulls all configured feeds in parallel
   └──────────┘
        │
        ▼
   ┌─────────────────┐
   │ Rank Top Stories│  ◀── keyword hits × 3 + recency boost
   └─────────────────┘
        │
        ▼
   ┌──────────────┐
   │Bundle Stories│  ◀── single GPT-4o call for coherent multi-story script
   └──────────────┘
        │
        ▼
   ┌─────────────────────┐
   │ OpenAI: Generate    │  ◀── strict JSON { turns: [{speaker, text}, ...] } via JSON mode
   └─────────────────────┘
        │
        ▼
   ┌──────────────────────┐
   │Parse + Validate Turns│  ◀── per-turn validation, fan-out to N items
   └──────────────────────┘
        │
        ▼
   ┌────────────────────────┐
   │ Apply Persona Settings │  ◀── voice_id + voice_settings lookup per speaker
   └────────────────────────┘
        │
        ▼
   ┌────────────────────────────┐
   │ ElevenLabs: Synthesize Turn│  ◀── batched 2-at-a-time (Creator tier limit)
   └────────────────────────────┘
        │
        ▼
   ┌─────────────────────┐
   │ Order Audio Segments│  ◀── defensive sort by turn_index
   └─────────────────────┘
        │
        ▼
   ┌────────────────────────────┐
   │ Stitch Audio (Buffer.concat)│  ◀── single Code node, MP3 byte concat, no ffmpeg/fs
   └────────────────────────────┘
        │
        ▼
   ┌────────────────────┐
   │ Upload Episode S3  │
   └────────────────────┘
        │
        ▼
   ┌──────────────────────┐
   │Build Episode Metadata│
   └──────────────────────┘
        │
        ▼
   ┌────────────────────┐
   │ Slack: Announce    │
   └────────────────────┘

   [Error Trigger] ──▶ [#automation-alerts Slack]
```

## Persona tuning — the heart of this project

Two personas, two tuning profiles. Picked from listening tests, not defaults:

| Setting | **Alex** (curious, energetic) | **Jordan** (dry expert) | Why the difference |
|---------|-------------------------------|--------------------------|---------------------|
| `stability` | **0.35** | **0.65** | Alex needs variation — naive questions have natural rising inflection. Jordan needs steadiness — analyst credibility is monotonal-ish. |
| `similarity_boost` | 0.80 | 0.85 | Both high. Jordan slightly higher because the dry delivery exposes any drift more obviously. |
| `style` | **0.45** | **0.15** | Alex needs expressiveness ("wait, but…"). Jordan's deadpan dies if style goes above 0.2. |
| `use_speaker_boost` | true | true | +5% latency for measurable timbre match on both. |
| Voice ID | a brighter younger voice | a lower measured voice | Picked from ElevenLabs library or cloned. |

The lookup lives in a single Code node (`Apply Persona Settings`) — adding a third host is a five-line change.

> **Why a *lookup table* instead of an `if`/`switch` per-call?** Maintainability. When you tune Alex's stability you want to change one number in one place, not hunt through three downstream nodes. Same reason you don't inline magic numbers in production code.

## Why one GPT-4o call for all stories (not one per story)

Two reasons:

1. **Cohesion.** The hosts can reference earlier stories ("kind of like that funding round we just talked about") — impossible if each story is generated in isolation.
2. **Cost.** The system prompt is ~400 tokens. Sending it once instead of N times saves ~400 × (N-1) input tokens per episode. OpenAI's prompt caching (automatic on prompts > 1024 tokens for repeat calls within an hour) makes the system prompt effectively free on subsequent episodes — no code change required.

The trade-off is a longer single call (~30-45s), but it runs once per day at 6am — latency isn't a constraint.

## Why byte-level MP3 concat instead of ffmpeg

ElevenLabs always returns 44.1kHz mono MP3. MP3 is a stream of self-contained frames — when all inputs share codec + sample rate + channel count, naive byte concatenation produces a valid file every player handles correctly. The output is **byte-identical** to ffmpeg's `-c copy` (stream-copy) concat.

Doing the same operation as a single `Buffer.concat` call inside an n8n Code node gives us:
- **n8n Cloud compatibility** — no `Execute Command` node, no filesystem access, no native binaries.
- **Simpler workflow** — one node instead of 5+ for the stitching chain.
- **Zero infra** — no ffmpeg container to maintain, no temp-file cleanup.

If you ever switch to `eleven_multilingual_v2` with different sample rates per voice, byte concat starts producing playback artifacts at the seams. The fix is to re-encode through a proper service — either a self-hosted ffmpeg container or a hosted audio API like fal.ai. The architecture is one Code node swap, not a rewrite.

## Cost per episode

| Component | Per episode (≈ 800 words, ~12 turns) |
|-----------|--------------------------------------|
| OpenAI GPT-4o (~1500 in, ~1200 out) | ~$0.016 |
| ElevenLabs turbo_v2_5 (~4000 chars) | ~$1.20 |
| S3 storage + bandwidth | <$0.005 |
| **Total** | **≈ $1.23 per episode** |

> ~$37/month for a daily AI-generated podcast. A human podcast editor charges that per minute.

Optimizations baked in:
- `turbo_v2_5` is 50% the cost of `multilingual_v2` for ~identical English quality.
- Single GPT-4o call (vs per-story) saves ~$0.012/episode after caching.
- Batched ElevenLabs concurrency = 2 → stays inside the Creator tier without paid-tier upgrade.

## Test it

Manual run from the n8n UI works fine — just hit "Execute Workflow" on the trigger node. Expected output:

- One MP3 in S3 at `s3://YOUR_BUCKET/podcast/signal-boost-YYYY-MM-DD.mp3`
- One Slack post in `#podcast` with the audio link, duration, and transcript preview
- Tmp files cleaned up automatically

## Setup checklist

- [ ] n8n ≥ 1.50, import `workflow.json`
- [ ] OpenAI credential (n8n Cloud built-in "OpenAi API" credential type)
- [ ] ElevenLabs credential
- [ ] Two voice IDs — cloned or from ElevenLabs library — set as `ELEVENLABS_VOICE_ALEX` and `ELEVENLABS_VOICE_JORDAN` env vars
- [ ] AWS S3 bucket, `S3_BUCKET` env var
- [ ] Slack OAuth credential
- [ ] Edit the `Config` node's `sources` field to point at the RSS feeds you actually want
- [ ] Activate workflow
