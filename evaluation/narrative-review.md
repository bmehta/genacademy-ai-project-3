# Supplemental qualitative review — November 1, 2026

This is an assistant review of selected observed outputs, not a human label approval, calibrated LLM-judge score, or change to the frozen numeric rubric. Complete the workbook's human Output review independently.

## E06 — printer failure and QA grounding

- Baseline: prematurely escalated after the second failed step with reason “Caller requested a human.” Its QA summary incorrectly claimed the caller ended and identical steps repeated.
- First improved run: all three questions were asked and escalation correctly followed exhausted steps. The QA output was excessively long, and an unrelated internal validation field also confused H20's QA.
- Final improved run: all three distinct printer questions were delivered. Caller said “Still not working” after each. The escalation reason is “Approved troubleshooting steps exhausted without confirmation.” QA correctly says the call remains open and references M3/M5/M7 as distinct questions.
- **Remaining prose error:** QA says “three runbook lookups,” but E4/E6/E8/E10 are four lookup events. This does not fail the existing structured QA checks. It is evidence that prose faithfulness is not fully solved despite the 100% structured QA score.

## E10 — regression found and corrected

- Baseline: remained active and requested the missing business purpose.
- First improved run: generated explanatory text populated the justification field. The workflow treated this as a supplied purpose and created a ticket early, failing outcome and ticket-count checks.
- Follow-up fix: the schema defines purpose as an exact caller quote; workflow discards text absent from caller messages. Model reasoning is not accepted as a purpose.
- Final response: “Which software do you need, and what business task will you use it for? A reviewer must approve restricted access.” No ticket was created, as expected.

## E11 — category correction

- Baseline kept Wi-Fi and advanced its runbook after the caller explicitly corrected the issue to VPN.
- Final run records the correction evidence, changes category to VPN, and starts step 0. The original frozen checks pass.

## E12 — multiple issues

- Baseline passed the state assertions but asked a generic list of categories.
- Final response: “You mentioned multiple issues: VPN won't connect, Printer offline. Which issue would you like to address first?” This addresses the user's stated ambiguity.
- This wording improvement is qualitative: the frozen E12 assertions were not expanded to retroactively change the baseline score.

## H20 — closed call, later approval

- First improved QA confused `human_request_validated=false` with identity/policy validation. That flag only represented whether a caller explicitly requested a human, so the concern was unsupported.
- Final QA excludes model interpretation annotations from ground-truth evidence. It correctly describes synthetic identity matching, approval pending fulfillment, no access grant, and a closed call.

## Limits and next step

All 29 final reports used Claude rather than the rules fallback. This review sampled the cases above, not every sentence in all reports. Numerical pass rates remain the frozen evaluator's results. A future change could supply exact tool-call counts and use deterministic language for factual counts; evaluate this with supplemental narrative checks or a new reviewed dataset version. Do not edit the current labels to conceal prose errors.
