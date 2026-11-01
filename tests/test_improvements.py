import json
import pytest
from app.agents import Agents, Interpretation
from app.workflow import Workflow

@pytest.fixture
def flow(tmp_path):return Workflow(tmp_path,Agents(mode='scripted'))

def begin(flow,text='Maya Chen NS-1001. My printer is offline.'):
    return flow.message(flow.create()['id'],text)

def test_misclassified_failed_step_cannot_request_human(flow,monkeypatch):
    state=begin(flow)
    original=flow.agents.interpret
    def bad_model(state,role):
        result=original(state,role)
        return {**result,'intent':'human','human_request_evidence':'Still not working.'}
    monkeypatch.setattr(flow.agents,'interpret',bad_model)
    state=flow.message(state['id'],'Still not working.')
    assert state['outcome']=='active' and state['step']==1
    e=json.loads(next(e['detail'] for e in reversed(state['events']) if e['name']=='support_interpretation'))
    assert e['raw_intent']=='human' and e['effective_intent']=='failed'
    assert not e['human_request_validated']


def test_fabricated_human_quote_rejected(flow,monkeypatch):
    state=begin(flow)
    original=flow.agents.interpret
    monkeypatch.setattr(flow.agents,'interpret',lambda s,r:{**original(s,r),'intent':'human','human_request_evidence':'Get me a human please'})
    state=flow.message(state['id'],'Still not working.')
    assert state['outcome']=='active'


def test_explicit_human_still_escalates(flow):
    state=begin(flow)
    state=flow.message(state['id'],'Please connect me to a human.')
    assert state['outcome']=='pending_review' and state['reason']=='Caller requested a human.'


def test_explicit_correction_starts_new_runbook(flow):
    state=begin(flow,'Maya Chen NS-1001. My Wi-Fi is broken.')
    state=flow.message(state['id'],'Correction: Wi-Fi and websites work. Only my VPN will not connect.')
    assert state['category']=='vpn' and state['step']==0
    assert 'public website' in state['messages'][-1]['text']
    assert any(e['name']=='category_correction' for e in state['events'])


def test_incidental_category_change_does_not_switch(flow,monkeypatch):
    state=begin(flow,'Maya Chen NS-1001. My VPN is broken.')
    original=flow.agents.interpret
    monkeypatch.setattr(flow.agents,'interpret',lambda s,r:{**original(s,r),'category':'wifi','category_corrected':False})
    state=flow.message(state['id'],'Yes.')
    assert state['category']=='vpn' and state['step']==1


def test_multi_issue_focus_then_select(flow):
    state=begin(flow,'Maya Chen NS-1001. Both my VPN and printer are broken.')
    assert state['category']=='unknown' and state['step']==-1
    assert 'Which issue would you like to address first?' in state['messages'][-1]['text']
    state=flow.message(state['id'],'The printer first.')
    assert state['category']=='printer' and state['step']==0
    assert not state['pending_issues']


def test_qa_packet_contains_actual_steps_and_closure(flow,monkeypatch):
    state=begin(flow)
    state=flow.message(state['id'],'Still not working.')
    captured=[]
    original=flow.agents.review
    def record(state):
        captured.append(Agents.review_evidence(state))
        return original(state)
    monkeypatch.setattr(flow.agents,'review',record)
    state=flow.message(state['id'],'Please get me a human.')
    evidence=captured[-1]
    assert evidence['call_closed'] is False
    assert len(evidence['asked_steps'])==2
    assert len({s['text'] for s in evidence['asked_steps']})==2
    assert evidence['escalation_trigger']=='Caller requested a human.'
    flow.end(state['id'])
    flow.decide(state['id'],{'decision':'accepted','reviewer':'Test','note':'Will contact caller.'})
    assert captured[-1]['call_closed'] is True


def test_category_correction_to_access_requires_approval(flow,monkeypatch):
    state=begin(flow)
    original=flow.agents.interpret
    def correct(s,r):
        return {**original(s,r),'category':'access','category_corrected':True,
          'correction_evidence':s['messages'][-1]['text'],'justification':'for a report'}
    monkeypatch.setattr(flow.agents,'interpret',correct)
    state=flow.message(state['id'],'Correction: I need restricted software access for a report.')
    assert state['category']=='access' and state['outcome']=='pending_review'
    assert not state['review']['resolved']


def test_model_reasoning_is_not_business_justification(flow,monkeypatch):
    original=flow.agents.interpret
    def explain(state,role):
        return {**original(state,role),'justification':'This access request needs a business justification before proceeding.'}
    monkeypatch.setattr(flow.agents,'interpret',explain)
    state=begin(flow,'Maya Chen NS-1001. I need restricted software access.')
    assert state['outcome']=='active' and not flow.store.tickets()
    assert 'business task' in state['messages'][-1]['text']


def test_qa_excludes_model_interpretation_from_evidence(flow):
    state=begin(flow)
    assert any(e['name'].endswith('_interpretation') for e in state['events'])
    packet=Agents.review_evidence(state)
    assert not any(e['name'].endswith('_interpretation') for e in packet['events'])
    assert any(e['name']=='employee_lookup' for e in packet['events'])
