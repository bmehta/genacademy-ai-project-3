"""Import reviewed labels from the workbook before freezing the dataset."""
import json
from pathlib import Path
from openpyxl import load_workbook
HERE=Path(__file__).resolve().parent
path=HERE/'golden_dataset.json'
if (HERE/'results/baseline.json').exists():
    raise SystemExit('A baseline exists. Do not change frozen labels. Archive the run and create a new dataset version deliberately.')
old=json.loads(path.read_text());by_id={c['case_id']:c for c in old}
ws=load_workbook(HERE/'Northstar-Week4-Golden-Dataset.xlsx',data_only=True)['Cases']
headers=[c.value for c in ws[1]];seen=set()
for values in ws.iter_rows(min_row=2,values_only=True):
    row=dict(zip(headers,values));cid=row['case_id']
    if cid not in by_id or cid in seen:raise SystemExit('Unknown or duplicate case ID: '+str(cid))
    seen.add(cid);c=by_id[cid]
    c['label_status']=row['label_status'];c['reviewer']=str(row['reviewer'] or '').strip();c['label_notes']=str(row['label_notes'] or '')
    c['actions']=json.loads(row['actions_json']);c['expected_final']=json.loads(row['expected_final_json']);c['expected_behavior']=row['expected_behavior']
    if c['label_status']=='APPROVED' and not c['reviewer']:raise SystemExit('Reviewer required for '+cid)
if len(seen)!=40:raise SystemExit('Expected exactly 40 cases.')
path.write_text(json.dumps(old,indent=2)+'\n')
print('Imported labels. Approved:',sum(c['label_status']=='APPROVED' for c in old),'/40')
