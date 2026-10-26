const CSRF = document.querySelector('meta[name="csrf"]')?.content || '';

function toggle(id){
  const el = document.getElementById(id);
  if (el) el.classList.toggle('hidden');
}

async function postForm(url, data){
  const body = new URLSearchParams(data || {});
  const res = await fetch(url, {
    method:'POST',
    headers:{'X-CSRF':CSRF,'X-Requested-With':'fetch',
             'Content-Type':'application/x-www-form-urlencoded'},
    body: body.toString(),
  });
  try { return await res.json(); } catch(e){ return {ok:res.ok}; }
}

async function playOnDevice(audioId){
  const r = await postForm('/play', {audio_id: audioId});
  if (r && r.message) flash(r.message, r.ok);
  refreshStatus();
}

async function stopPlayback(){
  await postForm('/stop', {});
  refreshStatus();
}

function flash(msg, ok){
  const d = document.createElement('div');
  d.className = 'flash ' + (ok ? 'ok' : 'error');
  d.textContent = msg;
  const main = document.querySelector('main.container');
  if (main){ main.prepend(d); setTimeout(()=>d.remove(), 4000); }
}

/* ---- live now-playing status ---- */
function fmt(sec){
  if (sec == null) return '';
  const m = Math.floor(sec/60), s = sec%60;
  return m + ':' + String(s).padStart(2,'0') + ' left';
}
async function refreshStatus(){
  try{
    const res = await fetch('/api/status', {headers:{'X-Requested-With':'fetch'}});
    if (!res.ok) return;
    const st = await res.json();
    const bar = document.getElementById('nowplaying');
    if (!bar) return;
    if (st.playing){
      bar.classList.add('on');
      document.getElementById('np-title').textContent = st.title || '';
      document.getElementById('np-sub').textContent = st.trigger || '';
      document.getElementById('np-remaining').textContent = fmt(st.remaining);
    } else {
      bar.classList.remove('on');
    }
    const state = document.getElementById('stat-state');
    if (state) state.textContent = st.playing ? 'Playing' : 'Idle';

    // device clock sync
    if (st.server_epoch){ clockOffsetMs = st.server_epoch*1000 - Date.now(); }
    if (st.timezone){ clockTz = st.timezone; }
    // master volume sync (don't fight the user while dragging)
    if (typeof st.master_volume === 'number' && !volDragging){
      setVolumeUI(st.master_volume, st.muted);
    }
  }catch(e){}
}

/* ---- live device clock ---- */
let clockOffsetMs = 0, clockTz = null;
function tickClock(){
  const el = document.getElementById('dev-clock');
  if (!el) return;
  const d = new Date(Date.now() + clockOffsetMs);
  const opts = {weekday:'short', day:'2-digit', month:'short',
                hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false};
  if (clockTz) opts.timeZone = clockTz;
  try { el.textContent = d.toLocaleString('en-GB', opts); }
  catch(e){ el.textContent = d.toLocaleString('en-GB'); }
}

/* ---- master volume + mute ---- */
let volDragging = false, volCommitTimer = null;
function setVolumeUI(value, muted){
  const range = document.getElementById('vol-range');
  const pct = document.getElementById('vol-pct');
  const btn = document.getElementById('mute-btn');
  if (range && !volDragging) range.value = value;
  if (pct) pct.textContent = value + '%';
  if (btn){
    btn.textContent = muted ? '🔇 Muted' : '🔊 Mute';
    btn.classList.toggle('danger', !!muted);
    btn.classList.toggle('ghost', !muted);
  }
}
function onVolInput(v){            // dragging: update label only, no server/tone
  volDragging = true;
  const pct = document.getElementById('vol-pct');
  if (pct) pct.textContent = v + '%';
}
function onVolCommit(v){           // release: save + play tone
  volDragging = false;
  sendVolume(parseInt(v, 10));
}
function stepVolume(delta){
  const range = document.getElementById('vol-range');
  let v = Math.max(0, Math.min(100, parseInt(range.value, 10) + delta));
  range.value = v;
  setVolumeUI(v, false);
  sendVolume(v);
}
async function sendVolume(v){
  clearTimeout(volCommitTimer);
  volCommitTimer = setTimeout(async ()=>{
    const r = await postForm('/volume/set', {value: v});
    if (r && typeof r.master_volume === 'number') setVolumeUI(r.master_volume, r.muted);
  }, 120);
}
async function toggleMute(){
  const r = await postForm('/volume/mute', {});
  if (r) setVolumeUI(r.master_volume, r.muted);
}

/* ---- youtube download ---- */
let ytTimer = null;
async function startYoutube(){
  const url = document.getElementById('yt-url').value.trim();
  const errBox = document.getElementById('yt-error');
  errBox.classList.add('hidden');
  document.getElementById('yt-done').classList.add('hidden');
  if (!url.startsWith('http')){ errBox.textContent='Enter a valid URL.'; errBox.classList.remove('hidden'); return; }
  const kind = (document.getElementById('yt-kind') || {}).value || 'audio';
  const go = document.getElementById('yt-go'); go.disabled = true;
  const status = document.getElementById('yt-status');
  status.classList.remove('hidden');
  document.getElementById('yt-msg').textContent = 'Starting…';
  const r = await postForm('/youtube/download', {url, kind});
  if (!r.ok){ status.classList.add('hidden'); go.disabled=false; errBox.textContent=r.message||'Failed to start.'; errBox.classList.remove('hidden'); return; }
  pollYoutube(r.job_id);
}

function pollYoutube(jobId){
  clearInterval(ytTimer);
  ytTimer = setInterval(async ()=>{
    const res = await fetch('/youtube/status/'+jobId, {headers:{'X-Requested-With':'fetch'}});
    if (!res.ok) return;
    const j = await res.json();
    document.getElementById('yt-msg').textContent = j.message || j.stage;
    if (j.stage === 'done'){
      clearInterval(ytTimer);
      document.getElementById('yt-status').classList.add('hidden');
      document.getElementById('yt-go').disabled = false;
      document.getElementById('yt-title').textContent = j.title || 'Media';
      const au = document.getElementById('yt-audio');
      const vid = document.getElementById('yt-video');
      const src = '/audio/'+j.audio_id;
      if (j.kind === 'video'){
        vid.src = src; vid.classList.remove('hidden'); au.classList.add('hidden'); au.removeAttribute('src');
        document.getElementById('yt-play').textContent = '📺 Play on TV';
      } else {
        au.src = src; au.classList.remove('hidden'); vid.classList.add('hidden'); vid.removeAttribute('src');
        document.getElementById('yt-play').textContent = '▶ Play on soundbar';
      }
      document.getElementById('yt-play').onclick = ()=>playOnDevice(j.audio_id);
      document.getElementById('yt-done').classList.remove('hidden');
    } else if (j.stage === 'error'){
      clearInterval(ytTimer);
      document.getElementById('yt-status').classList.add('hidden');
      document.getElementById('yt-go').disabled = false;
      const e = document.getElementById('yt-error');
      e.textContent = 'Download failed: ' + (j.message||'unknown error');
      e.classList.remove('hidden');
    }
  }, 1200);
}

document.addEventListener('DOMContentLoaded', ()=>{
  if (document.getElementById('nowplaying')){
    refreshStatus();
    setInterval(refreshStatus, 3000);
  }
  if (document.getElementById('dev-clock')){
    tickClock();
    setInterval(tickClock, 1000);
  }
});
