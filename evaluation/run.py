"""Evaluate identical declarative cases. Scripted diagnostics are not live Claude results."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from dotenv import load_dotenv
from app.agents import Agents
from app.workflow import Workflow

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def code_version():
    return hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['app/agents.py','app/workflow.py','app/storage.py','app/fixtures.py','app/main.py'])).hexdigest()

def observed(flow,state,extra):
    state=dict(state)
    events=state.get('events',[])
    state.update(ticket_count=len(flow.store.tickets()),
      lookup_errors=sum(e['name']=='employee_lookup' and e['status']=='error' for e in events),
      ticket_errors=sum(e['name']=='create_ticket' and e['status']=='error' for e in events),
      model_errors=sum(e['name']=='intake_model' and e['status']=='error' for e in events))
    state.update(extra)
    return state

def lookup(state,path):
    value=state
    for key in path.split('.'):
        if not isinstance(value,dict):return None
        value=value.get(key)
    return value

def evaluate_checks(checks,state,stage):
    output=[]
    for c in checks:
        actual=lookup(state,c['path'])
        ok=actual==c['expected'] if c['op']=='eq' else isinstance(actual,str) and c['expected'].lower() in actual.lower()
        output.append({**c,'actual':actual,'pass':ok,'stage':stage})
    return output

def voice_action(flow,sid,kind):
    import httpx
    from fastapi.testclient import TestClient
    from app import main
    metadata={}
    before=flow.get(sid)['messages']
    real_client=httpx.AsyncClient
    def upstream(request):
        metadata['upstream_filename']='recording.webm' if b'filename="recording.webm"' in request.content else 'OTHER'
        return httpx.Response(200,json={'text':'My VPN is broken' if kind=='codec' else ''})
    with patch.object(main,'workflow',flow), patch.dict(os.environ,{'ELEVENLABS_API_KEY':'evaluation-mock-key'}), patch.object(main.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(upstream),**kw)):
        with TestClient(main.app) as client:
            response=client.post('/api/voice/transcribe',files={'file':('recording.webm',b'synthetic-bytes-not-real-audio','audio/webm;codecs=opus' if kind=='codec' else 'audio/webm')})
    payload=response.json()
    return {'http_status':response.status_code,'transcript':payload.get('text'),'error_detail':payload.get('detail'),
       'message_count_unchanged':before==flow.get(sid)['messages'],**metadata}

def run_case(case,mode):
    checks=[];steps=[];extra={};action_times=[]
    with tempfile.TemporaryDirectory(prefix='northstar-eval-') as tmp:
        flow=Workflow(tmp,Agents(mode=mode));state=flow.create(case['fault']);sid=state['id']
        for index,action in enumerate(case['actions'],1):
            started=time.perf_counter();extra.pop('last_error',None)
            operation=action['operation']
            exception=None
            try:
                if operation=='message':state=flow.message(sid,action['text'])
                elif operation=='end':state=flow.end(sid)
                elif operation=='retry_ticket':state=flow.retry_ticket(sid)
                elif operation=='decide':state=flow.decide(sid,{'decision':action['decision'],'reviewer':'Evaluation fixture','note':action['note']})
                elif operation=='restart':
                    flow.connection.close();flow=Workflow(tmp,Agents(mode=mode));state=flow.get(sid)
                elif operation=='duplicate_ticket':extra['duplicate_ticket_same']=flow.store.ticket(sid,{})==state['ticket_id']
                elif operation=='voice':extra.update(voice_action(flow,sid,action['kind']))
                else:raise ValueError('Unknown operation: '+operation)
            except Exception as exc:
                exception=type(exc).__name__;extra['last_error']=exception;state=flow.get(sid)
            elapsed=time.perf_counter()-started;action_times.append(elapsed)
            if exception != action.get('expect_error'):
                checks.append({'path':'exception','metric':'trajectory','op':'eq','expected':action.get('expect_error'), 'actual':exception,'pass':False,'stage':index})
            snapshot=observed(flow,state,extra)
            checks.extend(evaluate_checks(action['checks'],snapshot,index))
            steps.append({'step':index,'operation':operation,'input':action.get('text',action.get('decision','')),'latency_seconds':elapsed,'observed':snapshot})
        final=observed(flow,state,extra)
        checks.extend(evaluate_checks(case['expected_final'],final,'final'))
        flow.connection.close()
    group_scores={}
    for metric in ['outcome','trajectory','safety','qa']:
        applicable=[c for c in checks if c['metric']==metric]
        group_scores[metric]=int(all(c['pass'] for c in applicable)) if applicable else None
    failure_groups=sorted({c['metric'] for c in checks if not c['pass']})
    return {'case_id':case['case_id'],'scenario_type':case['scenario_type'],'scope':case['scope'],
      'label_status':case['label_status'],'mode':mode,'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL',
      'check_score':sum(c['pass'] for c in checks)/len(checks),'metric_scores':group_scores,
      'failure_category':','.join(failure_groups) or 'none','failures':[c for c in checks if not c['pass']],
      'action_latencies_seconds':action_times,'total_execution_seconds':sum(action_times),'final':final,'steps':steps,'checks':checks}

def aggregate(rows):
    result={'cases':len(rows),'passed':sum(r['status']=='PASS' for r in rows),'failed':sum(r['status']=='FAIL' for r in rows)}
    for m in ['outcome','trajectory','safety','qa']:
        values=[r['metric_scores'][m] for r in rows if r['metric_scores'][m] is not None]
        result[m]={'passed':sum(values),'applicable':len(values),'rate':sum(values)/len(values) if values else None}
    times=sorted(t for r in rows if r['scope']=='workflow' for t in r['action_latencies_seconds'])
    result['workflow_action_p95_seconds']=times[math.ceil(.95*len(times))-1] if times else None
    result['failure_counts']=dict(Counter(c['path'] for r in rows for c in r['failures']))
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['scripted','live'],default='scripted')
    parser.add_argument('--run',choices=['smoke','baseline','improved'],default='smoke')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    if args.mode=='live' and not os.getenv('ANTHROPIC_API_KEY'):parser.error('Live evaluation requires ANTHROPIC_API_KEY; no silent fallback.')
    if args.run in ['baseline','improved'] and args.mode!='live':parser.error('Submission baseline/improved runs require live mode. Use smoke for offline diagnostics.')
    dataset=HERE/'golden_dataset.json';cases=json.loads(dataset.read_text())
    if args.run in ['baseline','improved'] and any(c['label_status'] != 'APPROVED' or not c['reviewer'].strip() for c in cases):
        parser.error('Review all expected labels in the workbook and import approvals before submission runs. Smoke runs may use provisional labels.')
    baseline_path=HERE/'results/baseline.json'
    if args.run=='improved':
        if not baseline_path.exists():parser.error('Run baseline before improved.')
        baseline=json.loads(baseline_path.read_text())
        if baseline['dataset_sha256']!=digest(dataset):parser.error('Dataset changed since baseline. Rebaseline this version; do not compare different cases.')
    # Prevent runtime import of the HTTP app from opening the user's existing data directory.
    with tempfile.TemporaryDirectory(prefix='northstar-api-eval-') as app_data:
        with patch.dict(os.environ,{'DATA_DIR':app_data}):
            rows=[]
            for case in cases:
                row=run_case(case,args.mode);rows.append(row)
                print(case['case_id'],row['status'],row['failure_category'],flush=True)
    run={'run_name':args.run,'mode':args.mode,'executed_at':datetime.now(timezone.utc).isoformat(),
      'dataset_sha256':digest(dataset),'agent_sha256':code_version(),'model':os.getenv('ANTHROPIC_MODEL','claude-haiku-4-5-20251001') if args.mode=='live' else None,
      'limitations':['Labels are AI-proposed until explicitly reviewed.','Voice API cases use mocked transcription, not real audio or speech quality.','Scripted results do not measure Claude quality or latency.'],
      'aggregate':aggregate(rows),'results':rows}
    out=HERE/'results'/f'{args.run}.json';out.parent.mkdir(exist_ok=True)
    if out.exists():
        archive=out.with_name(f'{args.run}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")}.json')
        out.rename(archive)
    out.write_text(json.dumps(run,indent=2)+'\n')
    print(json.dumps(run['aggregate'],indent=2))

if __name__=='__main__':main()
