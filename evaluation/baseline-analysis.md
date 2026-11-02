# Live baseline analysis — November 1, 2026

Source: `results/baseline.json`. Model: `claude-haiku-4-5-20251001`.
All 40 labels are APPROVED in the current dataset. Dataset and agent hashes match the recorded run, so the evidence corresponds to the reviewed cases and current implementation. The generic limitations text in the run file still mentions proposed labels; that boilerplate does not reflect the current approval status.

## Results

| Metric | Baseline | Pass bar | Result |
| --- | --- | --- | --- |
| Overall case pass rate | 38/40 (95%) | Descriptive, no separate gate | 2 failed |
| Outcome correctness | 36/37 (97.30%) | ≥90% | PASS |
| Trajectory correctness | 37/39 (94.87%) | ≥95% | FAIL |
| Listed safety checks | 36/36 (100%) | 100% | PASS |
| QA evidence-field consistency | 27/27 (100%) | ≥95% | PASS |
| Backend workflow-action p95 | 9.87 seconds | ≤25 seconds | PASS |

The latency denominator is 90 workflow actions. It excludes human waiting and the two mocked voice API cases. Total timed case execution was approximately 368.48 seconds. There are 38 workflow cases and 2 mocked voice API contract cases; passing this suite does not establish actual microphone/STT quality, broad security, or narrative faithfulness.

## Scored failure 1: E06 — premature printer escalation

**Expected:** Ask the three approved printer troubleshooting questions, then create one human handoff if all fail.

**Observed:** The first two questions were delivered. After the caller's second “Still not working,” the workflow escalated with reason “Caller requested a human.” The caller had not requested a human. The next scripted user message was rejected with ValueError because the session was already pending review.

**Cause:** The state transition is consistent with the support interpreter returning intent `human`; the raw structured model response is not saved, so that inference comes from the executed code branch and recorded reason. The workflow trusts this classification without evidence of an explicit caller request. Rejecting another message after escalation is the secondary symptom, not the main defect.

**Impact:** One approved troubleshooting step was skipped; the ticket's stated escalation reason is inaccurate. The final ticket/outcome checks passed, but the trajectory failed. Do not simply remove the exception check or mark the whole case successful because a ticket exists.

## Scored failure 2: E11 — category correction ignored

**Expected:** After “Correction: Wi-Fi and websites work. Only my VPN will not connect,” select `vpn`, reset step to 0, and remain active.

**Observed:** Category stayed `wifi`, step advanced to 1, and the assistant told the caller to toggle Wi-Fi and retry a website.

**Cause:** `support()` retains any known stored category: `state['category'] if state['category'] != 'unknown' else info['category']`. Even a correct new classification cannot override a known category. The run does not retain the raw new classification, so it does not establish whether Claude identified VPN correctly on this turn.

**Impact:** The caller receives troubleshooting for the wrong issue. Both category/outcome and trajectory assertions fail.

## Additional qualitative findings — not changes to the baseline score

**QA narrative in E06:** The report correctly notices the unsupported human-request reason. However, it also claims the caller ended the session and describes two identical troubleshooting recommendations. The recorded sequence contains no end operation and shows two different questions. Structured QA fields passing 100% does not prove that its prose is faithful.

**E12 evaluator coverage:** The multi-issue case passed because category stayed unknown, step stayed -1, and the session stayed active. The actual response was a generic list of supported categories, not a direct “Which issue should we address first?” question. The current assertions therefore only partially verify the intended behavior. Record this in human output review. Do not change the frozen assertions during the baseline/improved comparison; stronger assertions require a separate supplemental evaluation or a new dataset version and rebaseline.

**Offline findings did not all reproduce:** E04 (identity correction), E05 (descriptive yes), and E12 passed the live code checks. Do not present their scripted failures as live Claude failures. E11 reproduced; E06 is a newly observed live failure.

## Four proposed changes

1. **Category corrections:** Add an explicit correction signal to interpretation and let a confirmed new category replace the stored one. Reset its runbook step and clarification counter. Primary target: E11.
2. **Human-request evidence:** Distinguish “step failed” from “please get a person.” Require explicit evidence for caller-requested escalation and add negative examples such as “Still not working.” Log the interpreted intent and escalation trigger. Primary target: E06; regression check: E08 must still escalate promptly.
3. **Grounded QA prose:** Require statements to be supported by transcript/event evidence; supply clear call-ended status and synthetic-environment context. Prohibit inferring session closure, duplicate steps, or completed actions. Assess narrative improvement separately through human review.
4. **Multi-issue clarification:** Ask which reported issue to address first instead of repeating the generic category list. Preserve the current E12 assertions and record the wording improvement in human review; stronger semantic tests belong in a supplemental suite.

If only the two scored failures improve with no regressions, the theoretical ceiling is 40/40 overall, 37/37 outcome, and 39/39 trajectory. That would mean +5 percentage points overall, +2.70 points outcome, and +5.13 points trajectory. These are conditional targets, not measured improvements.

## Next evaluation

Preserve the baseline and reviewed dataset. Implement the changes, test regressions, and run the same live improved evaluation. Compare exact denominators and latency; inspect all changed and failing cases. This is one stochastic run, so a single better result does not establish repeatable reliability. Keep extra repetitions separate from the submitted paired comparison if used.

No agent code, golden labels, or baseline scores were changed during this analysis.
