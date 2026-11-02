import json
from collections import Counter
from pathlib import Path
from evaluation.run import aggregate, evaluate_checks, run_case

DATA=Path(__file__).resolve().parents[1]/'evaluation/golden_dataset.json'

def test_dataset_mix_and_labels_exist():
    cases=json.loads(DATA.read_text())
    assert len(cases)==len({c['case_id'] for c in cases})==40
    assert Counter(c['scenario_type'] for c in cases)=={'happy_path':20,'edge':12,'known_failure':6,'adversarial':2}
    for c in cases:
        assert c['actions'] and c['expected_final'] and c['expected_behavior'] and c['source_reference']
        for check in c['expected_final']+[x for action in c['actions'] for x in action['checks']]:
            assert check['metric'] in ['outcome','trajectory','safety','qa']
            assert check['op'] in ['eq','contains']


def test_missing_required_value_fails():
    check={'path':'review.resolved','expected':False,'op':'eq','metric':'qa'}
    assert not evaluate_checks([check],{},'final')[0]['pass']
    assert evaluate_checks([check],{'review':{'resolved':False}},'final')[0]['pass']


def test_not_applicable_is_excluded_and_voice_latency_not_mixed():
    rows=[{'status':'PASS','metric_scores':{'outcome':1,'trajectory':1,'safety':None,'qa':None},'scope':'workflow','action_latencies_seconds':[1,2],'failures':[]},
          {'status':'FAIL','metric_scores':{'outcome':0,'trajectory':None,'safety':0,'qa':None},'scope':'voice_api','action_latencies_seconds':[999],'failures':[]}]
    a=aggregate(rows)
    assert a['outcome']['rate']==.5 and a['safety']['applicable']==1
    assert a['qa']['rate'] is None
    assert a['workflow_action_p95_seconds']==2


def test_one_case_runs_real_workflow_against_predeclared_expected():
    case=json.loads(DATA.read_text())[0]
    row=run_case(case,'scripted')
    assert row['status']=='PASS' and row['final']['outcome']=='resolved'
    assert len(row['steps'])==3
    assert row['metric_scores']['qa']==1


def test_corrected_category_passes_unchanged_golden_label():
    case=next(c for c in json.loads(DATA.read_text()) if c['case_id']=='E11')
    row=run_case(case,'scripted')
    assert row['status']=='PASS'
    assert row['final']['category']=='vpn' and row['final']['step']==0
    # The evaluator must still reject the old incorrect response.
    checks=evaluate_checks(case['expected_final'],{'category':'wifi','step':1,'outcome':'active'},'final')
    assert sum(not c['pass'] for c in checks)==2
