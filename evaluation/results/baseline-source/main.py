import os
from pathlib import Path
from typing import Literal
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .fixtures import EMPLOYEES, RUNBOOKS
from .workflow import Workflow

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
workflow = Workflow(os.getenv('DATA_DIR', str(ROOT / 'data')))
app = FastAPI(title='Northstar IT · Multi-agent support')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.middleware('http')
async def local_origin(request: Request, call_next):
    # Local demonstration app, deliberately not deployable as a public reviewer portal.
    origin = request.headers.get('origin')
    if request.method not in ['GET', 'HEAD', 'OPTIONS'] and origin and origin != str(request.base_url).rstrip('/'):
        return Response('Cross-origin writes are disabled.', status_code=403)
    return await call_next(request)


class NewSession(BaseModel):
    fault: Literal['none', 'lookup', 'ticket', 'model'] = 'none'


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class Decision(BaseModel):
    decision: Literal['approved', 'rejected', 'accepted']
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=3, max_length=1000)


def call(method, *args):
    try:
        return method(*args)
    except KeyError:
        raise HTTPException(404, 'Session not found.')
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get('/')
def index():
    return FileResponse(ROOT / 'static/index.html')


@app.get('/api/config')
def config():
    return {'mode': workflow.agents.mode, 'voice_ready': bool(os.getenv('ELEVENLABS_API_KEY')), 'employees': EMPLOYEES, 'runbooks': RUNBOOKS}


@app.post('/api/sessions')
def create(body: NewSession):
    return workflow.create(body.fault)


@app.get('/api/sessions')
def sessions():
    return [call(workflow.get, row['id']) for row in workflow.store.sessions()]


@app.get('/api/sessions/{sid}')
def session(sid: str):
    return call(workflow.get, sid)


@app.post('/api/sessions/{sid}/messages')
def message(sid: str, body: Message):
    if not body.text.strip():
        raise HTTPException(422, 'Please enter a message.')
    return call(workflow.message, sid, body.text.strip())


@app.post('/api/sessions/{sid}/end')
def end(sid: str):
    return call(workflow.end, sid)


@app.post('/api/sessions/{sid}/retry-ticket')
def retry(sid: str):
    return call(workflow.retry_ticket, sid)


@app.get('/api/tickets')
def tickets():
    return workflow.store.tickets()


@app.post('/api/sessions/{sid}/decision')
def decision(sid: str, body: Decision):
    return call(workflow.decide, sid, body.model_dump())


def voice_key():
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise HTTPException(503, 'Add ELEVENLABS_API_KEY to .env and restart the server. Text support is available.')
    return key


def voice_response(response):
    if response.is_error:
        # Do not return upstream bodies, credentials or account details.
        detail = 'Voice service unavailable. Continue with text or try again.'
        if response.status_code in [401, 403]:
            detail = 'Voice service rejected the key or its permissions. Check your ElevenLabs configuration.'
        if response.status_code in [402, 429]:
            detail = 'Voice quota or rate limit reached. Continue with text.'
        raise HTTPException(502, detail)
    return response


@app.post('/api/voice/transcribe')
async def transcribe(file: UploadFile = File(...)):
    key = voice_key()
    content_type = (file.content_type or '').split(';')[0].strip().lower()
    extensions = {'audio/webm': 'webm', 'audio/mp4': 'm4a', 'audio/ogg': 'ogg', 'audio/wav': 'wav', 'audio/mpeg': 'mp3'}
    if content_type not in extensions:
        raise HTTPException(415, 'Unsupported recording format.')
    audio = await file.read(8 * 1024 * 1024 + 1)
    if len(audio) > 8 * 1024 * 1024 or not audio:
        raise HTTPException(413, 'Record a shorter message (maximum 8 MB).')
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = voice_response(await client.post('https://api.elevenlabs.io/v1/speech-to-text',
                headers={'xi-api-key': key}, data={'model_id': os.getenv('ELEVENLABS_STT_MODEL', 'scribe_v2'), 'language_code': 'eng'},
                files={'file': ('recording.' + extensions[content_type], audio, file.content_type)}))
        text = response.json().get('text', '').strip()
        if not text:
            raise HTTPException(422, 'No speech was recognized. Check your microphone selection in Chrome and its input volume, then record again or type your message.')
        return {'text': text}
    except httpx.RequestError:
        raise HTTPException(504, 'Transcription timed out. Your session is preserved; try again or type.')


@app.post('/api/voice/speak')
async def speak(body: Message):
    key = voice_key()
    voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'JBFqnCBsd6RMkjVDRZzb')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = voice_response(await client.post(f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
                headers={'xi-api-key': key}, json={'text': body.text, 'model_id': os.getenv('ELEVENLABS_TTS_MODEL', 'eleven_flash_v2_5')}))
        return Response(response.content, media_type='audio/mpeg', headers={'Cache-Control': 'no-store'})
    except httpx.RequestError:
        raise HTTPException(504, 'Speech playback timed out. Read the response in the transcript.')
