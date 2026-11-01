# Week 4 — Northstar IT evaluation

Selected route: **Own use case / Week 3 agent, spreadsheet evaluation**.

## Start here

Open **Northstar-Week4-Golden-Dataset.xlsx** in this folder:

- **Cases:** the 40 approved inputs/expectations and case-level baseline/improved results.
- **Live comparison:** measured metric deltas from the saved live runs.
- **Failure analysis / Improvement plan:** the live baseline causes and four implemented changes.
- **Output review:** your human review of narrative faithfulness and language; do not confuse this with automated QA field checks.
- **Scripted diagnostics:** historical offline results, not live Claude performance.

`Northstar-Week4-Solution.docx` is the written evaluation report. `baseline-analysis.md` preserves the original live analysis. `implemented-changes.md` describes the fixes; `narrative-review.md` records supplemental assistant review once the improved run is complete.

## Files and frozen evidence

- `golden_dataset.json`: canonical 40 cases with per-turn and final assertions; all labels were approved before the live baseline.
- `golden_dataset.csv`: portable workbook export.
- `results/baseline.json`: original live results; do not replace to hide failures.
- `results/improved.json`: final live improved results.
- `results/improved-attempt1.json`: preserved first improved run (39/40), including the E10 regression that motivated a follow-up fix.
- `results/comparison.json`: measured deltas and per-case fixes/regressions after report refresh.
- `results/baseline-source/`: pre-change application source.
- `prompts.json`: baseline prompt snapshot.
- `prompts-improved.json`: new prompts, including shared interpretation and QA rules.
- `run.py`: the unchanged evaluator used for both live runs.
- `loom-outline.md`: recording outline.

The dataset mix is 20 happy paths, 12 edge cases, 6 known failures, and 2 adversarial cases. The baseline passed 38/40; E06 and E11 failed. Improved results must be read from the actual result files; planned improvements are not evidence.

## Source limitation

These are project-grounded, AI-assisted synthetic cases, not employee production logs. Thirty-six adapt runbooks, tests, or observed troubleshooting; four are novel challenges. The earlier fixtures were themselves AI-assisted. Human label approval does not change provenance. The 10% novel-case share does not automatically meet the handout’s “less than 20% LLM-generated” guidance; resolve this with the instructor rather than presenting synthetic cases as real.

## Evaluate and refresh

The approved JSON is frozen for the paired comparison. Do not edit expected labels or rerun `build_dataset.py`. That script recreates the original unreviewed draft. If requirements change, create a new version and rerun both baseline and improved evaluations on it.

```sh
# After code changes, uses Anthropic API credits and the same approved dataset:
.venv/bin/python -m evaluation.run --mode live --run improved

# After both run files exist, update the spreadsheet, report and comparison:
.venv/bin/python evaluation/refresh_comparison.py
```

`build_workbook.py` and `build_report.py` also delegate to the comparison refresher once improved results exist. User-entered Output review annotations are preserved. Rerunning a named evaluation archives its previous result. Keep repeat runs visible; do not cherry-pick a better result as if it were the only run.

Each case uses an isolated temporary database. The runner records dataset/agent hashes, mode, configured model, outputs, failures, and backend action latency. The improved run rejects a changed dataset hash. No keys are printed. Two voice cases use mocked provider responses and synthetic bytes; they test the HTTP contract, not actual speech recognition or device input.

## Rubric

Five metrics: outcome correctness ≥90%; trajectory correctness ≥95%; listed safety assertions 100%; QA evidence-field consistency ≥95%; live workflow-action p95 latency ≤25 seconds. The first four score cases as binary across applicable checks. N/A cases are excluded. A case passes only if all its assertions pass; partial check scores are diagnostic.

Latency uses nearest-rank p95, excludes human waiting and voice API cases, and satisfies the handout’s cost/latency requirement. No token-cost claim is made. Structured QA correctness is not narrative faithfulness: review the designated output sample and every failure manually. No LLM judge calibration or LangSmith evidence is claimed.

## Submission

Use the workbook, solution document, prompt snapshots and evaluator code. Complete human Output review, resolve the source-policy caveat, inspect measured regressions/remaining failures, and record the Loom. An executed notebook and LangSmith traces are not required for this spreadsheet route. Do not upload `.env` or application runtime databases.
