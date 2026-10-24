# Demo recording — target 4 minutes 30 seconds

## Before recording

- Add both API keys to `.env` and restart the server. Confirm the Claude label and test microphone permissions and spoken playback.
- Use `http://127.0.0.1:8000`. Do not expose terminal secrets or the `.env` file in the recording.
- Rehearse with the actual APIs. Browser voice is push-to-talk: record, then click Stop & send.
- Prepare the restricted-software request and a ticket-failure example if live API latency makes showing three complete conversations too slow.
- Ensure a human decision includes reviewer name and an explanatory note.

I am Binita Mehta and welcome to Project 3 for the October cohort. I have decided to build the multi-agent IT Support Voice Agent.

## 0:00–0:30 — Introduce the problem

“Northstar IT helps employees resolve common issues and creates a reliable human handoff when automation cannot finish. This is a fictional company with synthetic employee data.”

## 0:30–1:00 — Explain orchestration

Point to the four specialists: intake, support, escalation, QA. Explain that LangGraph owns shared state and routing, Claude interprets requests, ElevenLabs handles speech, and SQLite persists tickets and human-review checkpoints.

## 1:00–2:20 — Live routine call

Start a session. Record: “I’m Maya Chen, NS-1001. My VPN won’t connect.” Answer the first diagnostic question, then explicitly confirm “The VPN works now.” Explain that the device actions are simulated for the demonstration. End the call and show the resolved audit with caller evidence.

## 2:20–3:20 — Human decision

Start a session: “I’m Maya Chen, NS-1001. I need access to restricted analytics software for a customer report.” Show the pending ticket, end the call, open Human review, enter your name and note, then approve. Highlight that it is approved pending fulfillment, not marked resolved.

## 3:20–3:50 — Failure recovery

Show a session started with Ticket creation timeout. Explain the two failed attempts and the honest no-ticket result. Click Retry ticket and show the single resulting ticket. Mention that a pending human-review checkpoint survives a backend restart (covered by the automated test).

## 3:50–4:30 — AI-assisted development and learnings

Show a session report and the passing tests. Explain that AI coding assistance built scaffolding, UI, graph nodes, tests, and documentation; tests caught an offline-parser bug. Describe the main learning: prompts define roles, but code enforces routing, retries, approvals, and truthful outcomes.

Finish with the GitHub/Google Doc links. Keep the recording under five minutes. If voice usage is unavailable, disclose that limitation rather than presenting scripted mode as live AI.
