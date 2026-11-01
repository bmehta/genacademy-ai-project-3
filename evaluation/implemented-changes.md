# Implemented improvements — November 1, 2026

The changes below were made after the live baseline analysis. Frozen cases and expected labels were not edited. Baseline source files are archived in `results/baseline-source/`.

| Change | Baseline evidence | Implementation | Verification |
| --- | --- | --- | --- |
| Explicit category correction | E11 kept Wi-Fi after caller corrected the issue to VPN | Interpretation includes correction flag and verbatim evidence. Workflow accepts a supported, different category only with evidence in the current caller message, resets the step, and starts the new runbook. Access requests still require approval. | Same E11 golden case; additional tests for incidental category changes and correction to restricted access. |
| Evidence for human requests | E06 escalated after “Still not working,” calling it a human request | Prompt distinguishes failed steps from explicit requests. Workflow validates a current-message evidence quote containing a person/escalation reference; unsupported human classification becomes failed/question. Raw and effective classifications are logged. | Tests inject incorrect and fabricated human-request evidence; genuine requests still escalate. |
| Grounded QA prose | E06 narrative claimed call closure and repeated instructions without evidence | QA receives explicit closure state, the actual runbook questions asked, numbered messages/events, synthetic-environment context, and escalation trigger. Prompt forbids inferred closure or completed actions. | Evidence-packet tests verify two distinct steps and correct closure before/after ending a call; live prose reviewed separately. |
| Focus question for multiple issues | E12 passed state checks but asked a generic category list | Interpretation lists multiple unresolved issues. Workflow asks which issue to address first, saves pending issues, and starts the selected runbook after clarification. Repeated ambiguity eventually escalates. | Regression test covers the focus question and caller selection; frozen E12 score unchanged. |

40 automated tests passed before the final live improved run. These tests cover behavior and input evidence; they do not guarantee that every model-generated sentence is faithful. Read `results/comparison.json` and `narrative-review.md` for measured and qualitative results once the run completes.

The changes were evaluated as a bundle. Do not assign the aggregate lift to an individual prompt edit without an ablation experiment. A single paired evaluation also does not establish repeatability.

## Observed intermediate regression

The first improved live run passed 39/40 cases, fixing E06 and E11 but regressing E10. The model placed classification reasoning in `justification`, and a truthy string triggered an access ticket without the required business purpose. This attempt is preserved in `results/improved-attempt1.json`.

The subsequent revision gives the justification field an explicit purpose-only definition and requires its value to be a verbatim quote from caller messages. Non-caller model explanations are discarded. QA evidence now excludes derived interpretation events, preventing the model from treating `human_request_validated` as identity validation. QA fields also specify a brief summary and separate findings/follow-up lists. Two new regression tests cover these issues. The final full run is stored in `results/improved.json`.
