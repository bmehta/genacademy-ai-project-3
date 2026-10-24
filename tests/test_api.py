import httpx
import pytest
from fastapi.testclient import TestClient
from app import main
from app.agents import Agents
from app.workflow import Workflow


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'workflow', Workflow(tmp_path, Agents(mode='scripted')))
    with TestClient(main.app) as client:
        yield client


def test_complete_http_flow(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/api/config').json()['mode'] == 'scripted'
    sid = client.post('/api/sessions', json={}).json()['id']
    state = client.post(f'/api/sessions/{sid}/messages', json={'text': 'Maya Chen NS-1001. My VPN is broken'}).json()
    assert state['verified']
    result = client.post(f'/api/sessions/{sid}/end').json()
    assert result['review']['outcome'] == 'incomplete'
    assert len(client.get('/api/sessions').json()) == 1
    assert client.post(f'/api/sessions/{sid}/messages', json={'text': 'Hi'}).status_code == 409


def test_validation_and_origin(client):
    assert client.post('/api/sessions', json={'fault': 'invalid'}).status_code == 422
    assert client.post('/api/sessions', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/sessions/missing').status_code == 404
    sid = client.post('/api/sessions', json={}).json()['id']
    assert client.post(f'/api/sessions/{sid}/messages', json={'text': '   '}).status_code == 422
    assert client.post(f'/api/sessions/{sid}/decision', json={'decision': 'approved', 'reviewer': '', 'note': ''}).status_code == 422


def test_missing_voice_key(client, monkeypatch):
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    assert client.post('/api/voice/speak', json={'text': 'hello'}).status_code == 503


def fake_voice(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-only-key')
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))


def test_voice_success(client, monkeypatch):
    def upstream(request):
        assert request.headers['xi-api-key'] == 'test-only-key'
        if 'speech-to-text' in str(request.url):
            return httpx.Response(200, json={'text': 'My VPN is broken'})
        return httpx.Response(200, content=b'test-audio')
    fake_voice(monkeypatch, upstream)
    result = client.post('/api/voice/transcribe', files={'file': ('audio.webm', b'fake-recording', 'audio/webm')})
    assert result.json()['text'] == 'My VPN is broken'
    result = client.post('/api/voice/speak', json={'text': 'Try reconnecting'})
    assert result.status_code == 200 and result.content == b'test-audio'


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_voice_errors_are_safe(client, monkeypatch, status):
    fake_voice(monkeypatch, lambda request: httpx.Response(status, json={'detail': 'secret-upstream-data'}))
    result = client.post('/api/voice/speak', json={'text': 'Hello'})
    assert result.status_code == 502 and 'secret-upstream-data' not in result.text


def test_voice_timeout_and_empty_audio(client, monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout('timeout')
    fake_voice(monkeypatch, timeout)
    assert client.post('/api/voice/speak', json={'text': 'Hello'}).status_code == 504
    assert client.post('/api/voice/transcribe', files={'file': ('audio.webm', b'', 'audio/webm')}).status_code == 413
    assert client.post('/api/voice/transcribe', files={'file': ('a.txt', b'abc', 'text/plain')}).status_code == 415


def test_browser_codec_metadata_preserved(client, monkeypatch):
    def upstream(request):
        assert b'filename="recording.webm"' in request.content
        assert b'Content-Type: audio/webm;codecs=opus' in request.content
        return httpx.Response(200, json={'text': 'My VPN is broken'})
    fake_voice(monkeypatch, upstream)
    result = client.post('/api/voice/transcribe', files={'file': ('recording.webm', b'fake-audio', 'audio/webm;codecs=opus')})
    assert result.status_code == 200


def test_empty_transcription_offers_microphone_guidance(client, monkeypatch):
    fake_voice(monkeypatch, lambda request: httpx.Response(200, json={'text': '  '}))
    result = client.post('/api/voice/transcribe', files={'file': ('recording.webm', b'fake-audio', 'audio/webm')})
    assert result.status_code == 422
    assert 'microphone selection in Chrome' in result.json()['detail']
