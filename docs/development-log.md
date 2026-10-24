# Development log — October 24, 2026

## User-provided direction

- Build Gen Academy Project 3F with LangChain/LangGraph.
- Due tomorrow; prioritize orchestration and a functional demo today.
- Browser voice; Anthropic and ElevenLabs keys available to the user.
- Fictional company, five routine scenarios plus one dedicated human escalation.
- Local SQLite tickets and a reviewer screen; local hosting is sufficient.
- “Please go ahead with implementation.”

## Implementation decisions

- Empty repository: created a Python/FastAPI application and buildless browser interface.
- Selected push-to-talk ElevenLabs speech APIs instead of a hosted conversational agent to keep graph orchestration local and avoid a public webhook/tunnel dependency.
- Added four specialized Claude nodes with distinct prompts and responsibilities.
- Kept runbook progression, approval gates, retries, and outcome fields in deterministic code.
- Added scripted offline interpretation for tests; mode is visible in the interface.
- Used durable SQLite checkpoints with `interrupt()` and `Command(resume=...)` for human decisions.
- Created a small synthetic directory and six runbooks, with LangChain tools for lookup.

## Observed test-driven iteration

Initial workflow test run: 9 passed, 5 failed. The five routine resolution cases failed because a substring match for “no” also matched “now.” Replaced negative substring matching with word-boundary matching. Also allowed the offline interpreter to use the latest employee ID when the caller corrects an earlier value.

Further validation results are recorded in the implementation handoff; update this log after live API rehearsal. Do not present unrun live checks as completed.

## Scope limits retained deliberately

No actual account resets, access grants, phone-number calling, external ticketing service, production reviewer authentication, vector database, continuous duplex audio, or public deployment. The QA report describes simulated verification as a record match rather than secure authentication.

## Completed automated verification

- 23 workflow and HTTP API tests passed.
- Chromium browser walkthrough passed: routine resolution, human approval, failed-ticket recovery, 390px mobile layout, fake-device microphone recording, and text fallback after a mocked transcription failure. No JavaScript errors were observed.
- Desktop and mobile screenshots were inspected.
- JavaScript syntax, Python compilation, and Git ignore rules for credentials/runtime databases were checked.
- Browser test selectors were narrowed to the visible tab after hidden duplicate labels caused test-only failures.
- Live Claude inference and ElevenLabs transcription/playback remain unverified until the local API keys are populated and a live rehearsal is performed.

## Voice-capture troubleshooting

After a reported empty-transcript error, a short generated speech sample was sent through the running local speech and transcription endpoints. Both returned HTTP 200 and the expected transcript. This verified the configured live ElevenLabs path for that sample, but not the user's physical microphone. Added input-device selection, a live level meter, and local playback of the last recording to distinguish silence/input selection from provider errors. Uploads now preserve the MediaRecorder MIME type and use a matching filename extension. Added regression tests for codec parameters and empty-transcript guidance. The API/workflow suite now has 25 passing tests.
