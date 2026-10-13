# n8n voice and AI automation workflows

Three n8n workflows that combine a language model, speech and ordinary business tools, plus a larger agent platform that runs locally with tests. I built them in 2026 to work through real integration problems: webhooks that fire more than once, model output that has to be checked before it is acted on, and binary audio moving between services.

Everything here is my own work. Nothing in this repository is running for a customer.

## What is in the repository

| Folder | What it does | State |
|---|---|---|
| [`01-voice-sales-outreach`](01-voice-sales-outreach) | A new lead arrives by webhook. The workflow writes a short voicemail script with GPT-4o, checks its length, synthesises it with ElevenLabs, stores the audio, logs the run and posts it to Slack. | Ran on n8n Cloud in May 2026 with test leads. |
| [`02-podcast-factory`](02-podcast-factory) | On a schedule, reads RSS feeds, ranks the stories, has GPT-4o write a two-host script as JSON, synthesises each line with a per-host voice, joins the audio and publishes it. | Designed and built as a workflow file. Not run end to end. |
| [`03-voice-crm-assistant`](03-voice-crm-assistant) | A Slack voice note is transcribed with Whisper. GPT-4o chooses one of three tools (create a contact, log an activity, look someone up), the workflow runs it against Supabase and replies with a spoken confirmation. | Ran on n8n Cloud in May 2026. One recorded run created a contact from a voice note. |
| [`04-production-agent-platform`](04-production-agent-platform) | A FastAPI and Next.js platform: a multi-tenant automation control plane and a voice operations agent, with approvals, replay, audit events and provider fallback. Includes n8n reference workflows. | Runs locally in a deterministic mock mode. Covered by automated tests and CI. Not run under customer traffic. |

Each workflow folder has a `workflow.json` you can import into n8n and a `README.md` covering the architecture, the decisions and the problems found while building it.

## Running a workflow

You need n8n (Cloud or self-hosted, version 1.50 or later) and your own accounts for the services a workflow uses.

1. In n8n, choose Workflows, then Import from File, and pick the folder's `workflow.json`.
2. Create the credentials listed below and select them on each node. The files refer to credentials by name only. No keys are stored in this repository.
3. Publish the workflow and connect its trigger: a webhook for the sales outreach workflow, a Slack event subscription for the CRM assistant, a schedule for the podcast workflow.
4. Send the test input from that folder's README.

| Service | Used by | Notes |
|---|---|---|
| OpenAI | 1, 2, 3 | One credential covers chat completions and Whisper transcription. |
| ElevenLabs | 1, 2, 3 | n8n has no built-in credential type for it, so use Header Auth with the name `xi-api-key`. API access from cloud addresses needs a paid tier. |
| Cloudflare R2 | 1, 2 | Use n8n's S3 credential type, not AWS, with a custom endpoint and Force Path Style on. |
| Slack | 1, 2, 3 | A bot token with `chat:write`, `chat:write.public`, `files:read`, `files:write` and `channels:read`. |
| Airtable | 1 | A personal access token. It needs `schema.bases:read` as well as record access, or n8n's table list stays empty. |
| Supabase | 3 | Three tables, with the SQL in that folder's README. |

The agent platform has its own instructions in [`04-production-agent-platform/README.md`](04-production-agent-platform/README.md). It starts with `docker compose up --build` and needs no paid keys in mock mode.

## Decisions that apply across the workflows

- **The model proposes, the workflow acts.** In the CRM assistant the model can only choose one of three functions with typed arguments. The database write is done by the workflow. In the other two, the script is validated for length and shape before any audio is paid for.
- **One model provider.** All three workflows use OpenAI. An early draft mixed providers. One credential, one bill and one rate limit were easier to operate, and function calling settled it for the CRM assistant.
- **File paths built from data that does not change.** The sales workflow names its audio file from the lead's email and the time the lead was received, not from the current time. Two nodes can then compute the same path independently, which matters because n8n's S3 node does not return the upload location.
- **Voice settings chosen per use.** The sales voice and the assistant voice use different stability and style values, and the two podcast hosts each have their own.
- **Cloudflare R2 for audio.** It speaks the S3 API, has a free tier and charges nothing for downloads.
- **An error workflow on each.** A failed run posts the failing step, the error and a link to the execution in a Slack alerts channel.

## Problems found while building

1. **Slack's `file_shared` event carries no file type.** It contains only a file ID. Filtering for audio in the first node rejected every event. The check has to come after the file details are fetched.
2. **Slack sends `file_shared` several times for one voice note,** as the file moves through recording, upload and sharing. Each one starts a run. The CRM assistant's `workflow.json` does not deduplicate these, so a note can be processed more than once. The fix, a check on the file ID, is described in that folder's README and is not in the file.
3. **n8n's S3 node returns only `{success: true}`.** There is no bucket or key for later nodes to read, so paths have to be reconstructed.
4. **n8n's Supabase node stops the workflow when a query returns no rows.** A first-time user has no history. Turning on Always Output Data fixes the stop, and the next step then has to ignore the empty placeholder row it produces.
5. **OpenAI returns function arguments as a JSON string,** not an object. They have to be parsed, and a parse failure has to be handled.
6. **ElevenLabs blocks its free tier from cloud addresses.** It is easy to mistake for a credentials problem.

## Limits

- None of the workflows is running now. Each needs its own credentials to run again.
- The Slack webhook in the CRM assistant does not verify Slack's request signature.
- The podcast workflow has not been run end to end, so its audio joining is untested against real episodes.
- Costs quoted in the folder READMEs are estimates from published price lists, not measured bills.
- The model's tool schemas use required fields. They do not use OpenAI's strict mode.

## Related write-ups

- [Voice-Driven CRM Assistant](https://www.nassamn.dev/projects/voice-crm-assistant) (folder 03)
- [Multi-tenant AI automation control plane](https://www.nassamn.dev/projects/multi-tenant-ai-automation-control-plane) and [Voice operations agent](https://www.nassamn.dev/projects/voice-operations-agent) (folder 04)
