# Portfolio submission artifacts

What to capture, in what format, for what purpose. Do this BEFORE you submit the application — interviewers respond to evidence, not claims.

---

## Tier 1 — must-have (do these first)

### A1 — Slack message screenshot from Project 1

**What**: The `#sales-outreach` channel showing a single AI-generated voicemail post with:
- Speaker emoji header + lead name + company + role
- The full script as a Slack blockquote
- The 🎧 Listen link (must be clickable, not "pending-upload")
- 💰 cost + 📝 word count footer

**Why it matters**: Single image proves the entire pipeline ran — LLM generated personalized copy, ElevenLabs synthesized, R2 hosted, Slack notified. One image, four products, real cost.

**How**: Run the curl with the Priya Mehta payload → wait 8s → switch to Slack → screenshot the message.

**Where to use it**: Top of your cover letter / portfolio page. First thing the hiring manager sees.

### A2 — Airtable Outreach row screenshot

**What**: The Airtable record-detail view (click any row to expand it) showing all 11 fields populated:
Lead, Email, Company, Role, Script, Audio URL, Tokens In, Tokens Out, Cost (USD), Generated At, Status.

**Why it matters**: Proves you understand observability and audit logging. Most automation tutorials skip this; production systems require it.

**How**: From the same execution as A1, open Airtable → Outreach table → click the new row → screenshot the expanded view.

### A3 — n8n execution canvas, Project 1, all green

**What**: The execution view (not the editor view) of a successful Project 1 run, zoomed out so all 14 nodes are visible with green borders.

**Why it matters**: Demonstrates that the system actually runs end-to-end. Recruiters often can't read code but they CAN see green vs red.

**How**: Trigger one run, open Executions → click it → zoom out (the magnifying-glass icons at bottom) → screenshot.

### A4 — Project 3 Slack conversation screenshot

**What**: `#sales-outreach` or wherever you tested Project 3, showing:
- Your voice note (the user message)
- The bot's audio reply right below it
- The `Action: create_contact` label visible

**Why it matters**: Single screenshot of an AI agent having a voice conversation with you and taking action in a real database. This is the "wow" artifact.

**How**: Drop voice note → wait for bot reply → screenshot both messages.

### A5 — Supabase contacts table row from Project 3

**What**: Table Editor → contacts → showing the row(s) the AI created from your voice notes (Maria Lopez, Priya Mehta, etc.).

**Why it matters**: Closes the loop on A4 — proves the spoken action actually persisted to a real database, not just confirmed in chat.

---

## Tier 2 — strongly recommended

### B1 — 60-second screen recording of Project 3 in action

**What**: Loom or QuickTime screen + audio recording (export as MP4):
- 0:00-0:10 — Brief voice intro: "This is my n8n + ElevenLabs voice CRM assistant. I'll drop a voice note in Slack and it'll create a contact in Supabase and reply with synthesized audio."
- 0:10-0:25 — Record voice note #1 in Slack on camera
- 0:25-0:35 — Bot reply audio plays (real audio captured)
- 0:35-0:50 — Switch to Supabase, point at the new row
- 0:50-0:60 — Switch to n8n executions, all green canvas

**Why it matters**: A 60s video proves you built and shipped this, not just imported a JSON file. Interviewers share these internally with their teams.

**How**: Loom free tier is enough. Practice once first; do the real take in one go.

### B2 — 30-second audio sample comparison (Project 1)

**What**: Two MP3 clips played back-to-back:
- Same script synthesized with ElevenLabs DEFAULT voice settings (stability 0.5, similarity_boost 0.75, style 0.0)
- Same script with your tuned settings (stability 0.45, similarity_boost 0.85, style 0.20)

**Why it matters**: Concrete proof you can hear and articulate the difference voice tuning makes. The JD specifically asks "stability, clarity, style exaggeration" — you can demonstrate it.

**How**: Run two ElevenLabs API calls manually (or duplicate the workflow with different settings) → save both MP3s → upload to your portfolio.

### B3 — n8n canvas screenshots of Project 3 zoomed sections

Three crops of the Project 3 canvas:
- **Crop 1**: Slack Event → Route → IF gates (the routing/verification logic)
- **Crop 2**: Whisper → Validate → Supabase: Load Context → Build Request → OpenAI Function Calling (the AI core)
- **Crop 3**: Switch → tool branches → Build Spoken Reply → ElevenLabs → Slack Upload (the action + reply)

**Why it matters**: Lets you walk through the architecture in a portfolio post or PDF without making the reader squint at a wide-angle canvas screenshot.

---

## Tier 3 — bonus (if you have time)

### C1 — Cost dashboard screenshot

Pivot view in Airtable: Cost (USD) summed by Company, or by Day. Even better: a small chart showing total spend over your test runs.

**Why it matters**: Demonstrates you're a senior automator who thinks in cost-per-event, not just "does it work."

### C2 — Architecture diagram (each project)

Hand-drawn-feel diagram (use Excalidraw, free) showing the data flow. The ASCII diagrams in the READMEs are good for engineers; a clean visual diagram is better for non-technical hiring managers.

### C3 — Project 2 partial demo

Even with Project 2 not fully wired, you can demo the script-generation step in isolation:
- Run the workflow up to the OpenAI: Generate Script node
- Capture the output JSON (the structured podcast script)
- Manually paste the first speaker's first turn into ElevenLabs UI with Alex's tuning
- Capture the resulting audio
- Repeat with Jordan's tuning

This produces a "what it would sound like" sample without needing the full workflow live.

---

## How to package for the job application

### Option 1 — Cover letter + linked portfolio (recommended)

Cover letter: 3 short paragraphs.
1. "I built three n8n workflows demonstrating the exact stack you list — OpenAI orchestration, ElevenLabs voice synthesis with tuned settings, full CRM/Supabase integration. Here's one of them running end-to-end: [link to Loom of A4]."
2. "What separated this from a tutorial follow-along were the production gotchas — Slack's `file_shared` fires multiple times per voice note, n8n's S3 node returns only `{success: true}`, OpenAI's function calling returns argument strings not objects. Each one's documented in the project READMEs with the fix."
3. "Full repo + READMEs + demo scripts here: [github link]. Happy to walk through any of it live."

Portfolio page (GitHub repo or simple HTML):
- A1 (Slack screenshot) hero image
- 3 project cards, each linking to its README
- B1 (Loom) embedded
- A2, A3, A5 screenshots inline

### Option 2 — PDF case study

If the company asks for a portfolio doc:
- Page 1: All three project cards (A1, A4 screenshots as proof)
- Pages 2-4: One page per project — architecture diagram, key code snippet, cost table
- Page 5: "Production gotchas I solved" with the bullet list from the top-level README
- Page 6: Roadmap / what's next

### Option 3 — Live demo invitation

If they invite you to interview, lead with: "I can demo any of these live during the call — happy to share screen and run a voice note through the CRM assistant in real time." Then have your laptop set up with Slack + n8n + Supabase tabs ready before the call.

---

## What NOT to include

- Don't share workflow JSONs publicly with credentials. Sanitize first.
- Don't share the actual ElevenLabs voice ID if it's a clone of a specific person (privacy/consent).
- Don't claim Project 2 is "complete" if it's only designed — say "designed, JSON ready to import" instead. Honesty beats inflation, and you can demo the partial via C3.
- Don't include the failed-execution screenshots from your build journey. Those are useful for YOUR notes, not for submission.
