const $ = id => document.getElementById(id);
const escapeHTML = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let config, session, busy = false, recorder, recordingStream, audio, recordingTimer;
const roles = [['intake','◎','Intake & routing','Understands the issue, finds the right path'],['support','⌘','Troubleshooting','Follows approved support runbooks'],['escalation','↗','Escalation','Brings in a human when it matters'],['quality','✓','Quality review','Checks the outcome and next steps']];
async function api(url, body, method) {
  const options = {method: method || (body === undefined ? 'GET' : 'POST')};
  if (body !== undefined) { if(body instanceof FormData) options.body=body; else {options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body);} }
  const res=await fetch(url, options);
  if(!res.ok){let detail;try{detail=(await res.json()).detail;}catch{}throw Error(typeof detail==='string'?detail:`Request failed (${res.status}). Your session is preserved.`);}
  return res.headers.get('content-type')?.includes('application/json')?res.json():res.blob();
}
function notice(text=''){ $('notice').textContent=text; }
function setBusy(value){busy=value;$('orb').classList.toggle('busy',value);renderControls();}
function renderControls(){
  const active=session&&!session.closed&&['active','ticket_failed'].includes(session.outcome);
  $('start').hidden=!!active; $('start').disabled=busy;
  $('record').hidden=!active; $('record').disabled=busy||!config?.voice_ready;
  $('end').hidden=!session||session.closed; $('end').disabled=busy||recorder?.state==='recording';
  $('message').disabled=!active||busy||recorder?.state==='recording'; $('send').disabled=!active||busy||recorder?.state==='recording';
  $('fault').disabled=!!active||busy;
}
function render(){
  if(!session)return;
  localStorage.setItem('northstar-session',session.id);
  $('session-label').textContent=`SESSION ${session.id.slice(0,8).toUpperCase()}`;
  $('call-status').textContent=session.closed?'Call ended':session.outcome.replaceAll('_',' ');
  $('call-title').textContent=session.outcome==='active'?'You’re in the right place.':session.outcome==='resolved'?'One less thing on your list.':'Your next step is ready.';
  $('call-hint').textContent=session.outcome==='active'?'Record a message, then click stop to send it.':'See the outcome and follow-up below.';
  $('messages').innerHTML=session.messages.map(m=>`<div class="bubble ${m.role==='user'?'user':''}"><small>${m.role==='user'?'YOU':escapeHTML(m.agent?.toUpperCase()+' AGENT')}</small>${escapeHTML(m.text)}</div>`).join('');
  $('messages').scrollTop=$('messages').scrollHeight;
  $('agent-list').innerHTML=roles.map(([id,icon,name,description])=>`<div class="agent ${session.agent===id?'active':''}"><span class="agent-icon">${icon}</span><div><strong>${name}</strong><small>${description}</small></div></div>`).join('');
  $('session-result').hidden=!session.review;
  if(session.review){$('session-result').innerHTML=`<h3>Session outcome</h3>${report(session)}${session.outcome==='ticket_failed'?'<button id="retry-ticket" class="primary result-button">Retry ticket</button>':''}`;
    if($('retry-ticket'))$('retry-ticket').onclick=()=>act(async()=>{session=await api(`/api/sessions/${session.id}/retry-ticket`,{});render();await refreshCounts();});}
  renderControls();
}
function report(s){ const r=s.review;if(!r)return '<p class="muted">Review is generated when the call ends or is escalated.</p>';
 return `<div class="report"><dl><dt>Outcome</dt><dd>${escapeHTML(r.outcome.replaceAll('_',' '))}</dd><dt>Summary</dt><dd>${escapeHTML(r.summary)}</dd><dt>Process checks</dt><dd>${r.employee_matched?'Synthetic employee matched':'Employee not matched'} · ${r.caller_confirmation.length?'Caller confirmed resolution':'No resolution confirmation'}</dd><dt>Findings</dt><dd><ul>${r.process_findings.map(x=>`<li>${escapeHTML(x)}</li>`).join('')}</ul></dd><dt>Follow-up</dt><dd>${r.follow_up_required?'Required':'None required'}${r.follow_up.length?`<ul>${r.follow_up.map(x=>`<li>${escapeHTML(x)}</li>`).join('')}</ul>`:''}</dd><dt>Tool failures</dt><dd>${r.tool_failures.length}</dd></dl><details><summary>Evidence & agent events</summary><pre>${escapeHTML(JSON.stringify({review:r,events:s.events},null,2))}</pre></details></div>`;
}
async function act(fn){if(busy)return;notice();setBusy(true);try{await fn();}catch(e){notice(e.message);}finally{setBusy(false);}}
async function speak(text){if(!$('audio-enabled').checked||!config.voice_ready)return;
  try{if(audio)audio.pause();const blob=await api('/api/voice/speak',{text});const url=URL.createObjectURL(blob);audio=new Audio(url);audio.onended=()=>URL.revokeObjectURL(url);await audio.play();}catch(e){notice(`Response saved. ${e.message}`);}}
async function send(text){if(!text.trim()||!session)return;session=await api(`/api/sessions/${session.id}/messages`,{text});$('message').value='';render();await refreshCounts();await speak(session.messages.at(-1).text);}
$('chat-form').onsubmit=e=>{e.preventDefault();act(()=>send($('message').value));};
$('start').onclick=()=>act(async()=>{session=await api('/api/sessions',{fault:$('fault').value});render();await speak(session.messages[0].text);});
$('end').onclick=()=>act(async()=>{if(audio)audio.pause();session=await api(`/api/sessions/${session.id}/end`,{});render();});
$('copy-identity').onclick=()=>{$('message').value='I am Maya Chen, NS-1001. ';$('message').focus();};
$('audio-enabled').onchange=()=>{if(!$('audio-enabled').checked&&audio)audio.pause();};
$('record').onclick=async()=>{
  if(recorder?.state==='recording'){recorder.stop();return;}
  if(busy)return;
  notice();if(audio)audio.pause();
  try{
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw Error('Recording is unavailable in this browser. Try Chrome on localhost or use text.');
    recordingStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus','audio/webm'].find(x=>MediaRecorder.isTypeSupported(x));
    recorder=new MediaRecorder(recordingStream,mime?{mimeType:mime}:{});let chunks=[];
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onstop=()=>{
      clearTimeout(recordingTimer);recordingStream.getTracks().forEach(t=>t.stop());$('orb').classList.remove('recording');$('record').textContent='● Record message';
      const actualType=recorder.mimeType||chunks[0]?.type||'audio/webm';
      const baseType=actualType.split(';')[0];
      const extension={'audio/webm':'webm','audio/mp4':'m4a','audio/ogg':'ogg','audio/wav':'wav'}[baseType]||'webm';
      const blob=new Blob(chunks,{type:actualType});
      act(async()=>{
        if(!blob.size)throw Error('The microphone produced an empty recording. Choose another input and try again.');
        const form=new FormData();form.append('file',blob,`recording.${extension}`);
        notice('Transcribing your message…');
        const result=await api('/api/voice/transcribe',form);$('message').value=result.text;notice();await send(result.text);
      });
    };
    recorder.onerror=()=>{notice('Recording failed. Choose another microphone or use text.');clearTimeout(recordingTimer);recordingStream.getTracks().forEach(t=>t.stop());renderControls();};
    recorder.start();renderControls();$('orb').classList.add('recording');$('record').textContent='■ Stop & send';$('end').disabled=true;
    recordingTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},45000);
  }catch(e){recordingStream?.getTracks().forEach(t=>t.stop());notice(e.name==='NotAllowedError'?'Microphone permission denied. Allow microphone access or use text.':e.message);renderControls();}
};
async function refreshCounts(){const tickets=await api('/api/tickets');$('pending-count').textContent=tickets.filter(t=>t.status==='pending').length;}
async function showTickets(){
  const tickets=await api('/api/tickets');
  $('tickets').innerHTML=tickets.length?tickets.map(t=>`<article class="ticket"><div class="section-title"><h3>${escapeHTML(t.id)}</h3><span class="badge">${escapeHTML(t.status)}</span></div><p>${escapeHTML(t.payload.summary)}</p><p><strong>${escapeHTML(t.payload.employee.name||'Unverified employee')}</strong> · ${escapeHTML(t.payload.category)}<br>Steps attempted: ${t.payload.steps_attempted}</p>${t.status==='pending'?`<label>Reviewer name<input data-name="${t.session_id}" placeholder="Your name" maxlength="100"></label><label>Decision notes<textarea data-note="${t.session_id}" placeholder="Explain your decision and next action…" maxlength="1000"></textarea></label><div class="decision-buttons">${t.payload.verified&&t.payload.category==='access'?`<button class="primary" data-decision="approved" data-id="${t.session_id}">Approve request</button>`:''}<button class="secondary" data-decision="accepted" data-id="${t.session_id}">Accept handoff</button><button class="secondary" data-decision="rejected" data-id="${t.session_id}">Reject</button></div><p class="error" data-error="${t.session_id}" role="status"></p>`:`<p>Reviewer: ${escapeHTML(t.decision?.reviewer)}<br>${escapeHTML(t.decision?.note)}</p>`}</article>`).join(''):'<div class="panel"><h3>All clear for now.</h3><p class="muted">Requests that need a person will appear here with their full context.</p></div>';
  document.querySelectorAll('[data-decision]').forEach(button=>button.onclick=async()=>{
    const sid=button.dataset.id;const reviewer=document.querySelector(`[data-name="${sid}"]`).value.trim();const note=document.querySelector(`[data-note="${sid}"]`).value.trim();const error=document.querySelector(`[data-error="${sid}"]`);
    if(!reviewer||note.length<3){error.textContent='Add your name and a short decision note.';return;}
    button.disabled=true;try{const updated=await api(`/api/sessions/${sid}/decision`,{decision:button.dataset.decision,reviewer,note});if(session?.id===sid){session=updated;render();}await showTickets();await refreshCounts();}catch(e){error.textContent=e.message;button.disabled=false;}
  });
}
async function showHistory(){
 const sessions=await api('/api/sessions');
 $('history').innerHTML=sessions.length?sessions.map(s=>`<article class="history-item"><div class="section-title"><h3>${escapeHTML(config.runbooks[s.category]?.title||'Intake session')}</h3><span class="badge">${escapeHTML(s.outcome.replaceAll('_',' '))}</span></div><p>${escapeHTML(s.employee?.name||'Unverified employee')} · ${s.id.slice(0,8).toUpperCase()} · ${s.mode==='claude'?'Claude':'Scripted demo'}</p>${report(s)}<details class="report"><summary>Conversation transcript</summary>${s.messages.map(m=>`<p><strong>${escapeHTML(m.role)}:</strong> ${escapeHTML(m.text)}</p>`).join('')}</details><div class="history-actions"><button class="secondary" data-open="${s.id}">Open session</button><button class="secondary" data-export="${s.id}">Export JSON</button></div></article>`).join(''):'<div class="panel"><h3>Your first session starts the story.</h3><p class="muted">Complete a support call to see its quality review here.</p></div>';
 document.querySelectorAll('[data-open]').forEach(b=>b.onclick=async()=>{session=sessions.find(s=>s.id===b.dataset.open);render();await switchView('support');});
 document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>{const s=sessions.find(s=>s.id===b.dataset.export);const url=URL.createObjectURL(new Blob([JSON.stringify(s,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`northstar-${s.id.slice(0,8)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
}
async function switchView(view){
 document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==view+'-view');
 document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
 $('breadcrumb').textContent={support:'Support desk',review:'Human review',history:'Session reviews'}[view];
 try{if(view==='review')await showTickets();if(view==='history')await showHistory();await refreshCounts();}catch(e){const target=view==='review'?$('tickets'):view==='history'?$('history'):$('notice');target.textContent=e.message;}
}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>switchView(b.dataset.view));
window.addEventListener('pagehide',()=>{recordingStream?.getTracks().forEach(t=>t.stop());if(session&&!session.closed)navigator.sendBeacon(`/api/sessions/${session.id}/end`,new Blob(['{}'],{type:'application/json'}));});
(async()=>{try{config=await api('/api/config');$('mode').textContent=config.mode==='claude'?'Claude agents configured':'Scripted demo · no LLM';$('agent-list').innerHTML=roles.map(([id,icon,name,desc])=>`<div class="agent"><span class="agent-icon">${icon}</span><div><strong>${name}</strong><small>${desc}</small></div></div>`).join('');
 $('scenarios').innerHTML=Object.entries(config.runbooks).map(([key,b])=>`<button class="scenario" data-case="${key}">${escapeHTML(b.title)}<span>${key==='access'?'Human review':'↗'}</span></button>`).join('');
 document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>{if(!session||session.closed||session.outcome!=='active'){notice('Start a new session first, then select a scenario.');return;}$('message').value=`I am Maya Chen, NS-1001. ${config.runbooks[b.dataset.case].example}`;$('message').focus();});
 const saved=localStorage.getItem('northstar-session');if(saved){try{session=await api(`/api/sessions/${saved}`);render();}catch{localStorage.removeItem('northstar-session');}}
 if(!config.voice_ready)notice('Voice is not configured yet. Add your ElevenLabs key to .env and restart. You can test every workflow using text.');
 renderControls();await refreshCounts();
}catch(e){notice(`Could not connect to the backend: ${e.message}`);}})();
