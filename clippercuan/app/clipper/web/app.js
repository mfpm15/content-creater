/* ClipperCuan Studio — UI lokal. Vanilla JS. */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const view = $('#view');
let INFO = null, SETTINGS = null, HEALTH = null, pollT = null;

/* ---------------- util ---------------- */
async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.body && !(o.body instanceof FormData)) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(o.body); }
  const r = await fetch(path, o);
  const isJson = (r.headers.get('content-type') || '').includes('json');
  const data = isJson ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
}
let toastT;
function toast(msg, bad = false) { const t = $('#toast'); t.textContent = msg; t.classList.toggle('bad', bad); t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), bad ? 6000 : 2800); }
const fmt = s => { s = Math.max(0, +s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`; };
const tpl = id => document.importNode($('#' + id).content, true);
const store = { get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };
const merge = (a, b) => { const o = structuredClone(a); for (const [k, v] of Object.entries(b || {})) o[k] = v && typeof v === 'object' && !Array.isArray(v) && o[k] && typeof o[k] === 'object' ? merge(o[k], v) : v; return o; };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function chipGroup(box, val, cb, attr = 'v') { $$('button', box).forEach(b => { b.type = 'button'; b.classList.toggle('on', b.dataset[attr] === val); b.onclick = () => { $$('button', box).forEach(x => x.classList.toggle('on', x === b)); cb(b.dataset[attr]); }; }); }
const llmOn = () => SETTINGS && HEALTH?.llm?.enabled && (SETTINGS.llm.model_titles || SETTINGS.llm.model_moments);
function paintAiHealth() {
  const box = $('#aiHealth'); if (!box || !HEALTH) return;
  const active = HEALTH.llm.enabled;
  box.className = 'ai-health ' + (active ? 'ready' : 'fallback');
  box.title = active ? `9Router terhubung untuk workflow ini. Model: ${HEALTH.llm.model}` : '9Router tidak diaktifkan. Highlight tetap berjalan memakai analisis lokal.';
  box.innerHTML = `<span class="status-dot"></span><span><b>${active ? 'AI 9Router aktif' : 'Mode lokal'}</b><small>${active ? esc(HEALTH.llm.model) : 'fallback aman tanpa AI eksternal'}</small></span>`;
}
function notify(title, body) {
  try { if ('Notification' in window && Notification.permission === 'granted' && document.hidden) new Notification(title, { body }); } catch {}
  try { const a = new AudioContext(), o = a.createOscillator(), g = a.createGain(); o.frequency.value = 880; g.gain.value = .06; o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + .18); } catch {}
}

/* ---------------- router ---------------- */
async function route() {
  clearInterval(pollT);
  const h = location.hash.replace(/^#\/?/, '') || 'new';
  const [page, id] = h.split('/');
  $$('.side nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === page || (page === 'p' && a.dataset.nav === 'history')));
  if (!INFO) { [INFO, SETTINGS, HEALTH] = await Promise.all([api('/api/info'), api('/api/settings'), api('/api/health')]); $('#sideFoot').textContent = 'Data lokal siap'; paintAiHealth(); }
  if (page === 'p' && id) return pageProject(id);
  const pages = { history: pageHistory, captions: pageCaptions, settings: pageSettings, templates: pageTemplates, system: pageSystem, help: pageHelp, agent: pageAgent };
  return (pages[page] || (() => pageNew()))();
}
addEventListener('hashchange', route);
// lencana "sedang diproses" di menu Riwayat
async function badge() { try { const l = await api('/api/projects'); const n = l.filter(p => ['queued', 'running'].includes(p.status)).length; const b = $('#runBadge'); b.hidden = !n; b.textContent = n; } catch {} }
setInterval(badge, 4000); badge();

/* ================= PROYEK BARU ================= */
async function pageNew(override) {
  view.replaceChildren(tpl('tpl-new'));
  const templates = await api('/api/templates').catch(() => ({}));
  const cfg = merge(INFO.defaults, override || store.get('lastSettings', {}));
  let srcMode = store.get('srcMode', 'link'), upload = null;

  // template
  const sel = $('#tplSel');
  Object.keys(templates).forEach(n => sel.append(new Option(n, n)));
  if (override && override.__name) sel.value = override.__name;
  sel.onchange = () => pageNew(sel.value ? { ...templates[sel.value], __name: sel.value } : null);
  $('#tplSave').onclick = async () => {
    const name = prompt('Nama template (mis. "Podcast kuning", "Gaming split"):', sel.value || '');
    if (!name) return;
    try { await api('/api/templates', { method: 'POST', body: { name, settings: collect() } }); toast('Template disimpan'); pageNew({ ...collect(), __name: name.trim().slice(0, 40) }); } catch (e) { toast(e.message, true); }
  };

  const setSrc = m => { srcMode = m; store.set('srcMode', m); $('#srcLink').hidden = m !== 'link'; $('#srcFile').hidden = m !== 'file'; };
  chipGroup($('#srcTabs'), srcMode, setSrc, 'src'); setSrc(srcMode);
  const links = () => $('#url').value.split(/\s+/).map(s => s.trim()).filter(Boolean);
  $('#url').oninput = () => { const n = links().length; $('#urlCount').textContent = n > 1 ? `${n} link → ${n} proyek akan dibuat dan diproses berurutan` : ''; };

  // unggah file
  const drop = $('#drop'), fileIn = $('#file');
  const doUpload = f => {
    if (!f) return;
    $('#fileName').textContent = f.name + ' · ' + (f.size / 1048576).toFixed(1) + ' MB';
    const bar = $('#upBar'); bar.hidden = false; upload = null; $('#start').disabled = true;
    const fd = new FormData(); fd.append('file', f);
    const x = new XMLHttpRequest(); x.open('POST', '/api/upload');
    x.upload.onprogress = e => { if (e.lengthComputable) $('i', bar).style.width = (e.loaded / e.total * 100) + '%'; };
    x.onload = () => { $('#start').disabled = false; if (x.status === 200) { upload = JSON.parse(x.responseText); toast('File siap'); } else toast('Upload gagal: ' + x.responseText, true); };
    x.onerror = () => { $('#start').disabled = false; toast('Upload gagal', true); };
    x.send(fd);
  };
  fileIn.onchange = () => doUpload(fileIn.files[0]);
  ['dragenter', 'dragover'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', ev => doUpload(ev.dataTransfer.files[0]));

  // mode, durasi, klip
  let uiMode = store.get('clipperUiMode', 'basic');
  const paintMode = () => { document.body.dataset.uiMode = uiMode; $$('#uiMode button').forEach(b => b.classList.toggle('on', b.dataset.mode === uiMode)); };
  $$('#uiMode button').forEach(b => b.onclick = () => { uiMode = b.dataset.mode; store.set('clipperUiMode', uiMode); paintMode(); }); paintMode();
  let contentProfile = cfg.content_profile || 'auto';
  chipGroup($('#contentProfile'), contentProfile, v => contentProfile = v);
  let durationPreset = cfg.duration_preset || 'auto';
  const durationText = { auto: 'Auto: AI memilih rentang setelah transkripsi tanpa memotong kalimat.', '15-25': '15–25 detik: ujaran padat dan payoff cepat.', '25-40': '25–40 detik: konteks sedang sebelum payoff.', '40-60': '40–60 detik: penjelasan lebih utuh.' };
  chipGroup($('#durationPreset'), durationPreset, v => { durationPreset = v; const [a, b] = v === 'auto' ? [15, 60] : v.split('-').map(Number); $('#min_sec').value = a; $('#max_sec').value = b; $('#durationEstimate').textContent = durationText[v]; });
  $('#durationEstimate').textContent = durationText[durationPreset] || durationText.auto;
  ['candidate_count', 'clip_count', 'min_sec', 'max_sec', 'language', 'model', 'transcriber'].forEach(k => $('#' + k).value = cfg[k]);
  $('#translate_en').checked = !!cfg.translate_en; $('#cut_silence').checked = !!cfg.cut_silence;
  const aiActive = !!HEALTH?.llm?.enabled;
  $('#llmRow').hidden = !aiActive; $('#localFallback').hidden = aiActive; $('#llmModel').textContent = SETTINGS.llm.model_moments;
  $('#use_llm').checked = aiActive && cfg.use_llm !== false;

  // format
  let layout = cfg.layout;
  const syncLayout = () => { $('#smartRow').hidden = !['portrait', 'square'].includes(layout); $('#splitRow').hidden = layout !== 'split'; };
  chipGroup($('#layouts'), layout, l => { layout = l; syncLayout(); }, 'l'); syncLayout();
  $('#smart_crop').checked = cfg.smart_crop;
  const f0 = cfg.split.face, guess = (f0[0] > .4 ? 'r' : 'l'), gy = (f0[1] > .4 ? 'b' : 't');
  let facePos = { tl: 'tl', tr: 'tr', bl: 'bl', br: 'br' }[gy + guess] || 'br';
  chipGroup($('#facePos'), facePos, v => facePos = v, 'f');
  $('#faceSize').value = Math.round(cfg.split.face[2] * 100);
  $('#faceRatio').value = Math.round(cfg.split.face_ratio * 100);

  // caption
  const cap = cfg.caption;
  let capPreset = cap.preset || 'bold-viral';
  $('#cap_font').innerHTML = INFO.fonts.map(f => `<option>${esc(f)}</option>`).join('');
  let capStyle = cap.style;
  const capCard = $('#capCard');
  $('#cap_enabled').checked = cap.enabled; capCard.classList.toggle('off', !cap.enabled);
  $('#cap_enabled').onchange = e => capCard.classList.toggle('off', !e.target.checked);
  $('#cap_font').value = cap.font; $('#cap_position').value = cap.position; $('#cap_color').value = cap.color; $('#cap_highlight').value = cap.highlight;
  $('#cap_wpl').value = cap.words_per_line; $('#cap_size').value = cap.size; $('#cap_upper').checked = cap.uppercase; $('#cap_pop').checked = cap.animation === 'pop';
  const pv = () => {
    const p = $('#capPreview'), hl = $('#cap_highlight').value, col = $('#cap_color').value;
    p.style.textTransform = $('#cap_upper').checked ? 'uppercase' : 'none';
    p.style.fontFamily = $('#cap_font').value.includes('Georgia') ? 'Georgia,serif' : 'inherit';
    p.style.fontSize = (+$('#cap_size').value / 82 * 22) + 'px';
    $$('.pv-w', p).forEach(w => { const on = w.classList.contains('on'); w.style.color = on ? (capStyle === 'box' ? '#000' : hl) : col; w.style.background = on && capStyle === 'box' ? hl : 'transparent'; w.hidden = capStyle === 'wbw' && !on; });
  };
  chipGroup($('#capStyle'), capStyle, v => { capStyle = v; pv(); });
  const useCapPreset = v => { capPreset = v; const presets = { clean: ['clean', false, false, 4], 'bold-viral': ['box', true, true, 3], minimal: ['clean', false, false, 3], karaoke: ['karaoke', false, true, 4] }; const p = presets[v]; capStyle = p[0]; $('#cap_upper').checked = p[1]; $('#cap_pop').checked = p[2]; $('#cap_wpl').value = p[3]; chipGroup($('#capStyle'), capStyle, x => { capStyle = x; pv(); }); pv(); };
  chipGroup($('#capPreset'), capPreset, useCapPreset);
  ['cap_color', 'cap_highlight', 'cap_upper', 'cap_font', 'cap_size'].forEach(k => $('#' + k).addEventListener('input', pv)); pv();

  // judul & watermark
  let ttlPreset = cfg.title.preset, wmPos = cfg.watermark.position, wmImage = '';
  $('#ttl_enabled').checked = cfg.title.enabled; $('#ttl_duration').value = cfg.title.duration;
  chipGroup($('#ttlPreset'), ttlPreset, v => ttlPreset = v);
  $('#wm_enabled').checked = cfg.watermark.enabled; $('#wm_text').value = cfg.watermark.text; $('#wm_opacity').value = Math.round(cfg.watermark.opacity * 100);
  chipGroup($('#wmPos'), wmPos, v => wmPos = v);
  $('#wm_file').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    try { const r = await api('/api/upload', { method: 'POST', body: fd }); wmImage = r.path; $('#wmName').textContent = f.name; $('#wm_enabled').checked = true; toast('Logo watermark siap'); } catch (err) { toast(err.message, true); }
  };

  // efek visual
  const fxBind = (sw, row) => { const f = () => $(row).classList.toggle('dim', !$(sw).checked); $(sw).addEventListener('change', f); f(); };
  $('#emoji_on').checked = !!cfg.emoji.enabled; $('#emoji_size').value = Math.round((cfg.emoji.size || 1) * 100);
  $('#pb_on').checked = !!cfg.progress_bar.enabled; $('#pb_color').value = cfg.progress_bar.color; $('#pb_pos').value = cfg.progress_bar.position;
  $('#cta_on').checked = !!cfg.cta.enabled; $('#cta_text').value = cfg.cta.text; $('#cta_dur').value = cfg.cta.duration;
  fxBind('#emoji_on', '#emojiSizeRow'); fxBind('#pb_on', '#pbRow'); fxBind('#cta_on', '#ctaRow');

  // musik latar
  $('#mu_on').checked = !!cfg.music.enabled; $('#mu_vol').value = Math.round(cfg.music.volume * 100); $('#mu_duck').checked = cfg.music.duck !== false;
  fxBind('#mu_on', '#muBody');
  const loadMusic = async (selectFile) => {
    const list = await api('/api/music').catch(() => []);
    const selM = $('#mu_file');
    selM.innerHTML = list.length ? list.map(m => `<option value="${esc(m.file)}">${esc(m.name)}</option>`).join('') : '<option value="">— belum ada musik, unggah dulu —</option>';
    const want = selectFile || cfg.music.file;
    if (want && list.some(m => m.file === want)) selM.value = want;
    const prev = $('#mu_prev'); prev.hidden = !selM.value; if (selM.value) prev.src = '/api/music/play?file=' + encodeURIComponent(selM.value);
  };
  $('#mu_file').onchange = () => { const v = $('#mu_file').value; $('#mu_prev').hidden = !v; if (v) $('#mu_prev').src = '/api/music/play?file=' + encodeURIComponent(v); };
  $('#mu_up').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    try { const r = await api('/api/music', { method: 'POST', body: fd }); await loadMusic(r.file); $('#mu_on').checked = true; $('#mu_on').dispatchEvent(new Event('change')); toast('Musik ditambahkan'); } catch (err) { toast(err.message, true); }
  };
  loadMusic();

  function collect() {
    const fs = +$('#faceSize').value / 100, pos = { tl: [0, 0], tr: [1 - fs, 0], bl: [0, 1 - fs], br: [1 - fs, 1 - fs] }[facePos];
    return {
      content_profile: contentProfile, candidate_count: +$('#candidate_count').value, auto_render: false,
      clip_count: +$('#clip_count').value, duration_preset: durationPreset, min_sec: +$('#min_sec').value, max_sec: +$('#max_sec').value, language: $('#language').value, model: $('#model').value, transcriber: $('#transcriber').value,
      translate_en: $('#translate_en').checked, cut_silence: $('#cut_silence').checked, use_llm: $('#use_llm').checked, layout, smart_crop: $('#smart_crop').checked,
      split: { face: [pos[0], pos[1], fs, fs], game: [0, 0, 1, 1], face_ratio: +$('#faceRatio').value / 100 },
      caption: { enabled: $('#cap_enabled').checked, preset: capPreset, style: capStyle, font: $('#cap_font').value, size: +$('#cap_size').value, color: $('#cap_color').value, highlight: $('#cap_highlight').value, uppercase: $('#cap_upper').checked, words_per_line: +$('#cap_wpl').value, position: $('#cap_position').value, safe_area: .12, max_chars: 24, animation: $('#cap_pop').checked ? 'pop' : 'none' },
      title: { enabled: $('#ttl_enabled').checked, preset: ttlPreset, duration: +$('#ttl_duration').value, size: cfg.title.size },
      watermark: { enabled: $('#wm_enabled').checked, text: $('#wm_text').value, image: wmImage, position: wmPos, opacity: +$('#wm_opacity').value / 100, size: cfg.watermark.size },
      emoji: { enabled: $('#emoji_on').checked, size: +$('#emoji_size').value / 100 },
      progress_bar: { enabled: $('#pb_on').checked, color: $('#pb_color').value, position: $('#pb_pos').value, height: cfg.progress_bar.height },
      cta: { enabled: $('#cta_on').checked, text: $('#cta_text').value, duration: +$('#cta_dur').value || 3 },
      music: { enabled: $('#mu_on').checked && !!$('#mu_file').value, file: $('#mu_file').value, volume: +$('#mu_vol').value / 100, duck: $('#mu_duck').checked },
    };
  }

  $('#start').onclick = async () => {
    let sources = [];
    if (srcMode === 'link') { sources = links(); if (!sources.length || sources.some(s => !/^https?:\/\//i.test(s))) return toast('Tempel link video yang valid (diawali https://), satu per baris', true); }
    else { if (!upload) return toast('Pilih file video dulu', true); sources = [upload.id]; }
    const settings = collect();
    if (settings.min_sec >= settings.max_sec) return toast('Durasi minimum harus lebih kecil dari maksimum', true);
    if (settings.candidate_count < 5) return toast('Jumlah kandidat minimal 5', true);
    store.set('lastSettings', { ...settings, watermark: { ...settings.watermark, image: '' } });
    try { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); } catch {}
    const start = $('#start'); start.disabled = true; start.classList.add('is-loading'); start.querySelector('span').textContent = 'Menyiapkan proyek…';
    try {
      let last;
      for (const source of sources) last = await api('/api/projects', { method: 'POST', body: { source, settings } });
      location.hash = sources.length > 1 ? '#/history' : '#/p/' + last.id;
      if (sources.length > 1) toast(`${sources.length} proyek masuk antrean`);
    } catch (e) { toast(e.message, true); start.disabled = false; start.classList.remove('is-loading'); start.querySelector('span').textContent = 'Generate Candidates'; }
  };
}

/* ================= PROYEK ================= */
async function pageProject(pid) {
  view.replaceChildren(tpl('tpl-project'));
  const cards = new Map();
  let P = null, prevStatus = null, eta = { t: 0, p: 0 };
  $('#pFolder').onclick = () => api(`/api/projects/${pid}/open-folder`, { method: 'POST' }).then(r => toast('Folder: ' + r.path)).catch(e => toast(e.message, true));
  $('#pCancel').onclick = () => api(`/api/projects/${pid}/cancel`, { method: 'POST' }).then(() => toast('Membatalkan…'));
  $('#pRetry').onclick = () => api(`/api/projects/${pid}/retry`, { method: 'POST' }).then(load);
  $('#pStyleAll').onclick = () => styleDialog(P, load);
  $('#pAdd').onclick = () => addClipDialog(P, load);
  $('#pSplit').onclick = () => splitDialog(P, load);
  $('#pZip').href = `/api/projects/${pid}/zip`;
  $('#pManifest').href = `/api/projects/${pid}/candidates/manifest`;
  $('#pSort').value = store.get('sort', 'score');
  $('#pSort').onchange = e => { store.set('sort', e.target.value); order(); };
  $('#pGoal').onchange = order; $('#pSearch').oninput = order;
  $('#pTop3').onclick = () => api(`/api/projects/${pid}/candidates/top/3`, { method: 'POST' }).then(load).catch(e => toast(e.message, true));
  $('#pTop5').onclick = () => api(`/api/projects/${pid}/candidates/top/5`, { method: 'POST' }).then(load).catch(e => toast(e.message, true));
  $('#pRenderSelected').onclick = () => api(`/api/projects/${pid}/batch-render`, { method: 'POST', body: { ids: [] } }).then(load).catch(e => toast(e.message, true));
  $('#pRerank').onclick = () => api(`/api/projects/${pid}/rerank`, { method: 'POST', body: { settings: {} } }).then(load).catch(e => toast(e.message, true));
  const order = () => {
    if (!P) return;
    const key = $('#pSort').value, goal = $('#pGoal').value, q = $('#pSearch').value.toLowerCase();
    const goalIds = P.rankings?.[goal] || [];
    [...(P.candidates || P.clips)].filter(c => !q || `${c.title} ${c.transcript_excerpt || c.text} ${c.topic_cluster}`.toLowerCase().includes(q))
      .sort((a, b) => key === 'time' ? a.start - b.start : key === 'duration' ? b.duration - a.duration : key === 'cluster' ? String(a.topic_cluster).localeCompare(String(b.topic_cluster)) : goalIds.indexOf(a.id) - goalIds.indexOf(b.id))
      .forEach(c => cards.get(c.id) && $('#pClips').append(cards.get(c.id).el));
  };

  async function load() {
    try { P = await api('/api/projects/' + pid); } catch (e) { view.innerHTML = `<section class="page"><div class="empty">${esc(e.message)}</div></section>`; clearInterval(pollT); return; }
    $('#pTitle').textContent = P.title; $('#pSource').textContent = P.source.includes('uploads') ? 'File unggahan' : P.source;
    const st = $('#pStatus'); st.className = 'card status ' + P.status;
    let etaTxt = '';
    if (P.status === 'running' && P.progress > 0.02) {
      const now = Date.now();
      if (!eta.t) eta = { t: now, p: P.progress };
      else if (P.progress > eta.p + 0.01) { const rate = (P.progress - eta.p) / (now - eta.t); const left = (1 - P.progress) / rate / 1000; if (isFinite(left)) etaTxt = ` · sisa ±${fmt(left)}`; }
    }
    $('#pMsg').textContent = P.message; $('#pPct').textContent = Math.round(P.progress * 100) + '%' + etaTxt; $('#pBar').style.width = P.progress * 100 + '%';
    $('#pCancel').hidden = !['queued', 'running'].includes(P.status);
    $('#pRetry').hidden = !['error', 'cancelled'].includes(P.status);
    const warn = [P.asr_warning, P.llm_warning].filter(Boolean).join(' · ');
    $('#pWarn').hidden = !warn; $('#pWarn').textContent = warn;
    $('#pErr').hidden = !P.error; if (P.error) $('#pErr pre').textContent = P.error;
    P.clips = P.candidates || P.clips || [];
    $('#pTools').hidden = !P.clips.length;
    const empty = $('.result-empty', $('#pClips')); if (empty) empty.hidden = !!P.clips.length;
    $('#pSplit').hidden = P.settings.layout !== 'split' || !P.media;
    $('#pZip').toggleAttribute('disabled', !P.clips.some(c => c.status === 'done'));
    if (P.media) $('#pMeta').textContent = `${P.clips.length} klip · sumber ${fmt(P.media.duration)} · ${P.media.width}×${P.media.height}` + (P.language ? ` · bahasa: ${P.language}` : '') + (P.transcript_source ? ` · subtitle: ${({ 'youtube-manual': 'YouTube (manual)', 'youtube-auto': 'YouTube (otomatis)', api: 'API cloud', 'whisper-lokal': 'Whisper lokal' })[P.transcript_source] || P.transcript_source}` : '') + (P.engine ? ` · pemilih: ${P.engine}` : '') + (P.duration_estimate ? ` · durasi ${P.duration_estimate.min}–${P.duration_estimate.max} dtk: ${P.duration_estimate.reason}` : '');
    const ready = P.viral_readiness ?? (P.clips.length ? Math.round(P.clips.reduce((a, c) => a + (c.readiness || c.score || 0), 0) / P.clips.length) : null);
    $('#pReadiness').hidden = ready == null; if (ready != null) { $('#pReadyScore').textContent = ready + '/100'; $('#pReadyBreakdown').textContent = ready >= 75 ? 'Siap direview untuk publikasi' : ready >= 55 ? 'Perlu review hook, ending, dan framing' : 'Perlu revisi sebelum publikasi'; }
    const ids = new Set(P.clips.map(c => c.id));
    for (const [id, card] of cards) if (!ids.has(id)) { card.el.remove(); cards.delete(id); }
    let added = false;
    for (const c of P.clips) { if (!cards.has(c.id)) { const n = clipCard(P, c, load); cards.set(c.id, n); $('#pClips').append(n.el); added = true; } cards.get(c.id).update(P, c); }
    if (added) order();
    if (prevStatus && prevStatus !== 'done' && P.status === 'done') notify('ClipperCuan', `${P.title}: ${P.clips.length} klip siap`);
    prevStatus = P.status;
    const busy = ['queued', 'running'].includes(P.status) || P.clips.some(c => ['queued', 'rendering'].includes(c.status));
    clearInterval(pollT); if (busy) pollT = setInterval(load, 1500);
  }
  await load();
}

function clipCard(P0, c0, reload) {
  const el = tpl('tpl-clip').firstElementChild;
  const vid = $('video', el);
  let C = c0, P = P0, ver = null, dirty = false, postDirty = false;
  ['.c-title', '.c-start', '.c-end'].forEach(s => $(s, el).addEventListener('input', () => dirty = true));
  $('.c-select', el).onchange = e => api(`/api/projects/${P.id}/candidates/${C.id}/action`, { method: 'POST', body: { action: 'selected', value: e.target.checked } }).then(reload).catch(err => toast(err.message, true));
  $('.c-pin', el).onclick = () => api(`/api/projects/${P.id}/candidates/${C.id}/action`, { method: 'POST', body: { action: 'pinned', value: !C.pinned } }).then(reload).catch(err => toast(err.message, true));
  $('.c-ban', el).onclick = () => api(`/api/projects/${P.id}/candidates/${C.id}/action`, { method: 'POST', body: { action: 'banned', value: !C.banned } }).then(reload).catch(err => toast(err.message, true));
  $('.c-post', el).addEventListener('input', () => postDirty = true);
  $('.c-ai', el).hidden = !llmOn(); $('.c-postai', el).hidden = !llmOn();
  $('.c-ai', el).onclick = async () => {
    const b = $('.c-ai', el); b.disabled = true;
    try { const r = await api(`/api/projects/${P.id}/clips/${C.id}/ai?kind=titles`, { method: 'POST' }); const box = $('.ai-list', el); box.hidden = false; box.replaceChildren(...r.titles.map(t => { const x = document.createElement('button'); x.type = 'button'; x.textContent = t; x.onclick = () => { $('.c-title', el).value = t; dirty = true; box.hidden = true; }; return x; })); }
    catch (e) { toast(e.message, true); } finally { b.disabled = false; }
  };
  const patch = async (changes, rerender = true) => {
    try { await api(`/api/projects/${P.id}/clips/${C.id}`, { method: 'PATCH', body: { changes, rerender } }); dirty = false; toast(rerender ? 'Render ulang dimulai' : 'Tersimpan'); reload(); }
    catch (e) { toast(e.message, true); }
  };
  const postText = () => { const p = C.post || {}; return [p.caption, (p.hashtags || []).join(' ')].filter(Boolean).join('\n\n'); };
  $('.c-copy', el).onclick = async () => { try { await navigator.clipboard.writeText($('.c-post', el).value); toast('Caption disalin'); } catch { $('.c-post', el).select(); document.execCommand('copy'); toast('Caption disalin'); } };
  $('.c-postsave', el).onclick = () => { const v = $('.c-post', el).value; const tags = v.match(/#[\p{L}\p{N}_]+/gu) || []; const caption = v.replace(/#[\p{L}\p{N}_]+/gu, '').trim(); postDirty = false; patch({ post: { caption, hashtags: tags } }, false); };
  $('.c-postai', el).onclick = async () => {
    const b = $('.c-postai', el); b.disabled = true;
    try { const r = await api(`/api/projects/${P.id}/clips/${C.id}/ai?kind=post`, { method: 'POST' }); $('.c-post', el).value = [r.caption, r.hashtags.join(' ')].join('\n\n'); postDirty = true; }
    catch (e) { toast(e.message, true); } finally { b.disabled = false; }
  };
  $('.c-save', el).onclick = () => {
    const ch = { title: $('.c-title', el).value };
    const s = +$('.c-start', el).value, e = +$('.c-end', el).value;
    if (s !== C.start || e !== C.end) { if (e - s < 1) return toast('Durasi minimal 1 detik', true); ch.start = s; ch.end = e; }
    patch(ch);
  };
  $('.c-del', el).onclick = async () => { if (!confirm(`Hapus ${C.id.replace('clip_', 'klip ')}?`)) return; try { await api(`/api/projects/${P.id}/clips/${C.id}`, { method: 'DELETE' }); toast('Klip dihapus'); reload(); } catch (e) { toast(e.message, true); } };
  $('.c-layout', el).onchange = e => patch({ overrides: { layout: e.target.value || P.settings.layout } });
  $('.c-words', el).onclick = () => wordsDialog(C, words => patch({ words }));
  $('.c-crop', el).onclick = () => cropDialog(P, C, keys => patch({ crop_keys: keys }));
  return {
    el,
    update(p, c) {
      P = p; C = c;
      $('.cid', el).textContent = c.title || c.id;
      $('.c-select', el).checked = !!c.selected; $('.c-pin', el).textContent = c.pinned ? 'Unpin' : 'Pin'; $('.c-ban', el).textContent = c.banned ? 'Unban' : 'Ban';
      $('.rank', el).textContent = `#${c.rank || '–'}`; $('.profile', el).textContent = c.profile || P.content_profile || 'auto';
      $('.cluster', el).textContent = c.topic_cluster || 'umum'; $('.overlap', el).textContent = `Overlap ${c.overlap_percentage || 0}%`;
      el.classList.toggle('selected', !!c.selected); el.classList.toggle('banned', !!c.banned);
      $('.score', el).textContent = c.score ? '★ ' + c.score : 'manual';
      $('.ready-score', el).textContent = `Readiness ${c.readiness ?? c.score ?? 0}/100`;
      $('.confidence', el).textContent = `Confidence ${Math.round((c.confidence ?? .5) * 100)}%`;
      const warnings = [...(c.warnings || []), ...(c.render_warnings || [])]; $('.clip-warnings', el).hidden = !warnings.length; $('.clip-warnings', el).textContent = warnings.join(' · ');
      const labels = { hook: 'Hook', novelty: 'Novelty', emotional_shift: 'Emosi', clarity: 'Clarity', payoff: 'Payoff', quotability: 'Quotability', visual_action: 'Visual', information_density: 'Density', clean_ending: 'Ending' };
      $('.score-grid', el).innerHTML = Object.entries(c.breakdown || {}).filter(([, v]) => typeof v === 'number').map(([k, v]) => `<span><b>${esc(labels[k] || k)}</b><i style="--v:${Math.max(0, Math.min(100, v))}%"></i><em>${v}</em></span>`).join('') || '<span class="muted">Breakdown belum tersedia untuk proyek lama.</span>';
      $('.dur', el).innerHTML = `${fmt(c.start)}–${fmt(c.end)} · ${Math.round(c.duration || c.end - c.start)} dtk` + (c.cut_saved > 0.3 ? ` <span class="tag-cut">−${c.cut_saved.toFixed(1)} dtk jeda</span>` : '');
      if (!dirty && document.activeElement?.closest('.clip') !== el) { $('.c-title', el).value = c.title || ''; $('.c-start', el).value = c.start; $('.c-end', el).value = c.end; }
      if (!postDirty) $('.c-post', el).value = postText();
      $('.reason', el).textContent = c.reason ? 'Kenapa dipilih: ' + c.reason : '';
      const busy = ['queued', 'rendering'].includes(c.status);
      $('.busy', el).hidden = !busy; $('.busy b', el).textContent = c.status === 'queued' ? 'Antre…' : 'Merender…';
      $('.err', el).hidden = c.status !== 'error'; $('.err', el).textContent = c.error || 'Render gagal';
      const lay = (c.overrides && c.overrides.layout) || P.settings.layout;
      $('.c-layout', el).value = c.overrides && c.overrides.layout ? c.overrides.layout : '';
      $('.c-crop', el).hidden = !['portrait', 'square'].includes(lay);
      const ok = c.status === 'done' && c.file;
      ['.c-dl', '.c-srt', '.c-words', '.c-crop'].forEach(s => $(s, el).toggleAttribute('disabled', !ok));
      if (ok && c.version !== ver) {
        ver = c.version;
        const u = `/files/${P.id}/${c.file}?v=${c.version}`, name = (c.title || c.id).replace(/[\\/:*?"<>|]+/g, '').slice(0, 60);
        vid.src = u; vid.poster = `/files/${P.id}/${c.thumb}?v=${c.version}`;
        $('.c-dl', el).href = u; $('.c-dl', el).download = name + '.mp4';
        $('.c-srt', el).href = `/files/${P.id}/${c.srt || c.id + '.srt'}?v=${c.version}`; $('.c-srt', el).download = name + '.srt';
      }
    },
  };
}

/* ---------------- dialog umum ---------------- */
function openDlg(build) { const d = $('#dlg'), b = $('#dlgBody'); b.replaceChildren(); build(b, () => d.close()); d.showModal(); }

/* edit kata caption + gaya per kata */
function wordsDialog(C, onSave) {
  const words = (C.words || []).map(w => ({ ...w, style: { ...(w.style || {}) } }));
  openDlg((b, close) => {
    b.innerHTML = `<h2>Edit caption</h2><p class="muted">Ketik untuk memperbaiki ejaan (kosongkan = hapus kata). Klik kata lalu tekan <kbd>Alt</kbd>+klik / <kbd>Ctrl</kbd>+klik untuk memilih beberapa, lalu beri warna atau ukuran khusus.</p>
      <div class="wtools"><span class="muted" id="wSel">0 kata dipilih</span>
        <input type="color" id="wCol" value="#3ddc97" title="Warna kata"><button class="btn ghost sm" id="wApplyCol">Beri warna</button>
        <label class="inline" style="margin:0">Ukuran <input type="range" id="wSc" min="80" max="180" value="130" style="width:120px"></label><button class="btn ghost sm" id="wApplySc">Beri ukuran</button>
        <button class="btn ghost sm" id="wClear">Hapus gaya</button></div>
      <div class="words"></div><div class="acts"><button class="btn" id="wSave">Simpan &amp; render</button></div>`;
    const box = $('.words', b), sel = new Set();
    const paint = (i, inp) => { const st = words[i].style; inp.style.color = st.color || ''; inp.style.fontWeight = st.scale > 1.05 ? 800 : ''; inp.classList.toggle('sel', sel.has(i)); };
    words.forEach((w, i) => {
      const inp = document.createElement('input'); inp.value = w.w; inp.title = `${w.s.toFixed(2)}–${w.e.toFixed(2)} dtk`;
      inp.oninput = () => words[i].w = inp.value.trim();
      inp.onclick = e => { if (!(e.altKey || e.ctrlKey || e.metaKey)) sel.clear(); sel.has(i) && (e.altKey || e.ctrlKey || e.metaKey) ? sel.delete(i) : sel.add(i); $$('input', box).forEach((x, j) => paint(j, x)); $('#wSel', b).textContent = `${sel.size} kata dipilih`; };
      paint(i, inp); box.append(inp);
    });
    if (!words.length) box.innerHTML = '<p class="muted">Klip ini tidak punya kata terdeteksi.</p>';
    const apply = patch => { if (!sel.size) return toast('Pilih kata dulu', true); sel.forEach(i => Object.assign(words[i].style, patch)); $$('input', box).forEach((x, j) => paint(j, x)); };
    $('#wApplyCol', b).onclick = () => apply({ color: $('#wCol', b).value });
    $('#wApplySc', b).onclick = () => apply({ scale: +$('#wSc', b).value / 100 });
    $('#wClear', b).onclick = () => { sel.forEach(i => words[i].style = {}); $$('input', box).forEach((x, j) => paint(j, x)); };
    $('#wSave', b).onclick = () => { onSave(words.filter(w => w.w).map(w => (Object.keys(w.style).length ? w : (({ style, ...r }) => r)(w)))); close(); };
  });
}

/* smart crop keyframe */
function cropDialog(P, C, onSave) {
  const m = P.media, lay = (C.overrides && C.overrides.layout) || P.settings.layout;
  const wFrac = Math.min(m.height * (lay === 'square' ? 1 : 9 / 16) / m.width, 1);
  const dur = C.end - C.start;
  let keys = (C.crop_keys && C.crop_keys.length ? C.crop_keys : [[0, 0.5]]).map(k => [...k]);
  let t = 0;
  openDlg((b, close) => {
    b.innerHTML = `<h2>Atur crop &amp; keyframe</h2><p class="muted">Geser kotak kuning untuk memilih area. Klik timeline untuk pindah waktu, lalu "Simpan keyframe". Klik kanan keyframe untuk menghapus. Tombol panah <kbd>←</kbd><kbd>→</kbd> menggeser kotak.</p>
      <div class="crop-wrap"><img alt="Frame video"><div class="crop-box" tabindex="0"></div></div>
      <div class="tl"><div class="ph"></div></div><div class="muted" id="cT"></div>
      <div class="acts" style="margin-top:12px"><button class="btn ghost" id="kAdd">◆ Simpan keyframe di sini</button><button class="btn ghost" id="kAuto">Auto (ikuti wajah)</button><button class="btn ghost" id="kCenter">Reset ke tengah</button><button class="btn" id="kSave">Simpan &amp; render</button></div>`;
    const img = $('img', b), box = $('.crop-box', b), wrap = $('.crop-wrap', b), tl = $('.tl', b);
    box.style.width = wFrac * 100 + '%';
    const interp = tt => { const s = [...keys].sort((a, b) => a[0] - b[0]); if (tt <= s[0][0]) return s[0][1]; for (let i = 0; i < s.length - 1; i++) if (tt <= s[i + 1][0]) { const k = (tt - s[i][0]) / ((s[i + 1][0] - s[i][0]) || 1); return s[i][1] + (s[i + 1][1] - s[i][1]) * k; } return s.at(-1)[1]; };
    let cx = interp(0);
    const place = () => { cx = Math.max(wFrac / 2, Math.min(1 - wFrac / 2, cx)); box.style.left = (cx - wFrac / 2) * 100 + '%'; };
    const draw = () => { $$('.kf', tl).forEach(n => n.remove()); keys.forEach((k, i) => { const d = document.createElement('button'); d.type = 'button'; d.className = 'kf' + (Math.abs(k[0] - t) < .3 ? ' cur' : ''); d.style.left = (k[0] / dur * 100) + '%'; d.title = `${k[0].toFixed(1)} dtk`; d.onclick = e => { e.stopPropagation(); seek(k[0]); }; d.oncontextmenu = e => { e.preventDefault(); e.stopPropagation(); if (keys.length > 1) { keys.splice(i, 1); draw(); } }; tl.append(d); }); $('.ph', tl).style.left = (t / dur * 100) + '%'; $('#cT', b).textContent = `Waktu: ${t.toFixed(1)} / ${dur.toFixed(1)} dtk · ${keys.length} keyframe`; };
    const seek = tt => { t = Math.max(0, Math.min(dur, Math.round(tt * 2) / 2)); img.src = `/api/projects/${P.id}/frame?t=${(C.start + t).toFixed(1)}`; cx = interp(t); place(); draw(); };
    tl.onclick = e => { const r = tl.getBoundingClientRect(); seek((e.clientX - r.left) / r.width * dur); };
    let drag = null;
    box.onpointerdown = e => { box.setPointerCapture(e.pointerId); drag = { x: e.clientX, cx }; };
    box.onpointermove = e => { if (!drag) return; cx = drag.cx + (e.clientX - drag.x) / wrap.clientWidth; place(); };
    box.onpointerup = () => drag = null;
    box.onkeydown = e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { cx += (e.key === 'ArrowLeft' ? -0.01 : 0.01); place(); e.preventDefault(); } };
    $('#kAdd', b).onclick = () => { const ex = keys.find(k => Math.abs(k[0] - t) < .3); if (ex) ex[1] = cx; else keys.push([t, cx]); keys.sort((a, b) => a[0] - b[0]); draw(); toast('Keyframe disimpan'); };
    $('#kCenter', b).onclick = () => { keys = [[0, 0.5]]; seek(t); };
    $('#kAuto', b).onclick = () => { onSave(null); close(); };
    $('#kSave', b).onclick = () => { onSave(keys.map(k => [+k[0].toFixed(2), +k[1].toFixed(4)])); close(); };
    seek(0);
  });
}

/* editor area split gaming (facecam + gameplay) */
function splitDialog(P, reload) {
  const sp = structuredClone(P.settings.split);
  openDlg((b, close) => {
    b.innerHTML = `<h2>Atur area split gaming</h2><p class="muted">Seret kotak <b style="color:var(--acc)">FACECAM</b> dan <b style="color:#6ec1ff">GAMEPLAY</b> ke posisi yang benar. Tarik pojok kanan bawah untuk mengubah ukuran.</p>
      <div class="split-wrap"><img alt="Frame video"><div class="rect game"><span>GAMEPLAY</span><i></i></div><div class="rect face"><span>FACECAM</span><i></i></div></div>
      <label>Porsi facecam di hasil (atas) <input type="range" id="sr" min="25" max="60" value="${Math.round(sp.face_ratio * 100)}"></label>
      <div class="acts"><button class="btn" id="sGo">Simpan &amp; render ulang semua</button></div>`;
    const wrap = $('.split-wrap', b);
    $('img', b).src = `/api/projects/${P.id}/frame?t=${(P.clips[0]?.start || 1).toFixed(1)}`;
    const bind = (cls, key) => {
      const el = $('.rect.' + cls, b);
      const draw = () => { const [x, y, w, h] = sp[key]; Object.assign(el.style, { left: x * 100 + '%', top: y * 100 + '%', width: w * 100 + '%', height: h * 100 + '%' }); };
      let d = null;
      el.onpointerdown = e => { e.stopPropagation(); el.setPointerCapture(e.pointerId); d = { x: e.clientX, y: e.clientY, r: [...sp[key]], resize: e.target.tagName === 'I' }; };
      el.onpointermove = e => {
        if (!d) return;
        const dx = (e.clientX - d.x) / wrap.clientWidth, dy = (e.clientY - d.y) / wrap.clientHeight; let [x, y, w, h] = d.r;
        if (d.resize) { w = Math.max(.08, Math.min(1 - x, w + dx)); h = Math.max(.08, Math.min(1 - y, h + dy)); }
        else { x = Math.max(0, Math.min(1 - w, x + dx)); y = Math.max(0, Math.min(1 - h, y + dy)); }
        sp[key] = [+x.toFixed(4), +y.toFixed(4), +w.toFixed(4), +h.toFixed(4)]; draw();
      };
      el.onpointerup = () => d = null; draw();
    };
    bind('game', 'game'); bind('face', 'face');
    $('#sGo', b).onclick = async () => {
      sp.face_ratio = +$('#sr', b).value / 100;
      try { await api(`/api/projects/${P.id}/rerender`, { method: 'POST', body: { settings: { split: sp } } }); close(); toast('Render ulang semua klip…'); reload(); } catch (e) { toast(e.message, true); }
    };
  });
}

/* tambah klip manual */
function addClipDialog(P, reload) {
  openDlg((b, close) => {
    const d = P.media?.duration || 0;
    b.innerHTML = `<h2>Tambah klip manual</h2><p class="muted">Pilih sendiri potongan dari video (durasi video ${fmt(d)}). Format menit:detik juga boleh, mis. <kbd>1:25</kbd>.</p>
      <video controls preload="metadata" style="width:100%;max-height:45vh;background:#000;border-radius:10px"></video>
      <div class="row3" style="margin-top:12px"><label>Mulai<div class="inrow"><input class="in" id="aS" placeholder="0:00"><button class="btn ghost sm" id="aSn" type="button">⏱ sekarang</button></div></label>
      <label>Selesai<div class="inrow"><input class="in" id="aE" placeholder="0:30"><button class="btn ghost sm" id="aEn" type="button">⏱ sekarang</button></div></label>
      <label>Judul (opsional)<input class="in" id="aT" maxlength="80"></label></div>
      <div class="acts"><button class="btn" id="aGo">Buat klip</button></div>`;
    const v = $('video', b);
    v.src = `/api/projects/${P.id}/source`;
    const parse = s => { s = String(s).trim(); if (!s) return NaN; const p = s.split(':').map(Number); return p.reduce((a, x) => a * 60 + x, 0); };
    $('#aSn', b).onclick = () => $('#aS', b).value = v.currentTime.toFixed(1);
    $('#aEn', b).onclick = () => $('#aE', b).value = v.currentTime.toFixed(1);
    $('#aGo', b).onclick = async () => {
      const s = parse($('#aS', b).value), e = parse($('#aE', b).value);
      if (!(e > s)) return toast('Waktu selesai harus lebih besar dari mulai', true);
      try { await api(`/api/projects/${P.id}/clips`, { method: 'POST', body: { start: s, end: e, title: $('#aT', b).value } }); close(); toast('Klip manual dibuat'); reload(); } catch (err) { toast(err.message, true); }
    };
  });
}

/* gaya semua klip */
function styleDialog(P, reload) {
  const s = P.settings;
  openDlg((b, close) => {
    b.innerHTML = `<h2>Ubah gaya semua klip</h2><p class="muted">Semua klip dirender ulang dengan gaya ini. Judul &amp; potongan yang sudah kamu edit tetap dipertahankan.</p>
      <div class="row2"><label>Format<select class="in" id="sLay"><option value="portrait">Portrait</option><option value="square">Square</option><option value="blur">Blur</option><option value="split">Split gaming</option><option value="landscape">Landscape</option></select></label>
      <label>Gaya caption<select class="in" id="sCap"><option value="box">Box highlight</option><option value="wbw">Word by word</option><option value="karaoke">Karaoke</option><option value="clean">Clean</option></select></label></div>
      <div class="row2"><label>Font<select class="in" id="sFont">${INFO.fonts.map(f => `<option>${esc(f)}</option>`).join('')}</select></label>
      <label>Preset judul<select class="in" id="sTtl"><option value="bar">Bar</option><option value="outline">Outline</option><option value="neon">Neon</option><option value="clean">Clean</option></select></label></div>
      <div class="row3"><label>Warna teks<input type="color" class="in color" id="sCol"></label><label>Warna sorotan<input type="color" class="in color" id="sHl"></label><label>Ukuran<input type="number" class="in" id="sSize" min="40" max="140"></label></div>
      <label class="check"><input type="checkbox" id="sCapOn"> Tampilkan caption</label><label class="check"><input type="checkbox" id="sTtlOn"> Tampilkan judul</label>
      <label class="check"><input type="checkbox" id="sCut"> Potong jeda hening</label>
      <label class="check"><input type="checkbox" id="sEmo"> Emoji otomatis</label><label class="check"><input type="checkbox" id="sPb"> Progress bar</label>
      <label class="check"><input type="checkbox" id="sCta"> Ajakan di akhir: <input class="in" id="sCtaT" style="max-width:260px"></label>
      <label class="check"><input type="checkbox" id="sMu"> Musik latar (${esc((s.music.file || '').split(/[\\/]/).pop() || 'pilih di Proyek baru')})</label>
      <label class="check"><input type="checkbox" id="sWmOn"> Watermark teks: <input class="in" id="sWm" style="max-width:220px"></label>
      <div class="acts"><button class="btn" id="sGo">Render ulang semua</button></div>`;
    $('#sLay', b).value = s.layout; $('#sCap', b).value = s.caption.style; $('#sFont', b).value = s.caption.font; $('#sTtl', b).value = s.title.preset;
    $('#sCol', b).value = s.caption.color; $('#sHl', b).value = s.caption.highlight; $('#sSize', b).value = s.caption.size;
    $('#sCapOn', b).checked = s.caption.enabled; $('#sTtlOn', b).checked = s.title.enabled; $('#sCut', b).checked = !!s.cut_silence;
    $('#sEmo', b).checked = !!s.emoji?.enabled; $('#sPb', b).checked = !!s.progress_bar?.enabled; $('#sCta', b).checked = !!s.cta?.enabled; $('#sCtaT', b).value = s.cta?.text || '';
    $('#sMu', b).checked = !!s.music?.enabled; $('#sMu', b).disabled = !s.music?.file; $('#sWmOn', b).checked = s.watermark.enabled; $('#sWm', b).value = s.watermark.text;
    $('#sGo', b).onclick = async () => {
      const ns = { cut_silence: $('#sCut', b).checked, emoji: { enabled: $('#sEmo', b).checked }, progress_bar: { enabled: $('#sPb', b).checked },
        cta: { enabled: $('#sCta', b).checked, text: $('#sCtaT', b).value }, music: { enabled: $('#sMu', b).checked && !!s.music?.file }, caption: { style: $('#sCap', b).value, font: $('#sFont', b).value, color: $('#sCol', b).value, highlight: $('#sHl', b).value, size: +$('#sSize', b).value, enabled: $('#sCapOn', b).checked },
        title: { preset: $('#sTtl', b).value, enabled: $('#sTtlOn', b).checked }, watermark: { enabled: $('#sWmOn', b).checked, text: $('#sWm', b).value } };
      if ($('#sLay', b).value !== s.layout) ns.layout = $('#sLay', b).value;
      try { await api(`/api/projects/${P.id}/rerender`, { method: 'POST', body: { settings: ns } }); close(); toast('Render ulang semua klip…'); reload(); } catch (e) { toast(e.message, true); }
    };
  });
}

/* ================= TRANSCRIPT & CAPTION ================= */
async function pageCaptions() {
  const projects = await api('/api/projects');
  view.innerHTML = `<section class="page"><header class="page-h"><p class="eyebrow">CAPTION WORKSPACE</p><h1>Transcript & Caption</h1><p>Periksa sumber, timing, quality score, glossary, cue, template, preview, dan safe area.</p></header><div class="card"><label>Pilih proyek<select class="in" id="cwProject"><option value="">Pilih proyek</option>${projects.map(p => `<option value="${esc(p.id)}">${esc(p.title || p.id)}</option>`).join('')}</select></label></div><div id="cwRoot"></div></section>`;
  $('#cwProject').onchange = e => e.target.value && loadCaptionWorkspace(e.target.value);
}

async function loadCaptionWorkspace(pid) {
  let state = await api(`/api/projects/${pid}/captions`);
  const root = $('#cwRoot');
  const draw = () => {
    const q = state.quality_report || {};
    root.innerHTML = `<div class="caption-status-grid"><div class="metric"><small>SUMBER</small><b>${esc(q.source || 'unknown')}</b></div><div class="metric"><small>QUALITY</small><b>${q.score || 0}/100</b><span>Bukan WER</span></div><div class="metric"><small>TIMING</small><b>${esc(q.timing_mode || 'none')}</b></div><div class="metric"><small>COVERAGE</small><b>${Math.round((q.coverage || 0) * 100)}%</b></div></div><div class="cw-tabs"><button class="on" data-tab="transcript">Transcript</button><button data-tab="style">Caption Style</button><button data-tab="preview">Preview</button><button data-tab="quality">Quality</button></div><section class="cw-panel" data-panel="transcript"><div class="card"><div class="cw-actions"><input class="in" id="cwFind" placeholder="Cari"><input class="in" id="cwReplace" placeholder="Ganti"><button class="btn ghost" id="cwDoReplace">Cari-ganti</button><button class="btn ghost" data-action="undo">Undo</button><button class="btn ghost" data-action="redo">Redo</button><button class="btn" id="cwSave">Simpan</button></div><div class="cue-list">${(state.cues || []).map((c, i) => `<div class="cue-row"><span>${i + 1}</span><input class="in cue-start" type="number" step=".01" value="${c.start}"><input class="in cue-end" type="number" step=".01" value="${c.end}"><textarea class="in cue-text" rows="2">${esc(c.text)}</textarea><button class="btn ghost sm" data-split="${i}">Split</button><button class="btn ghost sm" data-merge="${i}">Merge</button></div>`).join('')}</div></div><div class="card"><h3>Glossary</h3><p class="hint">Variant eksplisit saja. Semua koreksi masuk audit trail dan dapat di-undo.</p>${(state.glossary || []).map(g => `<div class="gloss-row"><input class="in" value="${esc(g.canonical)}" aria-label="Istilah canonical"><input class="in" value="${esc((g.variants || []).join(', '))}" aria-label="Variant istilah" placeholder="variant salah, pisahkan koma"></div>`).join('')}<div class="cw-actions"><button class="btn" data-action="glossary">Terapkan glossary</button></div></div></section><section class="cw-panel" data-panel="style" hidden><div class="template-gallery">${Object.entries(state.templates || {}).map(([id, t]) => `<button class="template-card ${id === (state.selected_template || state.recommended_template) ? 'on' : ''}" data-template="${id}" style="--cap:${t.color};--hl:${t.highlight};--bg:${t.background}"><div>Caption <mark>aktif</mark></div><b>${esc(t.label)}</b><small>${esc(t.position)} · ${esc(t.animation)} · ${t.max_words} kata</small></button>`).join('')}</div></section><section class="cw-panel" data-panel="preview" hidden><div class="preview-workspace"><div class="phone-canvas"><video src="/api/projects/${pid}/source" controls></video><div class="safe-guide"></div><div class="live-caption">${esc(state.cues?.[0]?.text || 'Preview caption')}</div></div><div class="card"><h3>Caption inspector</h3><dl class="kv"><dt>Current cue</dt><dd>1</dd><dt>Timecode</dt><dd>${state.cues?.[0] ? `${state.cues[0].start.toFixed(2)}–${state.cues[0].end.toFixed(2)}` : '—'}</dd><dt>Timing mode</dt><dd>${esc(q.timing_mode || 'none')}</dd><dt>Safe area</dt><dd>15%</dd></dl></div></div></section><section class="cw-panel" data-panel="quality" hidden><div class="card"><h3>Quality report</h3>${(q.warnings || []).map(w => `<p class="warn">${esc(w)}</p>`).join('') || '<p class="ok">Tidak ada warning utama.</p>'}<div class="cw-actions"><button class="btn" data-action="validate">Validate</button><button class="btn ghost" id="cwAutoFix">Auto Fix Safe Issues</button><button class="btn ghost" disabled title="Pilih ASR lokal secara eksplisit">Re-align</button><button class="btn ghost" disabled title="Pilih model secara eksplisit">Retranscribe</button></div><div id="cwValidation"></div></div></section>`;
    $$('.cw-tabs button', root).forEach(button => button.onclick = () => { $$('.cw-tabs button', root).forEach(x => x.classList.toggle('on', x === button)); $$('.cw-panel', root).forEach(panel => panel.hidden = panel.dataset.panel !== button.dataset.tab); });
    $$('.cue-row', root).forEach((row, i) => { $('.cue-start', row).oninput = e => state.cues[i].start = +e.target.value; $('.cue-end', row).oninput = e => state.cues[i].end = +e.target.value; $('.cue-text', row).oninput = e => state.cues[i].text = e.target.value; });
    $$('[data-action]', root).forEach(button => button.onclick = () => action(button.dataset.action));
    $$('[data-split]', root).forEach(button => button.onclick = () => action('split', { index: +button.dataset.split, word: Math.max(1, Math.floor((state.cues[+button.dataset.split].words || []).length / 2)) }));
    $$('[data-merge]', root).forEach(button => button.onclick = () => action('merge', { index: +button.dataset.merge }));
    $$('[data-template]', root).forEach(button => button.onclick = () => { state.selected_template = button.dataset.template; draw(); });
    $('#cwSave', root).onclick = save;
    $('#cwDoReplace', root).onclick = () => { const find = $('#cwFind', root).value, replacement = $('#cwReplace', root).value; if (find) { state.cues.forEach(c => c.text = c.text.split(find).join(replacement)); draw(); } };
    $('#cwAutoFix', root).onclick = () => { for (let i = 1; i < state.cues.length; i++) state.cues[i - 1].end = Math.min(state.cues[i - 1].end, state.cues[i].start); draw(); toast('Overlap aman diperbaiki; teks tetap sama'); };
  };
  const action = async (action, payload = {}) => { state = await api(`/api/projects/${pid}/captions/action`, { method: 'POST', body: { action, payload } }); draw(); };
  const save = async () => { state = await api(`/api/projects/${pid}/captions`, { method: 'PUT', body: { revision: state.revision, data: { cues: state.cues, glossary: state.glossary, selected_template: state.selected_template } } }); toast('Workspace tersimpan atomik'); draw(); };
  draw();
}

/* ================= RIWAYAT ================= */
async function pageHistory() {
  view.innerHTML = '<section class="page"><header class="page-h proj-h"><div><h1>Riwayat</h1><p>Semua proyek yang pernah kamu buat.</p></div><input class="in" id="hq" placeholder="Cari judul…" style="max-width:260px"></header><div class="hist" id="hl"></div></section>';
  let list = await api('/api/projects');
  const hl = $('#hl');
  const label = { done: 'selesai', running: 'diproses', queued: 'antre', error: 'gagal', cancelled: 'dibatalkan' };
  const draw = () => {
    const q = $('#hq').value.toLowerCase();
    const items = list.filter(p => (p.title || '').toLowerCase().includes(q));
    if (!items.length) { hl.innerHTML = '<div class="empty">Belum ada proyek. <a href="#/new" style="color:var(--acc)">Buat proyek baru →</a></div>'; return; }
    hl.replaceChildren(...items.map(p => {
      const a = document.createElement('a'); a.className = 'hcard'; a.href = '#/p/' + p.id;
      a.innerHTML = `<div class="hthumb"></div><div class="hbody"><b></b><div class="hrow"><span class="tag ${p.status}">${label[p.status] || p.status}${p.status === 'running' ? ' ' + Math.round(p.progress * 100) + '%' : ''}</span><span>${p.clips} klip</span><button class="del" title="Hapus">🗑</button></div><span class="muted" style="font-size:12px">${new Date(p.created * 1000).toLocaleString('id-ID')}</span></div>`;
      $('b', a).textContent = p.title || p.id;
      if (p.thumb) $('.hthumb', a).style.backgroundImage = `url('/files/${p.id}/${p.thumb}')`;
      $('.del', a).onclick = async e => { e.preventDefault(); if (!confirm('Hapus proyek ini beserta semua klipnya?')) return; await api('/api/projects/' + p.id, { method: 'DELETE' }); list = list.filter(x => x !== p); draw(); badge(); };
      return a;
    }));
  };
  $('#hq').oninput = draw; draw();
  pollT = setInterval(async () => { if (list.some(p => ['queued', 'running'].includes(p.status))) { list = await api('/api/projects'); draw(); } }, 3000);
}

/* ================= TEMPLATE ================= */
async function pageTemplates() {
  const t = await api('/api/templates');
  view.innerHTML = `<section class="page"><header class="page-h"><h1>Template gaya</h1><p>Simpan kombinasi format, caption, judul, dan watermark favoritmu. Buat template dari halaman <a href="#/new" style="color:var(--acc)">Proyek baru</a> → "Simpan sebagai template".</p></header><div class="card"><div class="tlist" id="tl"></div></div></section>`;
  const tl = $('#tl');
  const names = Object.keys(t);
  if (!names.length) { tl.innerHTML = '<div class="empty">Belum ada template.</div>'; return; }
  names.forEach(n => {
    const s = t[n], row = document.createElement('div'); row.className = 'trow';
    row.innerHTML = `<div><b></b><div class="muted" style="font-size:13px">${esc(s.layout)} · caption ${esc(s.caption?.style)} · ${esc(s.caption?.font)} · judul ${esc(s.title?.preset)}${s.cut_silence ? ' · potong jeda' : ''}</div></div><div class="acts"><button class="btn sm" data-use>Pakai</button><button class="btn ghost sm danger" data-del>Hapus</button></div>`;
    $('b', row).textContent = n;
    $('[data-use]', row).onclick = () => { location.hash = '#/new'; setTimeout(() => pageNew({ ...s, __name: n }), 0); };
    $('[data-del]', row).onclick = async () => { if (!confirm(`Hapus template "${n}"?`)) return; await api('/api/templates/' + encodeURIComponent(n), { method: 'DELETE' }); pageTemplates(); };
    tl.append(row);
  });
}

/* ================= CEK SISTEM ================= */
async function pageSystem() {
  view.innerHTML = '<section class="page"><header class="page-h"><h1>Cek sistem</h1><p>Memeriksa komponen yang dibutuhkan aplikasi…</p></header><div class="card" id="sys">Memeriksa…</div></section>';
  const s = await api('/api/system');
  const ok = v => v ? '<span class="ok">✓</span>' : '<span class="bad">✗</span>';
  $('#sys').innerHTML = `<dl class="kv">
    <dt>Sistem operasi</dt><dd>${esc(s.os)}</dd><dt>Python</dt><dd>${esc(s.python)}</dd>
    <dt>FFmpeg</dt><dd>${ok(!s.ffmpeg.error)} ${esc(s.ffmpeg.version || s.ffmpeg.error)}<br><span class="muted">${esc(s.ffmpeg.path)}</span></dd>
    <dt>Caption (libass)</dt><dd>${ok(s.ffmpeg.libass)} ${s.ffmpeg.libass ? 'tersedia' : 'TIDAK tersedia — caption tidak akan muncul'}</dd>
    <dt>GPU NVIDIA (CUDA)</dt><dd>${s.gpu_cuda ? '<span class="ok">✓</span> ' + s.gpu_cuda + ' GPU — transkripsi dipercepat' : 'tidak ada — memakai CPU (normal)'}</dd>
    <dt>Model Whisper terunduh</dt><dd>${s.models.length ? esc(s.models.join(', ')) : 'belum ada (diunduh otomatis saat pertama dipakai)'}</dd>
    <dt>Versi komponen</dt><dd>${Object.entries(s.versions).map(([k, v]) => `${ok(v)} ${esc(k)} ${esc(v || 'tidak terpasang')}`).join('<br>')}</dd>
    <dt>Ruang disk kosong</dt><dd>${s.disk_free_gb < 5 ? '<span class="bad">' : '<span>'}${s.disk_free_gb} GB</span></dd>
    <dt>Ukuran data aplikasi</dt><dd>${s.data_size_gb} GB</dd></dl>`;
}

/* ================= BANTUAN ================= */
function pageHelp() {
  view.innerHTML = `<section class="page help"><header class="page-h"><h1>Bantuan</h1><p>Panduan singkat memakai ClipperCuan.</p></header>
  <div class="card"><h3>Alur kerja</h3><ol>
    <li><b>Proyek baru</b> → tempel link (bisa banyak, satu per baris) atau pilih file.</li>
    <li>Atur jumlah &amp; durasi klip, bahasa, format, caption, judul, watermark. Simpan sebagai <b>template</b> agar cepat dipakai lagi.</li>
    <li>Klik <b>Mulai</b>. Proses: unduh → transkripsi → cari momen → render. Kamu dapat notifikasi saat selesai.</li>
    <li>Di halaman proyek: tonton, ubah judul/potongan, <b>Edit caption</b> (ejaan, warna &amp; ukuran per kata), <b>Atur crop</b> (keyframe), ganti format per klip, lalu <b>Simpan &amp; render</b>.</li>
    <li><b>Download semua (ZIP)</b> berisi MP4 + subtitle SRT + caption posting siap salin.</li></ol></div>
  <div class="card"><h3>Tips hasil terbaik</h3><ul>
    <li>Model <b>Small</b> sudah akurat untuk bahasa Indonesia. Pakai <b>Medium</b> jika banyak istilah/aksen.</li>
    <li>Aktifkan <b>Potong jeda hening</b> untuk podcast agar klip lebih padat.</li>
    <li>Untuk game: pilih <b>Split gaming</b>, lalu di halaman proyek klik <b>Atur area split</b> dan seret kotak facecam/gameplay.</li>
    <li>Klip terbaik ada di urutan atas (skor tertinggi). Baca "Kenapa dipilih" untuk alasannya.</li>
    <li>Pakai <b>＋ Klip manual</b> jika ada momen yang kamu tahu bagus tapi tidak terpilih.</li></ul></div>
  <div class="card"><h3>Masalah umum</h3><ul>
    <li><b>Link YouTube gagal</b>: tutup lalu buka aplikasi lagi (pengunduh diperbarui otomatis), atau unduh videonya lalu pakai mode File.</li>
    <li><b>Caption tidak muncul</b>: buka <a href="#/system" style="color:var(--acc)">Cek sistem</a>, pastikan libass ✓.</li>
    <li><b>Proses lambat</b>: pilih model Tiny/Base, kurangi jumlah klip, atau tutup aplikasi berat lain.</li>
    <li><b>Hasil di mana?</b> Klik <b>Buka folder</b> di halaman proyek. Lokasi data: <code>${esc(INFO.data_dir)}</code></li></ul></div>
  <div class="card"><h3>Versi</h3><p class="muted">ClipperCuan ${esc(INFO.version)} · berjalan lokal di http://127.0.0.1 — video tidak diunggah ke mana pun.</p></div></section>`;
}

/* ================= AI AGENT & OTOMATISASI ================= */
async function pageAgent() {
  const [st, info, tpls] = await Promise.all([api('/api/settings'), api('/api/agent/info'), api('/api/templates')]);
  const A = st.automation;
  const mcp = JSON.stringify(info.mcp_config, null, 2);
  view.innerHTML = `<section class="page"><header class="page-h"><h1>AI Agent &amp; otomatisasi</h1><p>Jalankan ClipperCuan tanpa klik: dari AI agent (MCP), webhook, folder pantau, atau baris perintah.</p></header>
  <div class="card"><h3>1 · Sambungkan AI agent (MCP)</h3>
    <p class="hint">Tempel konfigurasi ini ke klien MCP (Claude Desktop/Code, Cursor, atau agent kamu). Agent mendapat 11 tools: <code>create_clips</code>, <code>get_project</code>, <code>wait_for_project</code>, <code>edit_clip</code>, <code>add_clip</code>, <code>delete_clip</code>, <code>restyle_project</code>, <code>export_project</code>, <code>list_projects</code>, <code>list_templates</code>, <code>system_check</code>. Server aplikasi dinyalakan otomatis bila belum jalan.</p>
    <pre class="code" id="mcpCfg"></pre><div class="acts"><button class="btn ghost sm" data-copy="mcpCfg">Salin konfigurasi</button></div>
    <p class="hint">Contoh perintah ke agent: <i>"Buat 5 klip dari https://youtu.be/xxxx pakai template Podcast Kuning, tunggu selesai, lalu kirim path videonya."</i></p></div>
  <div class="card"><h3>2 · Otomatisasi tanpa sentuhan</h3>
    <label>Webhook saat proyek selesai/gagal (n8n, Make, Zapier, agent kamu)<div class="inrow"><input class="in" id="aHook" placeholder="https://… /webhook"><button class="btn ghost sm" id="aHookTest" type="button">Tes</button></div></label>
    <label>Salin hasil otomatis ke folder<input class="in" id="aExport" placeholder="mis. D:\\Konten\\Siap Upload  atau  /Users/kamu/Konten"></label>
    <div class="fx-row"><div><b>Folder pantau (inbox)</b><span>Taruh video di folder ini → otomatis diproses. Cocok untuk agent yang mengunduh video sendiri.</span></div><label class="sw"><input type="checkbox" id="aInbox"><span></span></label></div>
    <div class="row2"><label>Folder inbox<input class="in" readonly id="aInboxDir"></label><label>Template untuk inbox<select class="in" id="aInboxTpl"><option value="">Pengaturan bawaan</option></select></label></div>
    <div class="acts"><button class="btn" id="aSave">Simpan</button><button class="btn ghost" id="aScan" type="button">Cek inbox sekarang</button></div></div>
  <div class="card"><h3>3 · Baris perintah (CLI)</h3><pre class="code" id="cliEx"></pre><div class="acts"><button class="btn ghost sm" data-copy="cliEx">Salin</button></div></div>
  <div class="card"><h3>4 · REST API</h3><p class="hint">Semua fitur UI tersedia lewat HTTP lokal. Dokumentasi interaktif: <a href="/docs" target="_blank" style="color:var(--acc)">/docs</a>. Ringkasan hasil untuk agent: <code>GET /api/projects/{id}/summary</code>.</p>
    <pre class="code" id="restEx"></pre></div></section>`;
  $('#mcpCfg').textContent = mcp;
  $('#cliEx').textContent = `${info.cli} "https://youtu.be/xxxx" --clips 5 --template "Podcast Kuning" --emoji --cut-silence --json\n${info.cli} "D:/video/podcast.mp4" --layout split --export "D:/Konten" --json`;
  $('#restEx').textContent = `POST /api/projects  {"source": "https://youtu.be/xxxx", "settings": {"clip_count": 5, "layout": "portrait"}}\nGET  /api/projects/{id}/summary   → status, progress, clips[].video_path, caption, hashtags\nPOST /api/projects/{id}/export    {"folder": "D:/Konten"}\n\nWebhook (POST JSON): {"event": "project.done", "project_id": "…", "title": "…", "clips": [{"video_path": "…", "srt_path": "…", "caption": "…", "hashtags": ["#…"]}]}`;
  $$('[data-copy]').forEach(b => b.onclick = async () => { const t = $('#' + b.dataset.copy).textContent; try { await navigator.clipboard.writeText(t); } catch { const ta = document.createElement('textarea'); ta.value = t; document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove(); } toast('Disalin'); });
  $('#aHook').value = A.webhook_url; $('#aExport').value = A.export_dir; $('#aInbox').checked = A.inbox_enabled; $('#aInboxDir').value = info.inbox_dir;
  Object.keys(tpls).forEach(n => $('#aInboxTpl').append(new Option(n, n))); $('#aInboxTpl').value = A.inbox_template || '';
  $('#aHookTest').onclick = async () => { try { const r = await api('/api/automation/test-webhook', { method: 'POST', body: { url: $('#aHook').value } }); toast('✓ Webhook menjawab ' + r.status); } catch (e) { toast(e.message, true); } };
  $('#aSave').onclick = async () => { await api('/api/settings', { method: 'POST', body: { settings: { automation: { webhook_url: $('#aHook').value.trim(), export_dir: $('#aExport').value.trim(), inbox_enabled: $('#aInbox').checked, inbox_template: $('#aInboxTpl').value } } } }); toast('Otomatisasi disimpan'); };
  $('#aScan').onclick = async () => { const r = await api('/api/automation/inbox/scan', { method: 'POST' }); toast(r.created.length ? `${r.created.length} video masuk antrean` : 'Tidak ada video baru (atau inbox nonaktif)'); badge(); };
}

/* ================= PENGATURAN ================= */
async function pageSettings() {
  SETTINGS = await api('/api/settings');
  const L = SETTINGS.llm;
  view.innerHTML = `<section class="page"><header class="page-h"><h1>Pengaturan</h1><p>Opsional. Aplikasi tetap berjalan penuh tanpa AI eksternal.</p></header>
    <div class="card"><h3>AI router (9router / kompatibel OpenAI) <label class="sw"><input type="checkbox" id="lOn"><span></span></label></h3>
      <p class="hint">Dipakai untuk memilih momen terbaik, membuat judul, dan caption posting. Transkripsi tetap memakai Whisper lokal.</p>
      <div class="row2"><label>Base URL<input class="in" id="lUrl" placeholder="http://localhost:20128/v1"></label><label>API key<input class="in" id="lKey" type="password" placeholder="sk-…"></label></div>
      <div class="acts" style="margin-bottom:14px"><button class="btn ghost" id="lTest">Tes koneksi &amp; ambil model</button><span class="muted" id="lMsg"></span></div>
      <div class="row2"><label>Model pemilih momen (pintar)<input class="in" id="lM1" list="lModels" placeholder="mis. claude-sonnet / gpt thinker"></label><label>Model judul &amp; caption (cepat)<input class="in" id="lM2" list="lModels" placeholder="mis. haiku / gemini flash"></label></div>
      <datalist id="lModels"></datalist>
      <label>Temperature <input type="range" id="lTemp" min="0" max="100"></label>
      <button class="btn" id="lSave">Simpan</button></div>
    <div class="card"><h3>Transkripsi cloud (opsional)</h3>
      <p class="hint">Subtitle dibuat di server cloud, bukan di laptop — cocok untuk laptop pas-pasan. Format OpenAI <code>/audio/transcriptions</code>: Groq (gratis/murah, sangat cepat), OpenAI, atau 9router bila mendukung audio.</p>
      <div class="row3"><label>Base URL<input class="in" id="aUrl" placeholder="https://api.groq.com/openai/v1"></label><label>API key<input class="in" id="aKey" type="password" placeholder="gsk_…"></label><label>Model<input class="in" id="aModel" placeholder="whisper-large-v3"></label></div>
      <div class="acts"><button class="btn ghost" id="aTest">Tes koneksi</button><button class="btn" id="aSaveAsr">Simpan</button><span class="muted" id="aMsg"></span></div></div>
    <div class="card"><h3>Default proyek</h3><p class="muted">Pengaturan proyek terakhir otomatis dipakai lagi. <button class="btn ghost sm" id="rst">Kembalikan ke bawaan</button></p></div>
    <div class="card"><h3>Info</h3><p class="muted">Versi ${esc(INFO.version)}<br>Folder data &amp; hasil: <b>${esc(INFO.data_dir)}</b></p></div></section>`;
  $('#lOn').checked = L.enabled; $('#lUrl').value = L.base_url; $('#lKey').value = L.api_key; $('#lM1').value = L.model_moments; $('#lM2').value = L.model_titles; $('#lTemp').value = Math.round(L.temperature * 100);
  const A = SETTINGS.asr;
  $('#aUrl').value = A.base_url; $('#aKey').value = A.api_key; $('#aModel').value = A.model;
  const asrForm = () => ({ asr: { base_url: $('#aUrl').value.trim(), api_key: $('#aKey').value, model: $('#aModel').value.trim() } });
  $('#aTest').onclick = async () => { $('#aMsg').textContent = 'Menguji…'; try { await api('/api/asr/test', { method: 'POST', body: { settings: asrForm() } }); $('#aMsg').textContent = '✓ API transkripsi siap'; } catch (e) { $('#aMsg').textContent = '✗ ' + e.message; } };
  $('#aSaveAsr').onclick = async () => { SETTINGS = await api('/api/settings', { method: 'POST', body: { settings: asrForm() } }); $('#aKey').value = SETTINGS.asr.api_key; toast('Transkripsi cloud disimpan'); };
  $('#rst').onclick = () => { store.set('lastSettings', {}); toast('Kembali ke pengaturan bawaan'); };
  const form = () => ({ llm: { enabled: $('#lOn').checked, base_url: $('#lUrl').value.trim(), api_key: $('#lKey').value, model_moments: $('#lM1').value.trim(), model_titles: $('#lM2').value.trim(), temperature: +$('#lTemp').value / 100 } });
  $('#lTest').onclick = async () => {
    $('#lMsg').textContent = 'Menghubungi…';
    try { const r = await api('/api/llm/models', { method: 'POST', body: { settings: form() } }); $('#lModels').innerHTML = r.models.map(m => `<option value="${esc(m)}">`).join(''); $('#lMsg').textContent = `✓ Terhubung · ${r.models.length} model tersedia (klik kolom model untuk memilih)`; }
    catch (e) { $('#lMsg').textContent = '✗ ' + e.message; }
  };
  $('#lSave').onclick = async () => {
    const f = form();
    if (f.llm.enabled && !f.llm.model_moments) return toast('Isi model pemilih momen dulu', true);
    SETTINGS = await api('/api/settings', { method: 'POST', body: { settings: f } }); HEALTH = await api('/api/health'); paintAiHealth(); $('#lKey').value = SETTINGS.llm.api_key; toast(HEALTH.llm.enabled ? '9Router aktif dan pengaturan disimpan' : 'Pengaturan disimpan · workflow tetap memakai mode lokal');
  };
}

route().catch(e => { view.innerHTML = `<section class="page"><div class="empty">Gagal memuat: ${esc(e.message)}</div></section>`; });
