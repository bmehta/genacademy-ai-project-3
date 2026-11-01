import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import TypedDict
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command
from .agents import Agents
from .fixtures import EMPLOYEES, RUNBOOKS
from .storage import Store, now


@tool
def employee_lookup(employee_id: str, employee_name: str) -> dict:
    """Match an employee ID and full name against fictional records. Not real authentication."""
    normalize = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    return next((e for e in EMPLOYEES if normalize(e['id']) == normalize(employee_id)
                 and normalize(e['name']) == normalize(employee_name)), {})


@tool
def runbook_lookup(category: str) -> dict:
    """Retrieve the approved synthetic support runbook for a supported issue category."""
    return RUNBOOKS.get(category, {})


class State(TypedDict, total=False):
    id: str
    messages: list
    events: list
    verified: bool
    employee: dict
    category: str
    step: int
    outcome: str
    agent: str
    route: str
    reason: str
    ticket_id: str
    summary: str
    review: dict
    decision: dict
    fault: str
    event: str
    justification: str
    confirmations: list
    clarification_count: int
    pending_issues: list
    call_closed: bool


class Workflow:
    def __init__(self, directory, agents=None):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.store = Store(Path(directory) / 'support.sqlite')
        self.agents = agents or Agents()
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(str(Path(directory) / 'checkpoints.sqlite'), check_same_thread=False)
        self.checkpointer = SqliteSaver(self.connection)
        graph = StateGraph(State)
        for name in ['dispatch', 'intake', 'support', 'escalation', 'quality', 'human_review', 'decision_review']:
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, 'dispatch')
        graph.add_conditional_edges('dispatch', lambda s: s['route'], {'intake': 'intake', 'support': 'support', 'quality': 'quality', 'escalation': 'escalation'})
        for node in ['intake', 'support']:
            graph.add_conditional_edges(node, lambda s: s['route'], {'end': END, 'support': 'support', 'escalation': 'escalation', 'quality': 'quality'})
        graph.add_edge('escalation', 'quality')
        graph.add_conditional_edges('quality', lambda s: 'human' if s['outcome'] == 'pending_review' else 'end', {'human': 'human_review', 'end': END})
        graph.add_edge('human_review', 'decision_review')
        graph.add_edge('decision_review', END)
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def config(self, sid):
        return {'configurable': {'thread_id': sid}}

    def say(self, state, text, agent, **changes):
        return {**changes, 'agent': agent, 'messages': state['messages'] + [{'role': 'assistant', 'text': text, 'agent': agent, 'at': now()}]}

    def log(self, state, name, status, detail):
        return state.get('events', []) + [{'at': now(), 'name': name, 'status': status, 'detail': detail}]

    def interpret(self, state, role):
        info = self.agents.interpret(state, role)
        latest = next((m['text'] for m in reversed(state['messages']) if m['role'] == 'user'), '')
        quote = info.get('human_request_evidence', '').strip()
        explicit = bool(quote and quote.casefold() in latest.casefold()
                        and re.search(r'\b(human|person|technician|representative|someone|agent|escalat\w*)\b', quote, re.I)
                        and not re.search(r"\b(?:don't|do not|never|no need to)\b", quote, re.I))
        raw_intent = info['intent']
        if raw_intent == 'human' and not explicit:
            info = {**info, 'intent': 'failed' if state.get('step', -1) >= 0 else 'question'}
        purpose = info.get('justification', '').strip()
        purpose_is_quote = bool(purpose and any(purpose.casefold() in m['text'].casefold()
                                                for m in state['messages'] if m['role'] == 'user'))
        info = {**info, 'justification': purpose if purpose_is_quote else ''}
        detail = json.dumps({'raw_intent': raw_intent, 'effective_intent': info['intent'],
                             'category': info['category'], 'category_corrected': info.get('category_corrected', False),
                             'correction_evidence': info.get('correction_evidence', ''),
                             'human_request_evidence': quote, 'human_request_validated': explicit,
                             'justification_is_caller_quote': purpose_is_quote,
                             'multiple_issues': info.get('multiple_issues', [])})
        return {**state, 'events': self.log(state, role + '_interpretation', 'ok', detail)}, info

    def create(self, fault='none'):
        with self.lock:
            sid = uuid.uuid4().hex
            self.store.add_session(sid)
            state = {'id': sid, 'messages': [{'role': 'assistant', 'agent': 'intake', 'text': "Hi, I'm Nova, Northstar's IT assistant. Please tell me your full name, employee ID, and what you need help with. Use the fictional details shown here; don't share passwords or codes.", 'at': now()}],
                     'events': [], 'verified': False, 'category': 'unknown', 'step': -1, 'outcome': 'active', 'agent': 'intake', 'fault': fault, 'event': 'message', 'confirmations': [], 'clarification_count': 0}
            self.graph.update_state(self.config(sid), state, as_node='decision_review')
            return self.get(sid)

    def get(self, sid):
        if not self.store.exists(sid):
            raise KeyError(sid)
        state = dict(self.graph.get_state(self.config(sid)).values)
        return {**state, 'closed': self.store.closed(sid), 'mode': self.agents.mode}

    def message(self, sid, text):
        with self.lock:
            state = self.get(sid)
            if state['closed'] or state['outcome'] not in ['active', 'ticket_failed']:
                raise ValueError('This session is complete or awaiting a reviewer. Start a new session or use human review.')
            if len(state['messages']) >= 80:
                raise ValueError('Session limit reached. End this call and start a new session.')
            self.graph.invoke({'event': 'message', 'messages': state['messages'] + [{'role': 'user', 'text': text, 'at': now()}]}, self.config(sid))
            return self.get(sid)

    def end(self, sid):
        with self.lock:
            state = self.get(sid)
            if not state['closed'] and state['outcome'] == 'active':
                self.graph.invoke({'event': 'end'}, self.config(sid))
            self.store.close(sid)
            return self.get(sid)

    def retry_ticket(self, sid):
        with self.lock:
            if self.get(sid)['outcome'] != 'ticket_failed':
                raise ValueError('There is no failed ticket to retry.')
            self.graph.invoke({'event': 'retry', 'fault': 'none'}, self.config(sid))
            return self.get(sid)

    def decide(self, sid, decision):
        with self.lock:
            state = self.get(sid)
            if state['outcome'] != 'pending_review':
                raise ValueError('This request is not pending review.')
            if decision['decision'] == 'approved' and (not state.get('verified') or state['category'] != 'access'):
                raise ValueError('Only verified synthetic software requests can be approved. Other escalations can be accepted for follow-up or rejected.')
            self.graph.invoke(Command(resume=decision), self.config(sid))
            return self.get(sid)

    def dispatch(self, state):
        if state['event'] == 'end':
            return {'route': 'quality', 'outcome': 'incomplete'}
        if state['event'] == 'retry' or state['outcome'] == 'ticket_failed':
            return {'route': 'escalation'}
        return {'route': 'support' if state.get('verified') else 'intake'}

    def intake(self, state):
        try:
            if state['fault'] == 'model':
                raise TimeoutError('Simulated model timeout')
            state, info = self.interpret(state, 'intake')
        except Exception:
            return {'route': 'escalation', 'reason': 'Intake model unavailable after bounded retry.', 'events': self.log(state, 'intake_model', 'error', 'Model unavailable; safe escalation selected.')}
        changes = {'category': info['category'], 'justification': info['justification'], 'events': state['events']}
        if info['intent'] == 'human':
            return {**changes, 'route': 'escalation', 'reason': 'Caller requested a human.'}
        if not info['employee_id'] or not info['employee_name']:
            n = state.get('clarification_count', 0) + 1
            if n >= 3:
                return {**changes, 'route': 'escalation', 'reason': 'Unable to collect employee details after three attempts.'}
            return self.say(state, 'Please provide your full name and employee ID, for example Maya Chen, NS-1001.', 'intake', **changes, route='end', clarification_count=n)
        events = state.get('events', [])
        matched = {}
        for attempt in range(2):
            try:
                if state['fault'] == 'lookup':
                    raise TimeoutError()
                matched = employee_lookup.invoke({'employee_id': info['employee_id'], 'employee_name': info['employee_name']})
                events += [{'at': now(), 'name': 'employee_lookup', 'status': 'ok' if matched else 'mismatch', 'detail': 'Synthetic record match; not authentication.'}]
                break
            except TimeoutError:
                events += [{'at': now(), 'name': 'employee_lookup', 'status': 'error', 'detail': f'Timeout, attempt {attempt + 1}/2.'}]
        else:
            return {**changes, 'events': events, 'route': 'escalation', 'reason': 'Employee lookup timed out twice; identity remains unverified.'}
        if not matched:
            n = state.get('clarification_count', 0) + 1
            if n >= 3:
                return {**changes, 'events': events, 'route': 'escalation', 'reason': 'Employee details could not be matched.'}
            return self.say(state, "Those details don't match our fictional directory. Please check the full name and employee ID and try again.", 'intake', **{**changes, 'events': events}, route='end', clarification_count=n)
        return {**changes, 'verified': True, 'employee': matched, 'events': events, 'route': 'support', 'agent': 'intake', 'clarification_count': 0}

    def support(self, state):
        try:
            state, info = self.interpret(state, 'support')
        except Exception:
            return {'route': 'escalation', 'reason': 'Support model unavailable.', 'events': self.log(state, 'support_model', 'error', 'Model unavailable after bounded retry.')}
        # Keep interpreted evidence even on branches that return before a tool call.
        result = self.support_response(state, info)
        return {'events': state['events'], **result}

    def support_response(self, state, info):
        if info['intent'] == 'human':
            return {'route': 'escalation', 'reason': 'Caller requested a human.'}
        issues = list(dict.fromkeys(k for k in info.get('multiple_issues', []) if k in RUNBOOKS))
        if len(issues) > 1:
            n = state.get('clarification_count', 0) + 1
            if n >= 3:
                return {'route': 'escalation', 'reason': 'Unable to select a primary issue after clarification.'}
            names = ', '.join(RUNBOOKS[k]['title'] for k in issues)
            return self.say(state, f'You mentioned multiple issues: {names}. Which issue would you like to address first?',
                            'support', route='end', category='unknown', step=-1, pending_issues=issues, clarification_count=n)
        quote = info.get('correction_evidence', '').strip()
        latest = state['messages'][-1]['text']
        corrected = (info.get('category_corrected', False) and quote and quote.casefold() in latest.casefold()
                     and info['category'] in RUNBOOKS and info['category'] != state['category'])
        if corrected:
            category = info['category']
            events = self.log(state, 'category_correction', 'ok', json.dumps({'from': state['category'], 'to': category, 'evidence': quote}))
            # Start the newly selected runbook even if the old issue was reported as working.
            if category != 'access':
                book = runbook_lookup.invoke({'category': category})
                events = self.log({**state, 'events': events}, 'runbook_lookup', 'ok', f"Approved synthetic runbook: {book['title']}")
                return self.say(state, book['steps'][0], 'support', category=category, step=0,
                                clarification_count=0, pending_issues=[], route='end', events=events)
            # Restricted access always follows the justification and approval path.
            result = self.support_response({**state, 'category': 'access', 'step': -1, 'clarification_count': 0, 'justification': '',
                                             'events': events}, {**info, 'category_corrected': False})
            return {'category': 'access', 'step': -1, 'clarification_count': 0, 'pending_issues': [], 'events': events, **result}
        category = state['category'] if state['category'] != 'unknown' else info['category']
        if category == 'unknown':
            n = state.get('clarification_count', 0) + 1
            if n >= 2:
                return {'route': 'escalation', 'reason': 'Issue is unclear or outside supported runbooks.'}
            return self.say(state, 'Is this about VPN, account access, Wi-Fi, a printer, your microphone, or a software request?', 'support', route='end', clarification_count=n)
        book = runbook_lookup.invoke({'category': category})
        events = self.log(state, 'runbook_lookup', 'ok', f"Approved synthetic runbook: {book['title']}")
        if category == 'access':
            justification = info['justification'] or state.get('justification', '')
            if not justification:
                n = state.get('clarification_count', 0) + 1
                if n >= 3:
                    return {'category': category, 'route': 'escalation', 'reason': 'Software request needs clarification of business justification.'}
                return self.say(state, 'Which software do you need, and what business task will you use it for? A reviewer must approve restricted access.', 'support', category=category, route='end', clarification_count=n)
            return {'category': category, 'justification': justification, 'events': events, 'route': 'escalation', 'reason': 'Restricted software access requires human approval. ' + justification}
        if info['intent'] == 'resolved' and state['step'] >= 0:
            return self.say(state, 'Thanks for confirming the issue is fixed. I’ll close this session as resolved and prepare the quality review.', 'support', category=category, route='quality', outcome='resolved', confirmations=[state['messages'][-1]['text']])
        # Clarification does not silently advance a runbook.
        step = state['step']
        if step < 0 or info['intent'] in ['continue', 'failed']:
            step += 1
        if step >= len(book['steps']):
            return {'route': 'escalation', 'reason': 'Approved troubleshooting steps exhausted without confirmation.', 'events': events}
        if state['step'] >= 0 and info['intent'] == 'question':
            n = state.get('clarification_count', 0) + 1
            if n >= 3:
                return {'route': 'escalation', 'reason': 'Caller needs assistance beyond the runbook.'}
        else:
            n = 0
        return self.say(state, book['steps'][step], 'support', category=category, step=step, route='end', events=events, clarification_count=n, pending_issues=[])

    def escalation(self, state):
        events = state.get('events', [])
        try:
            summary = self.agents.handoff(state)
        except Exception:
            summary = state.get('reason', 'Human follow-up needed.')
            events += [{'at': now(), 'name': 'escalation_model', 'status': 'error', 'detail': 'Used factual handoff fallback.'}]
        payload = {'summary': summary, 'category': state['category'], 'employee': state.get('employee', {}), 'verified': state.get('verified', False), 'justification': state.get('justification', ''), 'steps_attempted': state.get('step', -1) + 1, 'reason': state.get('reason', '')}
        for attempt in range(2):
            try:
                ticket_id = self.store.ticket(state['id'], payload, fail=state['fault'] == 'ticket')
                events += [{'at': now(), 'name': 'create_ticket', 'status': 'ok', 'detail': ticket_id}]
                return self.say(state, f'I’ve created ticket {ticket_id} for human review. No access has been granted. You can end the call; the reviewer can act afterward.', 'escalation', ticket_id=ticket_id, outcome='pending_review', summary=summary, events=events)
            except (TimeoutError, sqlite3.OperationalError):
                events += [{'at': now(), 'name': 'create_ticket', 'status': 'error', 'detail': f'Ticket write failed, attempt {attempt + 1}/2.'}]
        return self.say(state, 'I couldn’t create a ticket after two attempts. Your request is saved in this session, but no ticket exists yet. Use Retry ticket to try again.', 'escalation', outcome='ticket_failed', summary=summary, events=events)

    def quality(self, state):
        call_closed = self.store.closed(state['id']) or state.get('event') == 'end'
        try:
            report = self.agents.review({**state, 'call_closed': call_closed})
            source = self.agents.mode
        except Exception:
            report = {'summary': 'Automated QA model unavailable; evidence checks retained.', 'process_findings': ['Human QA review required.'], 'follow_up': ['Review transcript and tool events manually.']}
            source = 'rules_fallback'
        report.update({'outcome': state['outcome'], 'resolved': state['outcome'] == 'resolved', 'employee_matched': bool(state.get('verified')), 'caller_confirmation': state.get('confirmations', []), 'ticket_id': state.get('ticket_id'), 'tool_failures': [e for e in state.get('events', []) if e['status'] == 'error'], 'human_decision': state.get('decision'), 'generated_at': now(), 'source': source, 'follow_up_required': state['outcome'] != 'resolved'})
        report['call_closed'] = call_closed
        return {'review': report, 'call_closed': call_closed, 'events': self.log(state, 'quality_review', 'ok', 'Evidence-based outcome checks applied.')}

    def human_review(self, state):
        decision = interrupt({'ticket_id': state['ticket_id'], 'summary': state['summary'], 'verified': state.get('verified', False)})
        self.store.decide(state['id'], decision)
        outcome = {'approved': 'approved_pending_fulfillment', 'rejected': 'rejected', 'accepted': 'human_follow_up'}[decision['decision']]
        return {'decision': decision, 'outcome': outcome, 'events': self.log(state, 'human_review', 'ok', decision['decision'] + ': ' + decision['note'])}

    def decision_review(self, state):
        return self.quality(state)
