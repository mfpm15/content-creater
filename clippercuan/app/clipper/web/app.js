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
  const titles = { home: ['WORKSPACE', 'Buat Klip'], history: ['PROYEK', 'Semua proyek'], new: ['PRODUKSI', 'Buat Klip'], queue: ['HASIL', 'Antrean'], results: ['HASIL', 'Hasil & antrean'], advanced: ['EDITOR', 'Studio'], settings: ['SISTEM', 'Pengaturan'] };
  const title = titles[page] || ['CLIPPER CUAN', 'Workspace'];
  if ($('#pageContext')) $('#pageContext').textContent = title[0];
  if ($('#pageTitle')) $('#pageTitle').textContent = title[1];
  $$('.side [data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === page || (page === 'p' && a.dataset.nav === 'history')));
  $$('[data-mobile-nav]').forEach(a => { const active = a.dataset.mobileNav === page || (page === 'p' && a.dataset.mobileNav === 'history'); a.classList.toggle('on', active); if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  document.body.classList.toggle('studio-mode', page === 'p' && !!id);
  if (!INFO) { [INFO, SETTINGS, HEALTH] = await Promise.all([api('/api/info'), api('/api/settings'), api('/api/health')]); $('#sideFoot').textContent = 'Data lokal siap'; paintAiHealth(); }
  if (page === 'p' && id) return pageProject(id);
  const pages = { home: pageHome, history: pageHistory, queue: pageQueue, results: pageResults, advanced: pageAdvanced, captions: pageCaptions, settings: pageSettings, templates: pageTemplates, system: pageSystem, help: pageHelp, agent: pageAgent };
  return (pages[page] || (() => pageNew()))();
}
addEventListener('hashchange', route);
// lencana "sedang diproses" di menu Riwayat
async function badge() { try { const l = await api('/api/projects'); const n = l.filter(p => ['queued', 'running', 'rendering'].includes(p.status)).length; const b = $('#runBadge'); b.hidden = !n; b.textContent = n; } catch {} }
setInterval(badge, 4000); badge();

/* ================= BERANDA ================= */
async function pageHome() {
  const [projects, recipes, system] = await Promise.all([api('/api/projects').catch(() => []), getRecipes().catch(() => ({})), api('/api/system').catch(() => null)]);
  const recent = projects.slice(0, 4), busy = projects.filter(p => ['queued', 'running', 'rendering'].includes(p.status));
  const done = projects.filter(p => p.status === 'done');
  const primary = Object.values(recipes).filter(r => r.surface === 'primary').slice(0, 3);
  const statusLabel = { done: 'Selesai', running: 'Diproses', rendering: 'Render', queued: 'Menunggu', error: 'Gagal', candidates_ready: 'Kandidat siap', cancelled: 'Dibatalkan' };
  view.innerHTML = `<section class="page home-page">
    <section class="home-hero"><div><span class="kicker">WORKSPACE VIDEO</span><h1>Ubah video panjang menjadi klip yang siap ditinjau.</h1><p>Mulai produksi baru atau lanjutkan proyek terakhir. Semua pemrosesan berjalan dari service lokal.</p><div class="hero-actions"><a class="btn" href="#/new">Mulai dari video</a>${recent[0] ? `<a class="btn ghost" href="#/p/${esc(recent[0].id)}">Lanjutkan proyek</a>` : ''}</div></div><div class="hero-stat"><small>HASIL SIAP</small><strong>${done.reduce((n, p) => n + (+p.clips || 0), 0)}</strong><span>klip dari ${done.length} proyek</span></div></section>
    <div class="home-grid"><section class="home-section recent-section"><div class="section-head"><div><h2>Proyek terbaru</h2><p>Lanjutkan dari status terakhir.</p></div><a href="#/history">Lihat semua</a></div><div class="recent-list">${recent.length ? recent.map(p => `<a class="recent-item" href="#/p/${esc(p.id)}"><div class="recent-thumb" ${p.thumb ? `style="background-image:url('/files/${esc(p.id)}/${esc(p.thumb)}')"` : ''}></div><div><b>${esc(p.title || 'Proyek tanpa judul')}</b><span>${new Date(p.created * 1000).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })} · ${p.clips || 0} klip</span></div><em class="status-badge ${esc(p.status)}">${statusLabel[p.status] || esc(p.status)}</em></a>`).join('') : '<div class="empty compact"><b>Belum ada proyek</b><span>Mulai dari URL atau file video.</span><a class="btn sm" href="#/new">Buat klip pertama</a></div>'}</div></section>
    <aside class="home-section queue-section"><div class="section-head"><div><h2>Antrean</h2><p>Status produksi saat ini.</p></div><a href="#/queue">Buka</a></div>${busy.length ? `<div class="queue-list">${busy.slice(0, 3).map(p => `<a href="#/p/${esc(p.id)}"><span class="status-dot busy"></span><div><b>${esc(p.title || 'Memproses video')}</b><small>${Math.round((p.progress || 0) * 100)}% · ${esc(p.message || 'Menunggu')}</small></div></a>`).join('')}</div>` : '<div class="quiet-state"><span class="status-dot ok"></span><div><b>Tidak ada proses aktif</b><small>Antrean siap menerima produksi baru.</small></div></div>'}</aside></div>
    <section class="home-section preset-section"><div class="section-head"><div><h2>Preset populer</h2><p>Tiga gaya utama untuk mulai cepat.</p></div></div><div class="popular-presets">${primary.map(r => `<a href="#/new" data-home-recipe="${esc(r.id)}"><span>${esc(r.category || 'Preset')}</span><b>${esc(r.label)}</b><small>${esc(r.desc)}</small></a>`).join('')}</div></section>
    <footer class="service-strip"><span><i class="status-dot ok"></i> Service lokal aktif</span><span>Storage ${system ? esc(String(system.disk_free_gb)) + ' GB tersedia' : 'siap'}</span><span>Clipper Cuan ${esc(INFO.version)}</span></footer>
  </section>`;
  $$('[data-home-recipe]').forEach(a => a.onclick = () => store.set('homeRecipe', a.dataset.homeRecipe));
}

async function pageQueue() {
  const projects = (await api('/api/projects')).filter(p => ['queued', 'running', 'rendering', 'error', 'cancelled'].includes(p.status));
  view.innerHTML = `<section class="page"><header class="page-h"><h1>Antrean produksi</h1><p>Proses aktif, gagal, dan yang dapat dilanjutkan.</p></header><div class="queue-page">${projects.length ? projects.map(p => `<a class="queue-row" href="#/p/${esc(p.id)}"><span class="status-dot ${p.status === 'error' ? 'bad' : ['running','rendering','queued'].includes(p.status) ? 'busy' : ''}"></span><div><b>${esc(p.title || p.id)}</b><small>${esc(p.message || p.status)}</small></div><strong>${Math.round((p.progress || 0) * 100)}%</strong></a>`).join('') : '<div class="empty"><b>Antrean kosong</b><span>Tidak ada proses aktif atau gagal.</span></div>'}</div></section>`;
}
async function pageResults() { await pageHistory('c'); }
async function pageAdvanced() {
  const projects = await api('/api/projects');
  const ready = projects.filter(p => (p.clips || 0) > 0 || ['candidates_ready', 'done'].includes(p.status));
  view.innerHTML = `<section class="page"><header class="page-h"><h1>Studio Lanjutan</h1><p>Pilih proyek dengan kandidat atau hasil untuk membuka editor.</p></header><div class="project-picker">${ready.length ? ready.map(p => `<a class="picker-row" href="#/p/${esc(p.id)}"><div><b>${esc(p.title || p.id)}</b><span>${p.clips || 0} klip · ${esc(p.status)}</span></div><span>Buka studio</span></a>`).join('') : '<div class="empty"><b>Belum ada proyek untuk diedit</b><span>Buat kandidat dari Produksi Baru terlebih dahulu.</span><a class="btn sm" href="#/new">Produksi Baru</a></div>'}</div></section>`;
}

/* ================= PROYEK BARU ================= */
async function pageNew(override) {
  view.replaceChildren(tpl('tpl-new'));
  const templates = await api('/api/templates').catch(() => ({}));
  const homeRecipe = store.get('homeRecipe', ''); store.set('homeRecipe', '');
  const cfg = merge(INFO.defaults, override || store.get('lastSettings', {}));
  if (homeRecipe) cfg.recipe = homeRecipe;
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
  ['candidate_count', 'min_sec', 'max_sec', 'language', 'model', 'transcriber'].forEach(k => $('#' + k).value = cfg[k]);
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
  $('#cap_font').innerHTML = INFO.fonts.map(f => `<option>${esc(f)}</option>`).join('');
  let capStyle = cap.style === 'box' ? 'clean' : cap.style;
  const capCard = $('#capCard');
  $('#cap_enabled').checked = cap.enabled; capCard.classList.toggle('off', !cap.enabled);
  $('#cap_enabled').onchange = e => capCard.classList.toggle('off', !e.target.checked);
  $('#cap_font').value = cap.font; $('#cap_position').value = cap.position; $('#cap_color').value = cap.color; $('#cap_highlight').value = cap.highlight;
  $('#cap_wpl').value = cap.words_per_line; $('#cap_size').value = cap.size; $('#cap_upper').checked = cap.uppercase; $('#cap_pop').checked = cap.animation === 'pop';
  $('#cap_box').checked = cap.style === 'box' || !!cap.box; $('#cap_glow').checked = cap.effect === 'glow';
  const pv = () => {
    const p = $('#capPreview'), c = { ...cap, enabled: true, style: capStyle, box: $('#cap_box').checked, effect: $('#cap_glow').checked ? 'glow' : 'none', font: $('#cap_font').value,
      color: $('#cap_color').value, highlight: $('#cap_highlight').value, uppercase: $('#cap_upper').checked, words_per_line: 3 };
    p.style.fontFamily = ffam(c.font); p.style.color = c.color; p.style.fontSize = (+$('#cap_size').value / 82 * 24) + 'px';
    p.classList.toggle('glow', c.effect === 'glow'); p.style.setProperty('--glow', c.highlight);
    p.innerHTML = captionHTML({ ...c, style: c.style === 'wbw' ? 'clean' : c.style }, [{ w: 'Ini', s: 0, e: .3 }, { w: 'momen', s: .3, e: .7 }, { w: 'penting', s: .7, e: 1 }], .4);
  };
  chipGroup($('#capStyle'), capStyle, v => { capStyle = v; pv(); });
  ['cap_color', 'cap_highlight', 'cap_upper', 'cap_font', 'cap_size', 'cap_box', 'cap_glow'].forEach(k => $('#' + k).addEventListener('input', pv)); pv();

  let posTouched = false; $('#cap_position').addEventListener('change', () => posTouched = true);
  const last = store.get('lastSettings', {});
  $('#storage_lite').checked = override || 'storage' in last ? cfg.storage === 'lite' : true;   // bawaan: hemat disk
  const liteTxt = () => { $('#liteEst').textContent = $('#storage_lite').checked ? 'Contoh video 1 jam: 0 MB (ada subtitle YouTube) atau ±30–60 MB audio, + ±10–20 MB per klip. Tanpa mode hemat: ±1–2,5 GB (1080p).' : 'Video penuh diunduh (1 jam 1080p ≈ 1–2,5 GB). Preview sumber di studio lebih lengkap; render tidak butuh internet.'; };
  $('#storage_lite').addEventListener('change', liteTxt); liteTxt();
  let recipeId = override || 'recipe' in last ? (cfg.recipe ?? '') : 'auto';
  let autoRender = override || 'auto_render' in last ? cfg.auto_render !== false : true, clipCount = String(cfg.clip_count ?? 'auto');
  if (clipCount === '0' || clipCount === '') clipCount = 'auto';
  $('#auto_render').checked = autoRender;
  const autoTxt = () => { $('#autoHint').textContent = !$('#auto_render').checked ? 'Mati: kandidat menunggu kamu pilih di studio sebelum dirender.' : clipCount === 'auto' ? 'Otomatis: 15 kandidat diranking, lalu klip terbaik dirender (±1 per 3 menit video, 3–10; video ≥ 30 menit = 10 klip). Kandidat yang skornya terlalu lemah dilewati.' : `${clipCount} klip terbaik langsung dirender.`; };
  $('#auto_render').addEventListener('change', autoTxt);
  chipGroup($('#clipCount'), clipCount, v => { clipCount = v; autoTxt(); }); autoTxt();
  const Q = { output: '1080', source: 'auto', encoder: 'auto', sharpen: true, ...(cfg.quality || {}) };
  const qTxt = () => { $('#qHint').textContent = (Q.output === '2160' ? '4K (2160×3840): file ±3× lebih besar & render ±3× lebih lama. ' : Q.output === '1440' ? '1440p (1440×2560): lebih tajam di HP besar, YouTube memproses dengan codec lebih baik. ' : '1080p (1080×1920): standar Shorts/TikTok/Reels. ')
    + (Q.source === 'auto' ? 'Sumber otomatis: resolusi terbaik sampai 4K (mode hemat) atau 1440p (unduh penuh) — portrait dari video landscape butuh sumber besar agar tidak burik.' : Q.source === '1080' ? 'Sumber 1080p: crop portrait akan diperbesar ±1,8× (kurang tajam).' : `Sumber maks ${Q.source === '2160' ? '4K' : '1440p'}.`)
    + ' GPU dipakai otomatis bila ada.'; };
  chipGroup($('#qOut'), String(Q.output), v => { Q.output = v; qTxt(); }); chipGroup($('#qSrc'), String(Q.source), v => { Q.source = v; qTxt(); }); qTxt();
  getRecipes().then(rs => {
    const box = $('#recipes'), experimental = $('#experimentalRecipes'); if (!box) return;
    const prof = cfg.content_profile || 'auto';
    const card = r => `<button type="button" data-r="${esc(r.id)}" class="${r.id === recipeId ? 'on' : ''}"><span class="rb">${esc(r.category || r.badge || '')}</span><b>${esc(r.label)}</b><small>${esc(r.desc)}</small></button>`;
    const primary = Object.values(rs).filter(r => r.surface === 'primary');
    const legacy = Object.values(rs).filter(r => r.surface === 'experimental');
    box.innerHTML = primary.map(card).join('') + `<button type="button" data-r="" class="${recipeId ? '' : 'on'}"><span class="rb">Manual</span><b>Atur sendiri</b><small>Pakai kontrol Advanced tanpa preset.</small></button>`;
    if (experimental) experimental.innerHTML = legacy.map(card).join('');
    $$('[data-r]').forEach(b => b.onclick = () => {
      try { sessionStorage.setItem('draftUrl', $('#url').value); } catch {}
      const r = rs[b.dataset.r], now = collect();
      pageNew(r ? merge(now, { ...r.settings, recipe: r.id }) : { ...now, recipe: '' });
      if (r) toast(`Gaya "${r.label}" diterapkan`);
    });
  }).catch(() => { $('#recipes').innerHTML = '<span class="muted">Rekomendasi tidak bisa dimuat. Coba lagi.</span>'; });
  try { const d = sessionStorage.getItem('draftUrl'); if (d) { $('#url').value = d; $('#url').oninput(); sessionStorage.removeItem('draftUrl'); } } catch {}

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

  // efek visual: dekorasi opt-in; checkbox lama tetap tersinkron untuk kompatibilitas proyek lama
  const fxBind = (sw, row) => { const f = () => $(row).classList.toggle('dim', !$(sw).checked); $(sw).addEventListener('change', f); f(); };
  let decorationMode = cfg.decoration?.mode || (cfg.emoji.enabled ? 'smart_emoji' : 'none');
  const syncDecoration = () => {
    $$('input[name="decoration_mode"]').forEach(r => r.checked = r.value === decorationMode);
    $('#emoji_on').checked = decorationMode === 'smart_emoji';
    $('#emojiSizeRow').classList.toggle('dim', decorationMode !== 'smart_emoji');
  };
  $$('input[name="decoration_mode"]').forEach(r => r.onchange = () => { if (r.checked) { decorationMode = r.value; syncDecoration(); } });
  $('#emoji_on').checked = decorationMode === 'smart_emoji'; $('#emoji_size').value = Math.round((cfg.emoji.size || 1) * 100);
  $('#emoji_on').onchange = e => { decorationMode = e.target.checked ? 'smart_emoji' : 'none'; syncDecoration(); };
  $('#pb_on').checked = !!cfg.progress_bar.enabled; $('#pb_color').value = cfg.progress_bar.color; $('#pb_pos').value = cfg.progress_bar.position;
  $('#cta_on').checked = !!cfg.cta.enabled; $('#cta_text').value = cfg.cta.text; $('#cta_dur').value = cfg.cta.duration;
  syncDecoration(); fxBind('#pb_on', '#pbRow'); fxBind('#cta_on', '#ctaRow');

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
      content_profile: contentProfile, candidate_count: +$('#candidate_count').value, auto_render: $('#auto_render').checked,
      clip_count: clipCount === 'auto' ? 'auto' : +clipCount, duration_preset: durationPreset, min_sec: +$('#min_sec').value, max_sec: +$('#max_sec').value, language: $('#language').value, model: $('#model').value, transcriber: $('#transcriber').value,
      translate_en: $('#translate_en').checked, cut_silence: $('#cut_silence').checked, use_llm: $('#use_llm').checked, layout, smart_crop: $('#smart_crop').checked,
      split: { face: [pos[0], pos[1], fs, fs], game: [0, 0, 1, 1], face_ratio: +$('#faceRatio').value / 100 },
      caption: { ...cfg.caption, enabled: $('#cap_enabled').checked, style: capStyle, box: $('#cap_box').checked, effect: $('#cap_glow').checked ? 'glow' : 'none', font: $('#cap_font').value, size: +$('#cap_size').value, color: $('#cap_color').value, highlight: $('#cap_highlight').value, uppercase: $('#cap_upper').checked, words_per_line: +$('#cap_wpl').value, position: $('#cap_position').value, y_pct: posTouched ? null : cfg.caption.y_pct, animation: $('#cap_pop').checked ? 'pop' : 'none' },
      title: { ...cfg.title, enabled: $('#ttl_enabled').checked, preset: ttlPreset, duration: +$('#ttl_duration').value },
      quality: { ...Q }, recipe: recipeId, storage: srcMode === 'link' && $('#storage_lite').checked ? 'lite' : 'full', crop: cfg.crop,
      watermark: { enabled: $('#wm_enabled').checked, text: $('#wm_text').value, image: wmImage, position: wmPos, opacity: +$('#wm_opacity').value / 100, size: cfg.watermark.size },
      decoration: { mode: decorationMode, provenance: decorationMode === 'none' ? null : 'keyword', max_active: 1 },
      emoji: { enabled: decorationMode === 'smart_emoji', size: +$('#emoji_size').value / 100, provenance: 'keyword' },
      progress_bar: { enabled: $('#pb_on').checked, color: $('#pb_color').value, position: $('#pb_pos').value, height: cfg.progress_bar.height },
      cta: { enabled: $('#cta_on').checked, text: $('#cta_text').value, duration: +$('#cta_dur').value || 3 },
      music: { enabled: $('#mu_on').checked && !!$('#mu_file').value, file: $('#mu_file').value, volume: +$('#mu_vol').value / 100, duck: $('#mu_duck').checked },
    };
  }

  const forSubmit = st => {   // resep otomatis: gaya dipilih server sesuai konten → jangan kirim gaya dari form
    if (st.recipe !== 'auto') return st;
    const o = { ...st }; ['caption', 'title', 'decoration', 'emoji', 'progress_bar', 'layout', 'smart_crop', 'cut_silence', 'split', 'content_profile'].forEach(k => delete o[k]);
    if (o.duration_preset === 'auto') { delete o.min_sec; delete o.max_sec; }
    if (contentProfile !== 'auto') o.content_profile = contentProfile;
    return o;
  };
  $('#startTop').onclick = $('#startTop2').onclick = () => $('#start').click();
  $('#start').onclick = async () => {
    let sources = [];
    if (srcMode === 'link') { sources = links(); if (!sources.length || sources.some(s => !/^https?:\/\//i.test(s))) return toast('Tempel link video yang valid (diawali https://), satu per baris', true); }
    else { if (!upload) return toast('Pilih file video dulu', true); sources = [upload.id]; }
    const settings = forSubmit(collect());
    if (settings.min_sec >= settings.max_sec) return toast('Durasi minimum harus lebih kecil dari maksimum', true);
    if (settings.candidate_count < 5) return toast('Jumlah kandidat minimal 5', true);
    const all = collect(); store.set('lastSettings', { ...all, watermark: { ...all.watermark, image: '' } });
    try { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); } catch {}
    const start = $('#start'); start.disabled = true; start.classList.add('is-loading'); start.querySelector('span').textContent = 'Menyiapkan proyek…';
    try {
      let last;
      for (const source of sources) last = await api('/api/projects', { method: 'POST', body: { source, settings } });
      location.hash = sources.length > 1 ? '#/history' : '#/p/' + last.id;
      if (sources.length > 1) toast(`${sources.length} proyek masuk antrean`);
    } catch (e) { toast(e.message, true); start.disabled = false; start.classList.remove('is-loading'); start.querySelector('span').textContent = '▶ Run pipeline'; }
  };

  const productionOrder = ['source', 'profile', 'analysis', 'candidates', 'style', 'preview', 'render'];
  const setProductionStage = stage => {
    const at = productionOrder.indexOf(stage);
    $$('[data-stage]').forEach(panel => { panel.hidden = productionOrder.indexOf(panel.dataset.stage) > at; });
    $$('#productionFlow li').forEach((item, index) => { item.classList.toggle('on', index === at); item.classList.toggle('done', index < at); });
  };
  const sourceReady = () => srcMode === 'file' ? !!upload : links().length > 0 && links().every(s => /^https?:\/\//i.test(s));
  const revealFromSource = () => setProductionStage(sourceReady() ? 'render' : 'source');
  $('#url').addEventListener('input', revealFromSource);
  fileIn.addEventListener('change', () => setTimeout(revealFromSource));
  revealFromSource();
}

/* ---------------- dialog umum ---------------- */
function openDlg(build) { const d = $('#dlg'), b = $('#dlgBody'); b.replaceChildren(); build(b, () => d.close()); d.showModal(); }

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
    if (P.media?.remote) { v.replaceWith(Object.assign(document.createElement('p'), { className: 'hint', textContent: 'Mode hemat disk: video penuh tidak disimpan, jadi isi waktu mulai/selesai secara manual (lihat waktu di YouTube).' })); }
    else v.src = `/api/projects/${P.id}/source`;
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
async function pageHistory(initialTab = 'p') {
  view.innerHTML = '<section class="page"><header class="page-h proj-h"><div><h1>Riwayat</h1><p>Semua proyek dan semua klip hasil render, dalam satu galeri.</p></div><div class="acts"><div class="seg" id="hTab"><button data-v="p" class="on">Proyek</button><button data-v="c">Galeri klip</button></div><input class="in" id="hq" placeholder="Cari judul…" style="max-width:260px"></div></header><div class="hist" id="hl"></div></section>';
  let list = await api('/api/projects');
  const hl = $('#hl');
  const label = { done: 'selesai', running: 'diproses', queued: 'antre', error: 'gagal', cancelled: 'dibatalkan', candidates_ready: 'kandidat siap', rendering: 'render' };
  let tab = initialTab, clips = null;
  const drawClips = async () => {
    clips = clips || await api('/api/clips').catch(() => []);
    const q = $('#hq').value.toLowerCase(), items = clips.filter(c => `${c.title} ${c.project_title}`.toLowerCase().includes(q));
    hl.className = 'gal';
    if (!items.length) { hl.innerHTML = '<div class="empty">Belum ada klip yang dirender.</div>'; return; }
    hl.replaceChildren(...items.map(c => {
      const a = document.createElement('a'); a.className = 'gcard'; a.href = '#/p/' + c.project_id;
      a.innerHTML = `<video muted loop playsinline preload="none"></video><span class="sc">${Math.round((c.score || 0) / 10)}/10</span><span class="du">${fmt(c.duration)}</span><b></b><small></small>`;
      const v = $('video', a); if (c.thumb) v.poster = `/files/${c.project_id}/${c.thumb}?v=${c.version}`;
      a.onmouseenter = () => { if (!v.src) v.src = `/files/${c.project_id}/${c.file}?v=${c.version}`; v.play().catch(() => {}); };
      a.onmouseleave = () => v.pause();
      $('b', a).textContent = c.title || c.id; $('small', a).textContent = c.project_title || '';
      return a;
    }));
  };
  chipGroup($('#hTab'), tab, v => { tab = v; draw(); });
  const draw = () => {
    if (tab === 'c') return drawClips();
    hl.className = 'hist';
    const q = $('#hq').value.toLowerCase();
    const items = list.filter(p => (p.title || '').toLowerCase().includes(q));
    if (!items.length) { hl.innerHTML = '<div class="empty">Belum ada proyek. <a href="#/new" style="color:var(--acc)">Buat proyek baru →</a></div>'; return; }
    hl.replaceChildren(...items.map(p => {
      const a = document.createElement('a'); a.className = 'hcard'; a.href = '#/p/' + p.id;
      a.innerHTML = `<div class="hthumb"></div><div class="hbody"><b></b><div class="hrow"><span class="tag ${p.status}">${label[p.status] || p.status}${p.status === 'running' ? ' ' + Math.round(p.progress * 100) + '%' : ''}</span><span>${p.clips} klip</span><button class="del" title="Hapus">🗑</button></div><span class="muted" style="font-size:12px">${new Date(p.created * 1000).toLocaleString('id-ID')}</span></div>`;
      $('b', a).textContent = p.title || p.id;
      // Keep project cards stable when an older manifest references a thumbnail
      // that has already been cleaned from disk. Candidate previews remain
      // available inside Studio, while this list uses its neutral placeholder.
      $('.hthumb', a).classList.toggle('has-output', Boolean(p.clips));
      $('.del', a).onclick = async e => { e.preventDefault(); if (!confirm('Hapus proyek ini beserta semua klipnya?')) return; await api('/api/projects/' + p.id, { method: 'DELETE' }); list = list.filter(x => x !== p); draw(); badge(); };
      return a;
    }));
  };
  $('#hq').oninput = draw; $$('#hTab button').forEach(b => b.classList.toggle('on', b.dataset.v === tab)); draw();
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
    <dt>Encoder video</dt><dd>${s.encoders?.length ? '<span class="ok">✓</span> GPU: ' + esc(s.encoders.join(', ')) + ' (dipakai otomatis, cadangan CPU)' : 'CPU (libx264) — kualitas sama, render 4K lebih lama'}</dd>
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
    <div class="card"><h3>Unduhan video</h3>
      <p class="hint">Jika YouTube meminta verifikasi ("Sign in to confirm you're not a bot"), pilih browser di laptop ini yang sudah login YouTube. Cookies dibaca langsung oleh yt-dlp, tidak disimpan di aplikasi.</p>
      <div class="inrow"><select class="in" id="dCk"><option value="">Tidak memakai cookies</option><option value="chrome">Chrome</option><option value="edge">Edge</option><option value="firefox">Firefox</option><option value="brave">Brave</option><option value="safari">Safari</option><option value="opera">Opera</option></select><button class="btn" id="dSave">Simpan</button></div></div>
    <div class="card"><h3>Default proyek</h3><p class="muted">Pengaturan proyek terakhir otomatis dipakai lagi. <button class="btn ghost sm" id="rst">Kembalikan ke bawaan</button></p></div>
    <div class="card"><h3>Info</h3><p class="muted">Versi ${esc(INFO.version)}<br>Folder data &amp; hasil: <b>${esc(INFO.data_dir)}</b></p></div></section>`;
  $('#lOn').checked = L.enabled; $('#lUrl').value = L.base_url; $('#lKey').value = L.api_key; $('#lM1').value = L.model_moments; $('#lM2').value = L.model_titles; $('#lTemp').value = Math.round(L.temperature * 100);
  $('#dCk').value = SETTINGS.download?.cookies_browser || '';
  $('#dSave').onclick = async () => { SETTINGS = await api('/api/settings', { method: 'POST', body: { settings: { download: { cookies_browser: $('#dCk').value } } } }); toast('Pengaturan unduhan disimpan'); };
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

addEventListener('DOMContentLoaded', () => {
  const sideToggle = $('#sideToggle');
  sideToggle.onclick = () => { const compact = document.body.classList.toggle('side-compact'); sideToggle.setAttribute('aria-expanded', String(!compact)); store.set('clipperSideCompact', compact); };
  if (store.get('clipperSideCompact', false)) document.body.classList.add('side-compact');
  addEventListener('keydown', e => { if (e.key === 'Escape') { const d = $('dialog[open]'); if (d) d.close(); } });
  route().catch(e => { view.innerHTML = `<section class="page"><div class="empty">Gagal memuat: ${esc(e.message)}</div></section>`; });
});
