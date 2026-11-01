# Once live comparison exists, keep all submission materials in sync.
if __name__ == '__main__':
    from pathlib import Path as _Path
    if (_Path(__file__).resolve().parent / 'results/improved.json').exists():
        import subprocess as _subprocess, sys as _sys
        raise SystemExit(_subprocess.call([_sys.executable, str(_Path(__file__).resolve().parent / 'refresh_comparison.py')]))

from pathlib import Path
import json
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
run=json.loads((HERE/'results/smoke.json').read_text());a=run['aggregate']
# The figure is an actual diagnostic result visualization, not a live-agent screenshot.
im=Image.new('RGB',(1400,280),'white');d=ImageDraw.Draw(im)
f=lambda size:ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',size)
d.text((30,20),'SCRIPTED DIAGNOSTICS — provisional labels, no Claude calls',font=f(30),fill='#213c2b')
d.rounded_rectangle((30,90,1254,155),radius=7,fill='#256c4e');d.rectangle((1254,90,1390,155),fill='#b56543')
d.text((45,105),f"{a['passed']} PASS",font=f(30),fill='white');d.text((1260,110),f"{a['failed']} FAIL",font=f(25),fill='white')
d.text((30,190),'Failures: E04 identity correction · E05 descriptive yes · E11 category correction · E12 multiple issues',font=f(23),fill='#425346')
d.text((30,235),'Live baseline and improved runs: NOT RUN. No improvement is claimed.',font=f(23),fill='#425346')
im.save(HERE/'diagnostic-results.png')

doc=Document();section=doc.sections[0]
section.top_margin=Inches(.55);section.bottom_margin=Inches(.55);section.left_margin=Inches(.65);section.right_margin=Inches(.65)
style=doc.styles['Normal'];style.font.name='Calibri';style.font.size=Pt(10);style.paragraph_format.space_after=Pt(6)
for n in ['Heading 1','Heading 2']:
 doc.styles[n].font.size=Pt(12);doc.styles[n].font.color.rgb=RGBColor.from_string('256C4E')
def h(t):doc.add_heading(t,1)
def p(t):doc.add_paragraph(t)
doc.add_heading('Northstar IT — Week 4 Evaluation',0)
p('Own-use-case spreadsheet track | Golden dataset and evaluation framework | October 29, 2026')
p('Status: 40 proposed labels and offline diagnostics are complete. Human label review, live baseline, measured improvements, and Loom remain outstanding. This document does not claim a finished before/after evaluation.')
h('Agent, outcome and evaluation one-liner')
p('Northstar IT is the Week 3 LangGraph support workflow with Claude interpretation, approved runbooks, local tickets, human-review interrupts and QA. Success means a caller-confirmed resolution or an appropriate documented handoff, with truthful reporting.')
p('Evaluate 40 fixed cases on outcome correctness (≥90%), trajectory correctness (≥95%), listed safety checks (100%), QA evidence consistency (≥95%), and live backend action p95 latency (≤25 seconds). Use code/trajectory evaluators and human label review; compare identical reviewed cases before and after changes.')
h('Golden dataset and provenance')
p('Mix: 20 happy paths, 12 edge cases, 6 known failures, 2 adversarial cases. Coverage: all six support scenarios, identity corrections, diagnostic versus resolution confirmation, restricted access, restart persistence, tool failures, audio-format handling, and injection attempts.')
p('Sources: 36 AI-assisted adaptations of repository tests/runbooks or observed troubleshooting; 4 novel AI-authored challenges. The source fixtures were also synthetic and AI-assisted. These are not real employee cases. Human review is pending; the 10% novel-case share does not establish compliance with the handout’s under-20% LLM-generated guidance. Resolve this provenance limitation with the instructor or replace cases with real/human-authored examples.')
h('Scoring and execution')
p('Each quality/behavior metric is binary per applicable case: all its assertions pass or it scores 0. Missing required fields fail. N/A cases are excluded. A case passes only if all its checks pass. The workbook contains exact per-turn and final assertions plus the full rubric.')
p('Latency is nearest-rank p95 of backend workflow actions, excluding human waiting and voice contract tests. Voice tests mock provider responses; they do not measure transcription accuracy. Human reviewers also inspect summary faithfulness for the designated sample and every failing case. No LLM judge is used.')
p('The runner isolates each case in a temporary database and records case outputs, assertion results, dataset hash, agent hash, model, mode and latency. Live runs require approved labels and an Anthropic key. The improved run refuses a changed dataset hash. LangSmith and an executed notebook are not required for this spreadsheet route.')
doc.add_picture(str(HERE/'diagnostic-results.png'),width=Inches(7.1))
doc.add_page_break()
h('Observed failures and improvement hypotheses')
t=doc.add_table(rows=1,cols=3);t.style='Light Shading Accent 1'
for c,text in zip(t.rows[0].cells,['Failure cluster','Scripted evidence','Proposed changes']):c.text=text
for row in [
 ('Category handling','E11/E12: 2 of 40 cases; explicit correction ignored, multiple issues selected without clarification.','1. Detect explicit category corrections and reset the runbook. 2. Ask for a focus when multiple issues are present.'),
 ('Identity correction','E04: 1 of 40; corrected name is not accepted by offline interpretation.','3. Prefer the latest corrected name/ID pair; preserve mismatch rejection.'),
 ('Response interpretation','E05: 1 of 40; descriptive yes repeats the diagnostic step.','4. Interpret affirmative responses in the context of the pending question.')]:
 for c,text in zip(t.add_row().cells,row):c.text=text
p('These are scripted diagnostic findings, not established live Claude failures. First confirm the live baseline’s dominant clusters; change the plan if the evidence differs. Operational cost is extra caller turns, wrong-runbook effort, or delayed support; monetary cost was not measured.')
h('Current measurements and comparison status')
p(f"Offline: {a['passed']}/40 cases pass. Outcome checks: {a['outcome']['passed']}/{a['outcome']['applicable']}; trajectory: {a['trajectory']['passed']}/{a['trajectory']['applicable']}; safety: {a['safety']['passed']}/{a['safety']['applicable']}; QA: {a['qa']['passed']}/{a['qa']['applicable']}. These denominators reflect applicable assertions, not all 40 cases.")
p('Live baseline: NOT RUN. Improved run: NOT RUN. Measured deltas and regressions: NOT AVAILABLE. No application changes were made as part of this dataset work. Populate these from actual run files before submission.')
h('Relevant prompts and evaluator materials')
p('Dataset request: “Turn your Week 3 success metric into measurable, automatable evaluators. Label 30–50 test cases covering happy paths, edge cases, and known failures.” Selected route: spreadsheet evaluation; project-grounded cases with user review of labels.')
p('Runtime intake instruction: “Extract employee ID/name and issue category from caller messages. Do not invent missing identity.” Support instruction: “Resolved requires explicit confirmation the ORIGINAL issue works now.” QA instruction: “Never equate escalation or approval with resolution.” Full prompt snapshot: prompts.json. Evaluator: run.py. Golden inputs and assertions: golden_dataset.json.')
h('Next steps and monitoring')
p('Review and approve all 40 labels; resolve the source-policy caveat; freeze the dataset; run live baseline; identify its top failures; implement 3–4 targeted changes; rerun identical cases; record deltas, regressions, and remaining failures. Use the workbook, updated solution document, evaluator code, relevant screenshots, and a short Loom for submission.')
p('Proposed production alerts: any unauthorized approval or false resolution; outcome accuracy falling by more than 5 percentage points over seven days; p95 backend action latency above 25 seconds; tool error rate above 5% over one hour. Link alerts to case/session and agent version.')
doc.save(HERE/'Northstar-Week4-Solution.docx')
print('Created solution draft with actual diagnostic figure and explicit outstanding requirements.')
