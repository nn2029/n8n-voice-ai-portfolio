# Interview demo script — Podcast Factory (60-90 sec)

**Open** (10s):
> "This is a daily AI podcast generator. 6am cron, scrapes three feeds, ranks the top three stories, Claude writes a 5-minute two-host script, ElevenLabs synthesizes each speaker with different voice tunings, ffmpeg stitches it, uploads to S3, posts to Slack. Costs about $1.20 per episode."

**Multi-voice tuning** (25s) — the key demo moment:
> "The interesting bit is the per-persona voice tuning. Two hosts: Alex is curious and energetic, Jordan is the dry expert. They get different ElevenLabs settings — Alex runs stability 0.35 with style 0.45, Jordan runs stability 0.65 with style 0.15. Higher stability for Jordan because dry delivery needs to sound steady; higher style for Alex because curiosity needs expressive rising inflection. The settings live in a single Code node lookup, so adding a third host is a five-line change." *(play 10-second clip showing both voices)*

**Architectural decisions** (20s):
> "Two design calls worth highlighting. One: one Claude call for all stories, not one per story — gives the hosts cohesion so they can reference earlier segments, and after I add prompt caching the system prompt becomes effectively free. Two: ffmpeg stream-copy concatenation instead of re-encoding — ElevenLabs always returns 44.1kHz mono so the codec/sample-rate match means `-c copy` is lossless and 50x faster than re-encoding."

**n8n native primitives** (15s):
> "I deliberately used n8n's first-party Write Binary File, Execute Command, and Read Binary File nodes for the stitching instead of inline `require('fs')` in a Code node. Two reasons — it works on n8n Cloud which sandboxes Node built-ins, and it shows the binary item handling more clearly on the canvas. Same outcome, more portable."

**Close** (10s):
> "What I'd ship next: ad insertion at fixed timecodes via ffmpeg overlay; a real podcast RSS feed served from a Cloudflare Worker so this is subscribable in Apple Podcasts; and a feedback loop where listener skip-points get fed back into the ranking algorithm."

---

## Likely interview follow-ups

**Q: How do you handle prompt drift on Claude returning malformed JSON?**
A: The `Parse + Validate Turns` node uses a regex match for the JSON array shape (`/\[\s*\{[\s\S]*\}\s*\]/`) instead of `JSON.parse` on the raw output — Claude sometimes prefixes with "Here's the script:" which would break a strict parse. Then per-turn validation rejects invalid speakers and length-bombs. If the output is genuinely broken, the error trigger fires and I get a Slack alert with the raw output for prompt tweaking. In production I'd add one retry with a system-prompt nudge ("Reminder: output ONLY the JSON array") before erroring.

**Q: ElevenLabs Creator tier caps concurrent requests at 2. How do you handle that with a 12-turn episode?**
A: The HTTP node's `batching` option — set to `batchSize: 2, batchInterval: 1000`. n8n processes items in waves of 2 with a 1-second gap. At 12 turns that's 6 waves, ~30 seconds for synthesis — fine for a daily batch job. If I needed lower latency I'd upgrade to the Pro tier (10 concurrent) and drop the batching.

**Q: What if one segment fails synthesis?**
A: Three retries with 4-second backoff inside the HTTP node. After that the error trigger fires and the whole episode rolls back — we don't ship a podcast with a missing turn. Better to skip a day than ship a glitched episode. A more sophisticated version would mark the failed turn and regenerate the surrounding pair through Claude so the conversation flows around the gap.

**Q: How would you A/B test ElevenLabs settings systematically?**
A: I'd refactor `Apply Persona Settings` to read settings from a Supabase config table keyed by `(persona, experiment_variant)`. The workflow takes a `variant` input, the Slack post includes which variant was used, and a separate workflow polls Slack reactions (`:thumbsup:` / `:thumbsdown:`) on each episode to score the variants. After 30 episodes you have a real signal.

**Q: Why RSS instead of a more sophisticated trend source?**
A: Portability — RSS works everywhere with no auth. In a real production version I'd add the Reddit API, Hacker News Firehose, and the ArXiv daily LLM listing. The `Fan Out Sources` node is designed to accept any source that yields items with `title`, `link`, `summary`, `pubDate` — you'd just add a normalizer per source.
