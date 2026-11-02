"""Refresh submission artifacts from measured runs without modifying frozen evaluation data."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import load_workbook
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
b=json.loads((HERE/'results/baseline.json').read_text())
i=json.loads((HERE/'results/improved.json').read_text())
assert b['dataset_sha256']==i['dataset_sha256']==hashlib.sha256((HERE/'golden_dataset.json').read_bytes()).hexdigest()
assert b['mode']==i['mode']=='live'
bcases={r['case_id']:r for r in b['results']};icases={r['case_id']:r for r in i['results']}
assert bcases.keys()==icases.keys()
fixed=[cid for cid in bcases if bcases[cid]['status']=='FAIL' and icases[cid]['status']=='PASS']
regressed=[cid for cid in bcases if bcases[cid]['status']=='PASS' and icases[cid]['status']=='FAIL']
remaining=[cid for cid,r in icases.items() if r['status']=='FAIL']
rows=[]
for m,t in [('outcome',.90),('trajectory',.95),('safety',1.0),('qa',.95)]:
    base=b['aggregate'][m];imp=i['aggregate'][m]
    rows.append([m,f"{base['passed']}/{base['applicable']} ({base['rate']:.2%})",f"{imp['passed']}/{imp['applicable']} ({imp['rate']:.2%})",f"{100*(imp['rate']-base['rate']):+.2f} pp",'PASS' if imp['rate']>=t else 'FAIL'])
bp=b['aggregate']['workflow_action_p95_seconds'];ip=i['aggregate']['workflow_action_p95_seconds']
rows.append(['latency',f'{bp:.2f} s',f'{ip:.2f} s',f'{ip-bp:+.2f} s','PASS' if ip<=25 else 'FAIL'])
comparison={'baseline':b['aggregate'],'improved':i['aggregate'],'fixed_cases':fixed,'regressions':regressed,'remaining_failures':remaining,'intermediate_attempt': json.loads((HERE/'results/improved-attempt1.json').read_text())['aggregate'] if (HERE/'results/improved-attempt1.json').exists() else None,'dataset_sha256':b['dataset_sha256'],'agent_hash_changed':b['agent_sha256']!=i['agent_sha256'],'metrics':rows}
(HERE/'results/comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')

workbook=HERE/'Northstar-Week4-Golden-Dataset.xlsx'
# Preserve user-entered output-review annotations across a result rebuild.
old=load_workbook(workbook)
prior_output=[list(row) for row in old['Output review'].iter_rows(min_row=2,values_only=True)]
old.close()
import runpy
runpy.run_path(str(HERE/'build_workbook.py'))
wb=load_workbook(workbook)
read=wb['Read me']
updates={
'Status':f"40 labels approved. Live baseline: {b['aggregate']['passed']}/40; improved: {i['aggregate']['passed']}/40. Human narrative review, Loom and the sourcing caveat remain submission tasks.",
'Review action':'All 40 case labels are approved and frozen. Do not re-import or change expected labels during this comparison.',
'Automation':'Baseline and improved were executed in live mode against the same dataset SHA. See Live comparison and Cases for measured results.',
'Submission checklist':'Live case results, comparison, four implemented changes, code and prompts are provided. Complete the human Output review, resolve source-policy caveat, and record Loom.'}
for row in read.iter_rows(min_row=2):
    if row[0].value in updates:row[1].value=updates[row[0].value]
fa=wb['Failure analysis'];fa.delete_rows(2,fa.max_row)
for row in [
 ['Ignored category correction','E11','1/40 live baseline','Stored non-unknown category overrides new interpretation.','Wrong troubleshooting path.','Validate explicit correction; update category and reset step.',icases['E11']['status']+' in improved run','P0'],
 ['Premature human handoff','E06','1/40 live baseline','Failed step treated as human request; subsequent input rejected.','Skipped last runbook step; inaccurate ticket reason.','Require caller quote for explicit human request; log effective intent.',icases['E06']['status']+' in improved run','P1'],
 ['Intermediate justification regression','E10','1/40 in first improved run','Model reasoning filled business-purpose field.','Ticket created before collecting purpose.','Require a verbatim caller-purpose quote.',icases['E10']['status']+' in final run; first attempt preserved.','P1'],
 ['Narrative / focus-question coverage','E06 / E12','Qualitative review, not separately scored','QA inferred call end and repeated steps; E12 only checked state.','Misleading summary or unfocused clarification.','Evidence packet, call status, actual questions and specific focus question.','See narrative-review.md; not a calibrated human score.','P1']]:fa.append(row)
plan=wb['Improvement plan'];plan.delete_rows(2,plan.max_row)
for row in [
 ['1','Category correction','E11','Evidence-backed explicit correction resets category and runbook.','Fix wrong-runbook behavior.','IMPLEMENTED; E11 '+icases['E11']['status']],
 ['2','Human-request evidence','E06 / E08','Validate current caller quote; failures alone cannot request a human.','Avoid premature escalation while honoring real requests.','IMPLEMENTED; E06 '+icases['E06']['status']+'; E08 '+icases['E08']['status']],
 ['3','Grounded QA','E06 / H20','Numbered messages/events, actual asked steps and explicit call closure.','Reduce unsupported narrative claims.','IMPLEMENTED; supplemental qualitative review, no new numeric metric.'],
 ['4','Multiple-issue clarification','E12','Ask which reported issue to address first, then use selection.','Clarify focus before runbook selection.','IMPLEMENTED; E12 '+icases['E12']['status']+'; wording reviewed separately.']]:plan.append(row)
out=wb['Output review'];out.delete_rows(2,out.max_row)
for row in prior_output:out.append(row)
check=wb['Submission checklist']
check_updates={
 '40-case golden dataset':('40/40 labels approved','Keep frozen; source-policy caveat still applies.'),
 'Case-level baseline results':(f"COMPLETE: {b['aggregate']['passed']}/40 PASS",'Preserved in results/baseline.json.'),
 '3–4 targeted changes':('Four changes implemented','See Improvement plan and code diff.'),
 'Case-level improved results and deltas':(f"COMPLETE: {i['aggregate']['passed']}/40 PASS",'Inspect remaining failures/regressions and human narrative review.'),
 'Solution document':('Updated with measured results','Review narrative-review.md and complete human assessment.'),
 'Prompts / evaluator code':('Baseline and improved prompts provided','prompts.json and prompts-improved.json.')}
for row in check.iter_rows(min_row=2):
    if row[0].value in check_updates:row[1].value,row[2].value=check_updates[row[0].value]
# Apply consistent formatting to new rows.
from copy import copy
for ws in [fa,plan,out]:
    template=wb['Cases'][2]
    for row in ws.iter_rows(min_row=2):
        ws.row_dimensions[row[0].row].height=90
        for cell in row:
            cell.alignment=copy(template[0].alignment);cell.font=copy(template[0].font)
    ws.auto_filter.ref=ws.dimensions
wb.save(workbook)

# Chart of measured case pass rates; not a fabricated application screenshot.
im=Image.new('RGB',(1400,360),'white');d=ImageDraw.Draw(im)
f=lambda n:ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',n)
d.text((25,15),'LIVE EVALUATION — same 40 reviewed cases',font=f(30),fill='#24452f')
for y,label,run in [(85,'Baseline',b),(180,'Improved',i)]:
    count=run['aggregate']['passed'];d.text((25,y+15),label,font=f(26),fill='#24452f')
    d.rectangle((210,y,1330,y+65),fill='#b56543');d.rectangle((210,y,210+1120*count/40,y+65),fill='#256c4e')
    d.text((230,y+15),f'{count}/40 PASS',font=f(29),fill='white')
d.text((25,290),f"Fixed: {', '.join(fixed) or 'none'} | Regressions: {', '.join(regressed) or 'none'} | Remaining: {', '.join(remaining) or 'none'}",font=f(23),fill='#425346')
im.save(HERE/'live-comparison.png')

doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.55);sec.left_margin=sec.right_margin=Inches(.65)
style=doc.styles['Normal'];style.font.name='Calibri';style.font.size=Pt(10);style.paragraph_format.space_after=Pt(5)
for name in ['Heading 1','Heading 2']:doc.styles[name].font.size=Pt(12);doc.styles[name].font.color.rgb=RGBColor.from_string('256C4E')
def h(t):doc.add_heading(t,1)
def p(t):doc.add_paragraph(t)
doc.add_heading('Northstar IT — Week 4 Evaluation',0)
p('Own-use-case spreadsheet track | Measured baseline and improved runs | November 1, 2026')
h('Use case and evaluation framework')
p('Northstar IT uses LangGraph, Claude, local tools/tickets, human review and QA to guide employees to caller-confirmed resolution or an appropriate handoff. Evaluate outcome correctness ≥90%, trajectory correctness ≥95%, listed safety assertions 100%, QA field consistency ≥95%, and backend action p95 ≤25 seconds on identical reviewed cases.')
p('Dataset: 40 approved labels, comprising 20 happy paths, 12 edge cases, 6 known failures and 2 adversarial cases. Thirty-six adapt repository/runbook/observed seeds; four are novel AI-authored challenges. All formulations are AI-assisted and source fixtures were synthetic. Label approval does not make these real cases or prove compliance with the handout’s under-20% LLM-generated sourcing guidance.')
h('Scoring and evidence')
p('Code/trajectory checks score each applicable case as 1 only if all assertions for that metric pass; N/A cases are excluded. A case passes only if all its assertions pass. Structured QA checks do not prove prose faithfulness. Human review of the designated outputs remains separate. No LLM judge or LangSmith is used.')
p('Both runs used claude-haiku-4-5-20251001 and identical dataset hashes. The agent hash changed. Each case used an isolated database. Two voice API cases mock transcription; they do not measure actual microphone or STT quality. Latency excludes human waiting and audio capture/playback. This is one run per version, not a repeated reliability estimate.')
h('Measured results')
t=doc.add_table(rows=1,cols=5);t.style='Light Shading Accent 1'
for c,s in zip(t.rows[0].cells,['Metric','Baseline','Improved','Delta','Target']):c.text=s
for row in rows:
 for c,s in zip(t.add_row().cells,row):c.text=s
p(f"Overall: {b['aggregate']['passed']}/40 → {i['aggregate']['passed']}/40. Fixed cases: {', '.join(fixed) or 'none'}. Regressions: {', '.join(regressed) or 'none'}. Remaining scored failures: {', '.join(remaining) or 'none'}.")
doc.add_picture(str(HERE/'live-comparison.png'),width=Inches(7.1))
doc.add_page_break()
h('Failure analysis and implemented changes')
p('E11: the workflow preserved Wi-Fi after an explicit VPN correction. Added an evidence-backed correction signal, category replacement and step reset. E06: “Still not working” was treated as a human request, skipping the final printer step; added explicit request evidence validation and raw/effective intent logging.')
p('A qualitative E06 review found unsupported claims that the call ended and identical steps repeated. QA now receives call-closure status, actual questions asked, numbered messages/events, and instructions against unsupported actions or requirements. E12 passed state checks but asked a generic category question; multiple-issue extraction now produces a specific focus question.')
p('These four changes were evaluated as one bundle. Per-case gains support the targeted fixes, but aggregate deltas cannot isolate each change’s causal contribution. QA grounding and question wording require separate qualitative assessment; the frozen rubric was not altered to award them new scores.')
h('Observed regression and follow-up revision')
p('The first improved run scored 39/40: E06 and E11 were fixed, but E10 regressed because model reasoning was accepted as a business justification. That run is preserved as improved-attempt1.json. The next revision requires a verbatim caller purpose instead of model commentary and excludes model interpretation events from QA ground-truth evidence. Final results above come from the subsequent full run, not a silent replacement of the failed attempt.')
h('Prompts and implementation evidence')
p('New interpretation instruction: “Still not working” and “No, that didn’t fix it” mean failed, not human. Human requests need an exact supporting quote. Explicit issue corrections return a new category plus quote; unresolved multiple issues trigger a focus question.')
p('New QA instruction: “Only say a call ended if call_closed=true.” Actual asked steps are supplied independently from tool lookup events. Findings reference numbered transcript/event evidence. Baseline prompts: prompts.json. Improved prompts: prompts-improved.json. Changes: app/agents.py and app/workflow.py. Evidence: results/baseline.json, results/improved.json, results/comparison.json and narrative-review.md.')
h('Validation, remaining limits and next steps')
p('40 automated tests passed before the final improved run, including correction routing, rejecting fabricated human-request evidence, preserving genuine handoffs, multi-issue selection, and accurate QA call-state inputs. The reviewed dataset and baseline were preserved. Expected outputs were not changed to fit predictions.')
p('One qualitative issue remains: E06 QA says three runbook lookups although the log contains four. This is outside the frozen structured-field checks; narrative faithfulness is not fully solved. Inspect the qualitative review notes before submission. Complete the workbook’s human Output review, resolve the sourcing caveat with the instructor, and record Loom using the measured results. Spreadsheet track does not require LangSmith traces or an executed notebook. Local demo authentication and administrative actions remain simulated.')
p('Suggested monitoring: any unauthorized approval/false resolution; outcome accuracy falling >5 percentage points over seven days; p95 backend action latency >25 seconds; tool errors >5% over an hour. Include session and agent version in alerts.')
doc.save(HERE/'Northstar-Week4-Solution.docx')
print(json.dumps(comparison,indent=2))
