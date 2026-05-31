# Interview demo script — Voice CRM Assistant (60-90 sec)

> **Demo artifact**: Live Slack channel + n8n canvas. Have your phone or laptop mic ready to record a voice note in Slack.

## Opening (10s)

> "This is a full conversational voice loop. I drop a voice note in Slack, and about 6 seconds later the bot replies with synthesized audio confirming a CRM action — create contact, log activity, query, or just answer a question. Whisper transcribes, GPT-4o with function calling routes to the right action, Supabase persists, ElevenLabs speaks back."

## Live demo — record voice notes in sequence (30s)

This is the killer moment. Record three voice notes back-to-back, with the bot replies playing between each:

**1.** *(record in Slack)* **"Create a contact for Priya Mehta, VP Operations at Northwind Logistics."**
   *(wait for bot's audio reply — should arrive in ~6s)*

**2.** *(record)* **"Log a call with her about Q3 routing pricing."**
   *(wait for reply)*

> "Notice it resolved 'her' to Priya — that's the short-term memory loop. The last 10 conversation turns per user are loaded from Supabase and threaded into GPT-4o's messages array on every call."

**3.** *(record)* **"Who do I know at Northwind?"**
   *(wait for reply)*

> "Same memory, third tool — query_contact. Reads from Supabase, the spoken reply summarizes the match."

## Architecture highlight — function calling (20s)

> "The interesting design call is OpenAI function calling instead of single-shot intent classification. Three tools defined — create_contact, log_activity, query_contact — each with strict JSON Schema parameters enforced at the API boundary. GPT-4o can also return a text-only reply if the user just asks a question. The Switch node downstream routes by tool name. Way more robust than 'parse JSON intent' because the schema validation happens at OpenAI's edge, not in my regex parser."

## Production engineering — the gotchas I solved (20s)

> "Three real bugs hit during build, worth mentioning because they're the kind of thing tutorials don't warn you about. **One**: Slack's `file_shared` event has no mime type in the payload — I had to remove the upfront audio filter because it was rejecting every event. **Two**: Slack fires `file_shared` 2-5 times per single voice note across the file lifecycle. Idempotency is needed by file_id to avoid duplicate Supabase rows. **Three**: OpenAI returns `tool_calls[].function.arguments` as a JSON-encoded string, not an object — easy to miss when you've been working with Anthropic where it's pre-parsed. Each of those bugs is a one-line fix once you know, but together they're the difference between a tutorial and a working system."

## Close (10s)

> "What I'd ship next: pgvector long-term memory so it can answer 'who did I talk to at Initech six months ago'; multi-tool calls in one turn — 'create the contact AND log the activity'; and a phone number via Twilio Media Streams. The Slack transport is interchangeable — Whisper + GPT-4o + Supabase + ElevenLabs is the conversational core. Same architecture, swap inbound for a phone call, you have an AI receptionist."

---

## Likely interview follow-ups & ready answers

**Q: How do you handle Slack's "respond in 3 seconds or we retry" rule?**
A: The `Respond: Accepted` node fires immediately after the IF routing, before any of the long-running work (Whisper, LLM, ElevenLabs). The rest of the pipeline runs async from Slack's perspective. If I let the response wait for the full pipeline, Slack would retry after 3 seconds and I'd be paying for duplicate Whisper + LLM calls on the same audio.

**Q: What's your signature verification story for Slack?**
A: Not in this portfolio piece — would add it for production. Slack sends an `X-Slack-Signature` HMAC header on every request, computed from your signing secret. A 10-line Code node at the top of the workflow verifies the signature before doing any work. Without it, anyone with your webhook URL can forge events. Also worth adding: per-user allowlist and per-user rate limiting, both ~5-line additions in the Route Slack Event node.

**Q: Why Supabase over Airtable for this one?**
A: Three reasons. (1) Row-level security — Supabase RLS lets me enforce per-user data isolation server-side; Airtable would need application-layer checks. (2) Full SQL — the `query_contact` tool uses `ilike` for name fuzzy match, which would be a brittle Airtable formula. (3) Real-time subscriptions — a v2 extension has the workflow react to manual CRM edits and proactively voice-notify the user; that's not Airtable's strength.

**Q: Tell me about a bug that was hard to debug.**
A: The "Audio too short" errors that started appearing intermittently. Whisper would reject the file with `duration: 0.74s` even though the voice note was clearly 6 seconds long. Eventually figured out Slack fires `file_shared` BEFORE the upload completes — the first event has a tiny preview file, and only the third or fourth event has the actual finished upload. Without idempotency by file_id, all of them get processed; the early ones error out, the late one succeeds. Once I understood the lifecycle, the fix was obvious — but the symptom looked like a Whisper bug.

**Q: How would this look as a phone agent (the JD specifically asks)?**
A: Swap the Slack webhook trigger for Twilio's Voice → Stream endpoint. Use Twilio Media Streams for bidirectional low-latency audio. Whisper becomes a streaming Whisper call (or Deepgram for sub-300ms STT). ElevenLabs has a streaming TTS endpoint that returns chunks as generated — wire those back through the same Twilio Media Stream. The GPT-4o function calling + Supabase + tool execution core stays exactly the same. That's the architectural win — designing the conversational core as transport-agnostic from day one.

**Q: What's your cost story?**
A: ~$0.04 per turn — 25 turns per dollar. Breakdown: Whisper $0.0008 (~$0.006/min × 8s), GPT-4o ~$0.005, ElevenLabs ~$0.036 for short replies. The dominant cost is TTS — for a power user doing 50 actions a day that's ~$2/day. Memory capped at 10 turns prevents unbounded context growth at the LLM step.
