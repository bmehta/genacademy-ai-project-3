import pytest
from app.agents import Agents
from app.workflow import Workflow


@pytest.fixture
def flow(tmp_path):
    return Workflow(tmp_path, Agents(mode='scripted'))


def start(flow, issue, fault='none'):
    state = flow.create(fault)
    return flow.message(state['id'], 'I am Maya Chen, NS-1001. ' + issue)


@pytest.mark.parametrize('issue,category', [
    ("My VPN won't connect", 'vpn'), ('My account is locked', 'account'),
    ('Wi-Fi has no internet', 'wifi'), ('Printer is offline', 'printer'), ('Microphone is not working', 'microphone')])
def test_routine_resolution(flow, issue, category):
    state = start(flow, issue)
    assert state['category'] == category and state['verified'] and state['step'] == 0
    # Yes to the first diagnostic question must not resolve the original issue.
    state = flow.message(state['id'], 'yes')
    assert state['outcome'] == 'active' and state['step'] == 1
    state = flow.message(state['id'], 'It works now')
    assert state['outcome'] == 'resolved'
    assert state['review']['resolved'] and state['review']['caller_confirmation']


def test_restart_and_approval(tmp_path):
    flow = Workflow(tmp_path, Agents(mode='scripted'))
    state = start(flow, 'I need restricted software access for a customer report')
    assert state['outcome'] == 'pending_review'
    assert flow.graph.get_state(flow.config(state['id'])).next == ('human_review',)
    flow.end(state['id'])
    flow.connection.close()
    restarted = Workflow(tmp_path, Agents(mode='scripted'))
    state = restarted.decide(state['id'], {'decision': 'approved', 'reviewer': 'Test Reviewer', 'note': 'Approved for the project.'})
    assert state['outcome'] == 'approved_pending_fulfillment'
    assert not state['review']['resolved']
    assert restarted.store.tickets()[0]['status'] == 'approved'
    with pytest.raises(ValueError):
        restarted.decide(state['id'], {'decision': 'approved', 'reviewer': 'Test', 'note': 'Duplicate'})


def test_ticket_failure_retry_no_duplicates(flow):
    state = start(flow, 'I need restricted software for a report', 'ticket')
    assert state['outcome'] == 'ticket_failed' and not state.get('ticket_id')
    assert not flow.store.tickets()
    assert len(state['review']['tool_failures']) == 2
    state = flow.retry_ticket(state['id'])
    assert state['outcome'] == 'pending_review'
    same = flow.store.ticket(state['id'], {})
    assert same == state['ticket_id'] and len(flow.store.tickets()) == 1


@pytest.mark.parametrize('fault', ['lookup', 'model'])
def test_failure_unverified_cannot_approve(flow, fault):
    state = start(flow, 'VPN is broken', fault)
    assert state['outcome'] == 'pending_review' and not state['verified']
    with pytest.raises(ValueError):
        flow.decide(state['id'], {'decision': 'approved', 'reviewer': 'Test', 'note': 'No'})
    state = flow.decide(state['id'], {'decision': 'accepted', 'reviewer': 'Test', 'note': 'Will contact caller'})
    assert state['outcome'] == 'human_follow_up'


def test_exhausted_steps_escalate(flow):
    state = start(flow, 'VPN broken')
    for _ in range(3):
        state = flow.message(state['id'], 'Still not working')
    assert state['outcome'] == 'pending_review'
    assert not state['review']['resolved']


def test_unmatched_identity(flow):
    state = flow.create()
    state = flow.message(state['id'], 'Maya Chen NS-9999. My VPN is broken')
    assert not state['verified'] and state['step'] == -1


def test_disconnect_is_incomplete(flow):
    state = start(flow, 'My VPN is broken')
    state = flow.end(state['id'])
    assert state['closed'] and state['outcome'] == 'incomplete'
    with pytest.raises(ValueError):
        flow.message(state['id'], 'Fixed')


def test_rejection(flow):
    state = start(flow, 'I need restricted software for a report')
    state = flow.decide(state['id'], {'decision': 'rejected', 'reviewer': 'Test', 'note': 'Use existing software'})
    assert state['outcome'] == 'rejected' and not state['review']['resolved']


def test_qa_model_failure_preserves_evidence(flow, monkeypatch):
    state = start(flow, 'VPN is broken')
    def fail(_):
        raise TimeoutError()
    monkeypatch.setattr(flow.agents, 'review', fail)
    state = flow.end(state['id'])
    assert state['review']['source'] == 'rules_fallback'
    assert state['review']['outcome'] == 'incomplete'
