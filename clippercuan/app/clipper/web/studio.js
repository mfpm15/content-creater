/* ClipperCuan Studio — workspace proyek: preview langsung + gaya + deretan klip + crop studio + editor caption. */
'use strict';

/* ---------------- font & preview caption ---------------- */
const FONT_FILES = {
  'Montserrat ExtraBold': 'Montserrat-ExtraBold.ttf', Anton: 'Anton-Regular.ttf', 'Bebas Neue': 'BebasNeue-Regular.ttf',
  'Poppins Black': 'Poppins-Black.ttf', Bangers: 'Bangers-Regular.ttf', 'Barlow Condensed': 'BarlowCondensed-ExtraBold.ttf',
  'Instrument Serif': 'InstrumentSerif-Regular.ttf', 'Instrument Serif Italic': 'InstrumentSerif-Italic.ttf', 'Pinyon Script': 'PinyonScript-Regular.ttf',
};
(() => {
  const st = document.createElement('style');
  st.textContent = Object.entries(FONT_FILES).map(([n, f]) => `@font-face{font-family:"CC ${n}";src:url("/fonts/${f}");font-display:swap}`).join('');
  document.head.append(st);
})();
const ffam = n => FONT_FILES[n] ? `"CC ${n}"` : n === 'Georgia Italic' ? 'Georgia,serif' : n === 'Arial Black' ? '"Arial Black",Arial,sans-serif' : 'Impact,"Arial Black",sans-serif';
const fitalic = n => /Italic$/.test(n || '') || n === 'Georgia Italic';

const KEY_HINT = new Set('rahasia jangan ternyata kenapa gimana bagaimana cara trik tips kesalahan penting wajib harus terbesar terbaik terburuk jujur sebenarnya uang duit cuan gaji juta miliar gratis bahaya gila parah serius kaget viral stop berhenti sukses gagal bisnis rezeki bangkrut secret never always mistake biggest best worst money truth actually crazy insane important nobody everyone million free wow anjir astaga gokil mantap keren sedih marah takut cinta benci bangga malu nangis lucu amazing love hate funny'.split(' '));
const STOPW = new Set('yang dan di ke dari ini itu untuk dengan pada adalah juga tidak bisa akan ada kita kami saya aku kamu dia mereka atau tapi jadi karena kalau sudah belum lebih sangat banyak seperti dalam oleh agar bahwa saja lagi sekarang nanti the and that with this from have what when'.split(' '));
function keywordIdx(line) {
  let best = -1, bs = 0;
  line.forEach((w, i) => {
    const t = String(w.w).toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
    let s = KEY_HINT.has(t) ? 3 : /\d/.test(t) ? 2 : (t.length >= 6 && !STOPW.has(t) ? 1 + t.length / 20 : 0);
    if ((w.style || {}).emphasis) s = 10;
    if (s > bs) { bs = s; best = i; }
  });
  return best;
}
function chunkWords(words, per, maxc) {
  const out = []; let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    const txt = cur.map(x => x.w).join(' '), gap = i + 1 < words.length ? words[i + 1].s - w.e : 99;
    if (/[.?!…:;]$/.test(w.w) || gap > .55 || cur.length >= per || txt.length >= maxc) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  if (out.length > 1 && out.at(-1).length === 1 && out.at(-2).length < per) out.at(-2).push(...out.pop());
  return out;
}
/* HTML caption untuk waktu t (detik, relatif klip). Meniru render ASS: box/karaoke/wbw/keyword/glow. */
function captionHTML(cap, words, t) {
  if (!cap.enabled || !words?.length) return '';
  const up = s => cap.uppercase ? String(s).toUpperCase() : String(s);
  const hl = cap.highlight || '#FFC933', style = cap.style;
  const box = style === 'box' || !!cap.box;
  if (style === 'wbw') {
    const w = words.find((x, i) => t >= x.s && t < (words[i + 1]?.s ?? x.e + .3));
    return w ? `<span class="w on" style="color:${hl}">${esc(up(w.w))}</span>` : '';
  }
  const lines = chunkWords(words, Math.max(1, +cap.words_per_line || 3), +cap.max_chars || 24);
  const li = lines.findIndex((l, i) => t >= l[0].s - .05 && t < Math.min(l.at(-1).e + .15, lines[i + 1]?.[0].s ?? 1e9));
  if (li < 0) return '';
  const line = lines[li], kw = style === 'keyword' ? keywordIdx(line) : -1;
  const active = line.findIndex((w, i) => t >= w.s && t < (line[i + 1]?.s ?? 1e9));
  const onBox = c => { const h = c.replace('#', ''); const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255); return .2126 * r + .7152 * g + .0722 * b > .6 ? '#000' : '#fff'; };
  return line.map((w, i) => {
    const st = w.style || {}, isKw = i === kw, isOn = i === active && (box || style === 'karaoke');
    const css = [];
    if (st.color) css.push(`color:${st.color}`);
    if (st.font) css.push(`font-family:${ffam(st.font)}`, fitalic(st.font) ? 'font-style:italic' : '');
    if (st.scale && Math.abs(st.scale - 1) > .01) css.push(`font-size:${st.scale}em`);
    if (isKw) {
      const accentScale = Math.max(100, Math.min(115, +(cap.accent_scale || 108))) / 100;
      if ((cap.accent_mode || 'font') === 'font') {
        const accentFont = cap.accent_font || cap.font;
        css.push(`font-family:${ffam(accentFont)}`, fitalic(accentFont) ? 'font-style:italic' : '');
      }
      css.push(`color:${hl}`, `font-size:${accentScale}em`);
    }
    if (isOn && box) css.push(`background:${hl}`, `color:${onBox(hl)}`, 'text-shadow:none');
    else if (isOn) css.push(`color:${hl}`);
    return `<span class="w${isOn ? ' on' : ''}" style="${css.filter(Boolean).join(';')}">${esc(up(w.w))}</span>`;
  }).join(' ');
}
function titleSplit(t) {
  t = String(t || '').trim();
  const q = t.indexOf('?');
  if (q > 0 && q < t.length - 1) return [t.slice(0, q + 1), t.slice(q + 1).trim()];
  const w = t.split(/\s+/); if (w.length < 3) return ['', t];
  const k = Math.max(1, Math.round(w.length / 3)); return [w.slice(0, -k).join(' '), w.slice(-k).join(' ')];
}
function titleHTML(ttl, cap, title) {
  if (!ttl.enabled || !String(title || '').trim()) return '';
  const p = ttl.preset || 'bar', f = ffam(cap.font);
  if (p === 'duo') {
    const [a, b] = titleSplit(title);
    return `<div class="tt duo" style="font-family:${f}">${a ? `<span class="l1" style="--g:${ttl.glow || '#C6FF3D'}">${esc(a)}</span>` : ''}<span class="l2" style="--a:${ttl.accent || '#3DE0A0'}">${esc(b)}</span></div>`;
  }
  return `<div class="tt ${p}" style="font-family:${f};--hl:${cap.highlight}">${esc(p === 'clean' ? title : String(title).toUpperCase())}</div>`;
}
const CAPTION_SIZES = { small: 64, medium: 72, large: 84, xlarge: 96 };
const CAPTION_SIZE_LABELS = { small: 'Kecil', medium: 'Sedang', large: 'Besar', xlarge: 'Sangat Besar' };
/* ASS size is width-relative. Preview uses same 1080-wide coordinate system. */
function paintOverlay(phone, cfg, words, t, title) {
  const cap = cfg.caption, W = phone.clientWidth || 360, k = W / 1080;
  const c = $('.cc-cap', phone), tt = $('.cc-title', phone);
  c.style.fontFamily = ffam(cap.font); c.style.fontStyle = fitalic(cap.font) ? 'italic' : 'normal';
  c.style.fontSize = (cap.size * k).toFixed(2) + 'px'; c.style.lineHeight = cap.line_height || 1.12; c.style.color = cap.color;
  c.dataset.height = `~${((cap.size * (cap.line_height || 1.12) + 2 * (cap.outline || 0)) / 1920 * 100).toFixed(1)}% tinggi output`;
  const y = cap.y_pct != null && cap.y_pct !== '' ? +cap.y_pct : { bottom: 76, middle: 50, top: 20 }[cap.position || 'bottom'];
  c.style.top = y + '%';
  const popMs = Math.max(90, Math.min(300, +(cap.animation_ms || 180)));
  const popPeak = Math.max(1.05, Math.min(1.16, 1 + Math.round(popMs / 30) / 100));
  c.style.setProperty('--caption-pop-ms', `${popMs}ms`);
  c.style.setProperty('--caption-pop-peak', popPeak);
  c.classList.toggle('glow', cap.effect === 'glow');
  c.classList.toggle('pop', ['pop', 'subtle-pop', 'word-focus'].includes(cap.animation));
  c.classList.toggle('box-punch', cap.style === 'box' || !!cap.box);
  c.classList.toggle('word-focus', cap.style === 'karaoke');
  c.style.setProperty('--glow', cap.glow_color || cap.highlight);
  c.innerHTML = captionHTML(cap, words, t);
  tt.style.fontSize = Math.round((cfg.title.size || 70) * k) + 'px';
  const tEnd = cfg.title.duration ? +cfg.title.duration : 1e9;
  tt.innerHTML = t <= tEnd ? titleHTML(cfg.title, cap, title) : '';
  const wm = cfg.watermark, m = $('.cc-wm', phone);
  m.hidden = !(wm.enabled && wm.text && !wm.image); m.textContent = wm.text || '';
  m.dataset.pos = wm.position || 'br'; m.style.opacity = wm.opacity ?? .8;
  const pb = cfg.progress_bar || {}, bar = $('.cc-pb', phone);
  bar.hidden = !pb.enabled; bar.style.background = pb.color; bar.dataset.pos = pb.position || 'bottom';
}

/* ---------------- data util ---------------- */
let RECIPES = null;
const getRecipes = async () => RECIPES || (RECIPES = (await api('/api/recipes')).recipes);
const statusLabel = { draft_candidate: 'Kandidat', selected: 'Terpilih', queued: 'Antre', rendering: 'Render…', done: 'Siap', error: 'Gagal' };
const score10 = c => Math.max(0, Math.min(10, Math.round((c.score || 0) / 10)));
const isHot = c => c.hot ?? (c.score || 0) >= 75;

/* ================= STUDIO PROYEK ================= */
async function pageProject(pid) {
  view.innerHTML = `<section class="studio">
    <header class="st-head">
      <div class="st-title"><a href="#/history" class="st-back" title="Kembali ke riwayat">←</a><div><small id="sMeta" class="muted"></small><h1 id="sTitle">Memuat…</h1></div></div>
      <div class="acts"><button class="btn ghost sm" id="sDetail">Detail</button><button class="btn ghost sm" id="sFolder">Buka folder</button><button class="btn ghost sm" id="sRetry" hidden>Ulangi</button><button class="btn ghost sm danger" id="sCancel" hidden>Batalkan</button><a class="btn ghost sm" id="sManifest" target="_blank">Manifest</a><a class="btn sm" id="sZip">Download ZIP</a></div>
    </header>
    <div class="st-progress" id="sProg"><i id="sBar"></i></div>
    <p class="warn" id="sWarn" hidden></p><p class="st-auto" id="sAuto" hidden></p>
    <details id="sErr" class="card" hidden><summary>Detail error</summary><pre></pre></details>
    <div class="st-main">
      <div class="st-stage">
        <div class="st-phone" id="sPhone"><video playsinline preload="metadata"></video><img alt="" hidden><div class="cc-title"></div><div class="cc-cap"></div><div class="cc-decoration" hidden aria-hidden="true"></div><div class="cc-wm" hidden></div><div class="cc-pb" hidden></div><div class="safe" hidden></div><div class="layer-badge" id="sLayerBadge">1 layer subtitle</div><div class="st-empty" id="sEmpty"><span class="spin"></span><b>Menyiapkan kandidat…</b><small>Unduh · transkripsi · cari momen</small></div></div>
        <div class="st-stage-bar"><button class="btn ghost sm" id="sPrev" title="Klip sebelumnya" aria-label="Klip sebelumnya"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button><button class="btn sm st-play" id="sPlay" aria-label="Putar preview"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m8 5 11 7-11 7z"/></svg></button><button class="btn ghost sm" id="sNext" title="Klip berikutnya" aria-label="Klip berikutnya"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m9 5 7 7-7 7"/></svg></button><span id="sTime" class="muted">0:00</span><span class="sp"></span><span class="st-mode" id="sMode"></span><label class="check sm"><input type="checkbox" id="sSafe"> Safe area</label></div>
      </div>
      <aside class="st-panel">
        <div class="st-tabs" role="tablist" aria-label="Inspector"><button role="tab" aria-selected="true" data-tab="style" class="on">Caption</button><button role="tab" aria-selected="false" data-tab="clip">Frame</button><button role="tab" aria-selected="false" data-tab="brand">Dekorasi</button><button role="tab" aria-selected="false" data-tab="audio">Audio</button></div>
        <div class="st-tab" role="tabpanel" data-tab="style"></div><div class="st-tab" role="tabpanel" data-tab="clip" hidden></div><div class="st-tab" role="tabpanel" data-tab="brand" hidden></div><div class="st-tab" role="tabpanel" data-tab="audio" hidden><div class="pn-sec"><h4>Audio</h4><p class="muted">Musik, volume, dan ducking mengikuti pengaturan proyek.</p></div></div>
        <div class="st-apply" id="sApply" hidden><span>Gaya diubah</span><button class="btn ghost sm" id="sSaveStyle">Simpan</button><button class="btn sm" id="sRestyle">Simpan & render ulang</button></div>
      </aside>
    </div>
    <section class="st-strip">
      <div class="st-strip-h"><div class="st-count"><small>KANDIDAT</small><b id="sCount">0</b><span id="sCountTxt" class="muted"></span></div>
        <div class="acts"><div class="seg sm" id="sFilter"><button data-f="all" class="on">Semua</button><button data-f="hot">Skor tinggi</button><button data-f="sel">Terpilih</button><button data-f="done">Dirender</button></div>
          <select class="in sm" id="sGoal" aria-label="Urutkan"><option value="best_overall">Urut: skor terbaik</option><option value="strongest_hook">Hook terkuat</option><option value="densest_insight">Insight terpadat</option><option value="most_emotional">Paling emosional</option><option value="easiest_to_understand">Mudah dipahami</option><option value="series_potential">Potensi seri</option><option value="time">Waktu sumber</option></select>
          <input class="in sm" id="sSearch" type="search" placeholder="Cari…" aria-label="Cari klip">
          <button class="btn ghost sm" id="sTop3">Pilih top 3</button><button class="btn ghost sm" id="sTop5">Top 5</button><button class="btn ghost sm" id="sNone">Kosongkan</button><button class="btn ghost sm" id="sAdd">＋ Manual</button><button class="btn ghost sm" id="sSplit" hidden>Area split</button></div></div>
      <div class="st-cards" id="sCards"></div>
    </section>
    <footer class="st-foot"><span class="status-dot" id="sDot"></span><b>Render</b><span id="sFootMsg" class="muted ell"></span><span class="sp"></span><span id="sFootPct"></span><span class="hot">Skor tinggi <b id="sHot">0</b></span><button class="btn" id="sRender">Render terpilih</button><button class="btn ghost sm" id="sLog">Log</button></footer>
  </section>`;

  const phone = $('#sPhone'), vid = $('video', phone), img = $('img', phone);
  let P = null, cur = null, S = null, styleDirty = false, words = [], wordsFor = null, filter = 'all', prevStatus = null;
  const cardEls = new Map();

  /* ---------- preview ---------- */
  const clipOf = id => P?.clips.find(c => c.id === id);
  const previewTime = c => Number.isFinite(+c?.start) ? +c.start + 1 : 1;
  const rel = () => cur && cur.status === 'done' && cur.file ? vid.currentTime : vid.currentTime - (cur?.start || 0);
  const live = () => !(cur && cur.status === 'done' && cur.file);   // klip jadi = video hasil render (overlay sudah terbakar)
  function tick() {
    if (!cur) return;
    const t = rel();
    $('#sTime').textContent = `${fmt(Math.max(0, t))} / ${fmt((cur.end - cur.start) || 0)}`;
    if (live()) {
      if (!vid.paused && vid.currentTime >= cur.end) { vid.currentTime = cur.start; }
      const cfg = merge(S, cur.overrides || {});
      paintOverlay(phone, cfg, words.map(w => ({ ...w, s: w.s - cur.start, e: w.e - cur.start })), t, $('#cTitle')?.value ?? cur.title);
      const pbar = $('.cc-pb', phone); pbar.style.width = Math.min(100, Math.max(0, t / (cur.end - cur.start) * 100)) + '%';
    }
  }
  vid.addEventListener('timeupdate', tick);
  vid.addEventListener('play', () => { $('#sPlay').textContent = '❚❚'; (function loop() { if (!vid.paused) { tick(); requestAnimationFrame(loop); } })(); });
  vid.addEventListener('pause', () => $('#sPlay').textContent = '▶');
  $('#sPlay').onclick = () => vid.paused ? vid.play().catch(() => {}) : vid.pause();
  $('#sSafe').onchange = e => $('.safe', phone).hidden = !e.target.checked;
  const visible = () => ordered().filter(passes);
  $('#sPrev').onclick = () => { const l = visible(); const i = l.findIndex(c => c.id === cur?.id); if (i > 0) selectClip(l[i - 1].id); };
  $('#sNext').onclick = () => { const l = visible(); const i = l.findIndex(c => c.id === cur?.id); if (i >= 0 && i < l.length - 1) selectClip(l[i + 1].id); };

  async function loadWords(c) {
    if (wordsFor === c.id + ':' + c.start + ':' + c.end) return;
    wordsFor = c.id + ':' + c.start + ':' + c.end;
    if (c.words?.length) { words = c.words.map(w => ({ ...w, s: w.s + c.start, e: w.e + c.start })); return; }
    try { words = (await api(`/api/projects/${P.id}/words?start=${c.start}&end=${c.end}`)).words; } catch { words = []; }
  }
  async function showPreview() {
    const c = cur; if (!c || !P.media) return;
    await loadWords(c);
    const lay = (c.overrides && c.overrides.layout) || S.layout;
    phone.dataset.layout = lay;
    $('#sEmpty').hidden = true;
    if (!live()) {
      img.hidden = true; vid.hidden = false;
      const u = `/files/${P.id}/${c.file}?v=${c.version}`;
      if (!vid.src.endsWith(u)) { vid.src = u; vid.poster = `/files/${P.id}/${c.thumb}?v=${c.version}`; }
      $('.cc-cap', phone).innerHTML = ''; $('.cc-title', phone).innerHTML = ''; $('.cc-wm', phone).hidden = true; $('.cc-pb', phone).hidden = true;
      $('#sMode').textContent = 'Hasil render'; $('#sMode').className = 'st-mode done';
    } else if (P.media.remote) {
      vid.hidden = true; img.hidden = false; img.src = `/api/projects/${P.id}/frame?t=${previewTime(c).toFixed(1)}`;
      $('#sMode').textContent = 'Preview gaya (mode hemat: frame)'; $('#sMode').className = 'st-mode';
      cropPreview(c, img); tick();
    } else {
      img.hidden = true; vid.hidden = false;
      const u = `/api/projects/${P.id}/source`;
      if (!vid.src.endsWith(u)) vid.src = u;
      const go = () => { if (Math.abs(vid.currentTime - c.start) > .3 && (vid.currentTime < c.start || vid.currentTime > c.end)) vid.currentTime = c.start; tick(); };
      vid.readyState >= 1 ? go() : vid.addEventListener('loadedmetadata', go, { once: true });
      $('#sMode').textContent = 'Preview langsung · belum dirender'; $('#sMode').className = 'st-mode';
      cropPreview(c, vid); tick();
    }
  }
  function cropPreview(c, el) {   // posisi crop perkiraan: object-position dari keyframe pertama
    const lay = (c.overrides && c.overrides.layout) || S.layout;
    el.style.objectFit = ['portrait', 'square', 'split'].includes(lay) ? 'cover' : 'contain';
    const x = c.crop_keys?.[0]?.[1] ?? .5; el.style.objectPosition = `${x * 100}% ${((S.crop?.y ?? .5) * 100)}%`;
  }

  /* ---------- deretan klip ---------- */
  function ordered() {
    const g = $('#sGoal').value;
    if (g === 'time') return [...P.clips].sort((a, b) => a.start - b.start);
    const ids = P.rankings?.[g] || [];
    return [...P.clips].sort((a, b) => (ids.indexOf(a.id) + 1 || 999) - (ids.indexOf(b.id) + 1 || 999) || (b.score || 0) - (a.score || 0));
  }
  function passes(c) {
    const q = $('#sSearch').value.toLowerCase();
    if (q && !`${c.title} ${c.text || ''} ${c.topic_cluster || ''}`.toLowerCase().includes(q)) return false;
    return filter === 'all' || (filter === 'hot' && isHot(c)) || (filter === 'sel' && c.selected) || (filter === 'done' && c.status === 'done');
  }
  function card(c) {
    let el = cardEls.get(c.id);
    if (!el) {
      el = document.createElement('article'); el.className = 'st-card'; el.tabIndex = 0;
      el.innerHTML = `<div class="th"><img loading="lazy" alt=""><span class="no"></span><label class="ck" title="Pilih untuk render"><input type="checkbox"><i></i></label><span class="sc"></span><span class="du"></span><span class="stt"></span></div><b class="tl"></b>`;
      el.onclick = e => { if (!e.target.closest('.ck')) selectClip(c.id); };
      el.onkeydown = e => { if (e.key === 'Enter') selectClip(c.id); };
      $('.ck input', el).onchange = e => api(`/api/projects/${P.id}/candidates/${c.id}/action`, { method: 'POST', body: { action: 'selected', value: e.target.checked } }).then(load).catch(err => toast(err.message, true));
      cardEls.set(c.id, el);
    }
    const thumb = c.status === 'done' && c.thumb ? `/files/${P.id}/${c.thumb}?v=${c.version}` : `/api/projects/${P.id}/frame?t=${previewTime(c).toFixed(1)}`;
    const im = $('img', el); im.onerror = () => { im.onerror = null; im.removeAttribute('src'); }; if (im.dataset.src !== thumb) { im.dataset.src = thumb; im.src = thumb; }
    $('.no', el).textContent = c.rank ? '#' + String(c.rank).padStart(2, '0') : '··';
    $('.ck input', el).checked = !!c.selected;
    $('.sc', el).textContent = c.manual ? 'manual' : `${isHot(c) ? '🔥 ' : ''}${score10(c)}/10`; $('.sc', el).classList.toggle('hot', isHot(c));
    $('.du', el).textContent = fmt(c.duration || (c.end - c.start));
    $('.stt', el).textContent = statusLabel[c.status] || c.status || ''; $('.stt', el).dataset.s = c.status || '';
    $('.tl', el).textContent = c.title || c.id;
    el.classList.toggle('on', cur?.id === c.id); el.classList.toggle('sel', !!c.selected); el.classList.toggle('banned', !!c.banned);
    return el;
  }
  function drawStrip() {
    const list = ordered().filter(passes);
    $('#sCards').replaceChildren(...list.map(card));
    if (!list.length) $('#sCards').innerHTML = `<div class="st-none">${P.clips.length ? 'Tidak ada klip di filter ini.' : 'Kandidat klip akan muncul di sini.'}</div>`;
    const done = P.clips.filter(c => c.status === 'done').length, hot = P.clips.filter(isHot).length, sel = P.clips.filter(c => c.selected).length;
    $('#sCount').textContent = P.clips.length; $('#sCountTxt').textContent = `${P.clips.length} ditemukan · ${done} dirender · ${hot} hot · ${sel} dipilih`;
    $('#sHot').textContent = hot;
    const todo = P.clips.filter(c => c.selected && !['done', 'queued', 'rendering'].includes(c.status)).length;
    $('#sRender').textContent = todo ? `Render terpilih (${todo})` : sel ? 'Semua terpilih sudah dirender' : 'Pilih klip untuk dirender';
    $('#sRender').disabled = !todo;
  }
  $$('#sFilter button').forEach(b => b.onclick = () => { filter = b.dataset.f; $$('#sFilter button').forEach(x => x.classList.toggle('on', x === b)); drawStrip(); });
  $('#sGoal').onchange = drawStrip; $('#sSearch').oninput = drawStrip;
  const selectTop = n => api(`/api/projects/${pid}/candidates/top/${n}`, { method: 'POST' }).then(load).catch(e => toast(e.message, true));
  $('#sTop3').onclick = () => selectTop(3); $('#sTop5').onclick = () => selectTop(5);
  $('#sNone').onclick = () => api(`/api/projects/${pid}/candidates/select`, { method: 'POST', body: { ids: [] } }).then(load);
  $('#sAdd').onclick = () => addClipDialog(P, load);
  $('#sSplit').onclick = () => splitDialog(P, load);
  $('#sRender').onclick = async () => {
    if (styleDirty) await saveStyle(false);
    api(`/api/projects/${pid}/batch-render`, { method: 'POST', body: { ids: [] } }).then(r => { toast('Render dimulai'); load(r); }).catch(e => toast(e.message, true));
  };
  $('#sDetail').onclick = () => openDlg(b => { b.innerHTML = `<h2>Detail teknis</h2><dl class="kv"><dt>Proyek</dt><dd>${esc(P.id)}</dd><dt>Sumber</dt><dd>${esc(P.source)}</dd><dt>Status</dt><dd>${esc(P.status)}</dd><dt>Engine</dt><dd>${esc(P.engine || 'lokal')}</dd><dt>Pesan</dt><dd>${esc(P.message || 'Tidak ada')}</dd></dl>`; });
  $('#sFolder').onclick = () => api(`/api/projects/${pid}/open-folder`, { method: 'POST' }).then(r => toast('Folder: ' + r.path)).catch(e => toast(e.message, true));
  $('#sCancel').onclick = () => api(`/api/projects/${pid}/cancel`, { method: 'POST' }).then(() => toast('Membatalkan…'));
  $('#sRetry').onclick = () => api(`/api/projects/${pid}/retry`, { method: 'POST' }).then(load);
  $('#sZip').href = `/api/projects/${pid}/zip`; $('#sManifest').href = `/api/projects/${pid}/candidates/manifest`;
  $('#sLog').onclick = () => openDlg(b => { b.innerHTML = `<h2>Log proyek</h2><pre class="code">${esc([P.message, P.asr_warning, P.llm_warning, P.error, ...P.clips.filter(c => c.error).map(c => `${c.id}: ${c.error}`)].filter(Boolean).join('\n\n') || 'Tidak ada catatan.')}</pre>`; });

  /* ---------- panel: tab ---------- */
  $$('.st-tabs button').forEach(b => b.onclick = () => { $$('.st-tabs button').forEach(x => { const on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); }); $$('.st-tab').forEach(t => t.hidden = t.dataset.tab !== b.dataset.tab); });
  const markDirty = () => { styleDirty = true; $('#sApply').hidden = false; tick(); };
  async function saveStyle(rerender) {
    try { P = await api(`/api/projects/${pid}/settings`, { method: 'POST', body: { settings: S, rerender } }); styleDirty = false; $('#sApply').hidden = true; toast(rerender ? 'Render ulang dimulai' : 'Gaya disimpan untuk render berikutnya'); load(P); }
    catch (e) { toast(e.message, true); }
  }
  $('#sSaveStyle').onclick = () => saveStyle(false); $('#sRestyle').onclick = () => saveStyle(true);

  async function buildStyleTab() {
    const box = $('.st-tab[data-tab="style"]'), recipes = await getRecipes().catch(() => ({}));
    const cap = S.caption, fonts = INFO.fonts;
    const primaryRecipes = Object.values(recipes).filter(r => r.surface === 'primary');
    const advancedRecipes = Object.values(recipes).filter(r => r.surface === 'experimental');
    box.innerHTML = `<div class="pn-sec layer-stack"><h4>Layer aktif <span class="layer-ok">1 layer subtitle</span></h4><div><span>Video</span><span class="on">Crop</span><span class="on">Spoken Caption</span><span class="${S.title.enabled ? 'on' : ''}">Hook</span><span class="${S.decoration?.mode && S.decoration.mode !== 'none' ? 'on' : ''}">Decoration</span></div><small>${S.source_has_burned_captions === 'yes' ? 'Caption sumber aktif: caption tambahan dimatikan saat render.' : S.source_has_burned_captions === 'no' ? 'Sumber ditandai tanpa burned captions.' : 'Status caption bawaan sumber belum diketahui. Periksa preview bila teks tampak ganda.'}</small></div><div class="pn-sec"><h4>Preset tampilan</h4><div class="rc-grid">${primaryRecipes.map(r => `<button type="button" data-r="${esc(r.id)}" class="${(S.recipe_applied || S.recipe) === r.id ? 'on' : ''}" title="${esc(r.desc)}"><b>${esc(r.label)}</b><small>${esc(r.status || r.badge || 'Production')}</small></button>`).join('')}</div><details class="advanced-only"><summary>Advanced · kreatif & eksperimental</summary><div class="rc-grid">${advancedRecipes.map(r => `<button type="button" data-r="${esc(r.id)}" class="${(S.recipe_applied || S.recipe) === r.id ? 'on' : ''}" title="${esc(r.desc)}"><b>${esc(r.label)}</b><small>${esc(r.status || r.badge || (r.experimental ? 'Experimental' : 'Production'))}</small></button>`).join('')}</div></details></div>
      <div class="pn-sec"><h4>Font caption</h4><div class="font-grid">${fonts.map(f => `<button type="button" data-font="${esc(f)}" class="${cap.font === f ? 'on' : ''}" style="font-family:${ffam(f)};${fitalic(f) ? 'font-style:italic' : ''}">${esc(f.replace(' ExtraBold', '').replace(' Black', ''))}<small>${esc(f)}</small></button>`).join('')}</div>
        <div class="cap-sample" id="capSample"></div></div>
      <div class="pn-sec"><h4>Gaya caption</h4><div class="seg wrap" id="pStyle"><button data-v="clean">Plain</button><button data-v="karaoke">Karaoke</button><button data-v="wbw">Word by word</button><button data-v="keyword">Subtract &amp; font</button></div>
        <div class="pn-row"><span>Box highlight · kotak mengikuti kata aktif</span><div class="seg sm" id="pBox"><button data-v="on">ON</button><button data-v="off">OFF</button></div></div>
        <div class="pn-row"><span>Efek</span><div class="seg sm" id="pFx"><button data-v="none">Tanpa</button><button data-v="glow">Glow</button></div></div>
        <div class="row3"><label>Teks<input type="color" class="in color" id="pCol"></label><label>Sorotan/box<input type="color" class="in color" id="pHl"></label><label>Kata/baris<input type="number" class="in" id="pWpl" min="1" max="8"></label></div>
        <label>Font kata kunci (Subtract)<select class="in" id="pAcc">${['Instrument Serif Italic', 'Pinyon Script', 'Georgia Italic', 'Bangers', 'Anton'].map(f => `<option>${f}</option>`).join('')}</select></label>
        <label>Posisi vertikal <b id="pYv"></b><input type="range" id="pY" min="10" max="90"></label>
        <label>Ukuran caption <span title="Mapping tetap: 64 / 72 / 84 / 96 ASS units. Preview memakai skala lebar yang sama dengan renderer.">ⓘ</span><select class="in" id="pSize"><option value="small">Kecil</option><option value="medium">Sedang</option><option value="large">Besar</option><option value="xlarge">Sangat Besar</option></select> <b id="pSv"></b></label>
        <div class="pn-row"><label class="check"><input type="checkbox" id="pUp"> HURUF BESAR</label><label class="check"><input type="checkbox" id="pPop"> Animasi pop</label><label class="check"><input type="checkbox" id="pOn"> Tampilkan</label></div></div>
      <div class="pn-sec advanced-only"><h4>Hook opsional · area atas</h4><div class="seg wrap" id="pTtl"><button data-v="duo">Dua baris aksen</button><button data-v="bar">Label warna</button><button data-v="outline">Outline</button><button data-v="neon">Neon</button><button data-v="clean">Teks bersih</button><button data-v="off">Tanpa hook</button></div>
        <label>Tampil (detik, 0 = sepanjang klip)<input type="number" class="in" id="pTd" min="0" max="120"></label></div>
      <div class="pn-sec"><h4>Format proyek</h4><div class="seg wrap" id="pLay"><button data-v="portrait">9:16</button><button data-v="square">1:1</button><button data-v="blur">Blur</button><button data-v="split">Split gaming</button><button data-v="landscape">16:9</button></div>
        <div class="pn-row"><span>Kualitas hasil</span><div class="seg sm" id="pQ"><button data-v="1080">1080p</button><button data-v="1440">1440p</button><button data-v="2160">4K</button></div></div></div>`;
    const sync = () => {
      const c = S.caption;
      chipGroup($('#pStyle', box), c.style === 'box' ? 'clean' : c.style, v => { c.style = v; markDirty(); sync(); });
      chipGroup($('#pBox', box), c.box || c.style === 'box' ? 'on' : 'off', v => { c.box = v === 'on'; if (c.style === 'box') c.style = 'clean'; markDirty(); sync(); });
      chipGroup($('#pFx', box), c.effect || 'none', v => { c.effect = v; markDirty(); sync(); });
      chipGroup($('#pTtl', box), S.title.enabled ? S.title.preset : 'off', v => { S.title.enabled = v !== 'off'; S.title.role = 'hook'; S.title.duration = Math.min(5, Math.max(.5, +S.title.duration || 3)); if (v !== 'off') S.title.preset = v; markDirty(); sync(); showPreview(); });
      chipGroup($('#pLay', box), S.layout, v => { S.layout = v; markDirty(); showPreview(); });
      chipGroup($('#pQ', box), String((S.quality || {}).output || '1080'), v => { S.quality = { ...(S.quality || {}), output: v }; markDirty(); });
      $$('[data-font]', box).forEach(b => b.classList.toggle('on', b.dataset.font === c.font));
      $('#pCol', box).value = c.color; $('#pHl', box).value = c.highlight; $('#pWpl', box).value = c.words_per_line; $('#pAcc', box).value = c.accent_font || c.font || 'Barlow Condensed';
      const y = c.y_pct ?? { bottom: 76, middle: 50, top: 20 }[c.position || 'bottom']; $('#pY', box).value = y; $('#pYv', box).textContent = Math.round(y) + '%';
      S.caption_layers = 1; c.role = 'spoken-caption';
      $('#sLayerBadge').textContent = S.source_has_burned_captions === 'yes' ? 'Caption sumber · tanpa tambahan' : '1 layer subtitle';
      $('#sLayerBadge').classList.toggle('warn', S.source_has_burned_captions === 'unknown');
      const sizeLevel = c.size_level || Object.keys(CAPTION_SIZES).find(k => CAPTION_SIZES[k] === +c.size) || 'large';
      $('#pSize', box).value = sizeLevel; $('#pSv', box).textContent = `${CAPTION_SIZE_LABELS[sizeLevel]} · ${c.size} · ~${((c.size * (c.line_height || 1.12) + 2 * (c.outline || 0)) / 1920 * 100).toFixed(1)}% tinggi`;
      $('#pUp', box).checked = !!c.uppercase; $('#pPop', box).checked = c.animation === 'pop'; $('#pOn', box).checked = c.enabled; $('#pTd', box).value = S.title.duration || 0;
      const sample = [{ w: 'Ini', s: 0, e: .3 }, { w: 'rahasia', s: .3, e: .7 }, { w: 'cuan', s: .7, e: 1 }];
      const cs = $('#capSample', box); cs.style.fontFamily = ffam(c.font); cs.style.color = c.color; cs.classList.toggle('glow', c.effect === 'glow'); cs.classList.toggle('pop', ['pop', 'subtle-pop', 'word-focus'].includes(c.animation)); cs.classList.toggle('box-punch', c.style === 'box' || !!c.box); cs.style.setProperty('--glow', c.glow_color || c.highlight);
      cs.innerHTML = captionHTML({ ...c, enabled: true, words_per_line: 3, style: c.style === 'wbw' ? 'clean' : c.style }, sample, .4) || 'Contoh caption';
    };
    $$('[data-font]', box).forEach(b => b.onclick = () => { S.caption.font = b.dataset.font; markDirty(); sync(); });
    $$('[data-r]', box).forEach(b => b.onclick = () => {
      const r = recipes[b.dataset.r]; if (!r) return;
      const { content_profile, duration_preset, ...look } = r.settings;
      S = merge(S, look); S.recipe = r.id; S.recipe_applied = r.id; $$('[data-r]', box).forEach(x => x.classList.toggle('on', x === b)); markDirty(); sync(); showPreview();
      toast(`Resep "${r.label}" diterapkan ke preview. Simpan untuk dipakai saat render.`);
    });
    const bindIn = (id, fn) => $(id, box).addEventListener('input', e => { fn(e.target); markDirty(); sync(); });
    bindIn('#pCol', t => S.caption.color = t.value); bindIn('#pHl', t => { S.caption.highlight = t.value; if (S.caption.effect === 'glow') S.caption.glow_color = t.value; });
    bindIn('#pWpl', t => S.caption.words_per_line = Math.max(1, +t.value || 3)); bindIn('#pAcc', t => S.caption.accent_font = t.value);
    bindIn('#pY', t => S.caption.y_pct = +t.value); bindIn('#pSize', t => { S.caption.size_level = t.value; S.caption.size = CAPTION_SIZES[t.value]; });
    bindIn('#pUp', t => S.caption.uppercase = t.checked); bindIn('#pPop', t => S.caption.animation = t.checked ? 'pop' : 'none'); bindIn('#pOn', t => { S.caption.enabled = t.checked; S.caption_layers = 1; });
    bindIn('#pTd', t => S.title.duration = +t.value || 0);
    sync();
  }

  async function buildBrandTab() {
    const box = $('.st-tab[data-tab="brand"]'), music = await api('/api/music').catch(() => []);
    const w = S.watermark;
    box.innerHTML = `<div class="pn-sec"><h4>Watermark <label class="sw"><input type="checkbox" id="bWm"><span></span></label></h4>
        <label>Teks<input class="in" id="bWmT" maxlength="40" placeholder="@akunkamu"></label>
        <div class="inrow"><label class="btn ghost sm upbtn">＋ Logo PNG<input type="file" id="bWmF" accept="image/png,image/jpeg,image/webp" hidden></label><span class="muted ell" id="bWmN">${w.image ? esc(w.image.split(/[\\/]/).pop()) : 'tanpa logo'}</span>${w.image ? '<button class="btn ghost sm" id="bWmX">Hapus logo</button>' : ''}</div>
        <div class="seg sm" id="bWmP"><button data-v="tl">↖</button><button data-v="tr">↗</button><button data-v="c">●</button><button data-v="bl">↙</button><button data-v="br">↘</button></div>
        <label>Transparansi<input type="range" id="bWmO" min="15" max="100"></label></div>
      <div class="pn-sec"><h4>Dekorasi opt-in</h4>
        <div class="seg wrap" id="bDec"><button data-v="none">Tanpa dekorasi</button><button data-v="smart_emoji">Emoji cerdas</button><button data-v="light_illustration">Ilustrasi ringan</button></div><p class="hint">Maksimal satu dekorasi aktif. Renderer membatalkan elemen bila bertabrakan dengan caption, wajah, produk, atau HUD.</p>
        <div class="fx-row"><div><b>Emoji cerdas</b><span>Event semantik singkat dengan provenance</span></div><label class="sw"><input type="checkbox" id="bEmo"><span></span></label></div>
        <div class="fx-row"><div><b>Progress bar</b><span>Garis berjalan sepanjang klip</span></div><label class="sw"><input type="checkbox" id="bPb"><span></span></label></div>
        <label>Warna progress<input type="color" class="in color" id="bPbC"></label>
        <div class="fx-row"><div><b>CTA di akhir</b><span>Mis. "Follow untuk part 2"</span></div><label class="sw"><input type="checkbox" id="bCta"><span></span></label></div>
        <input class="in" id="bCtaT" maxlength="50">
        <div class="fx-row"><div><b>Potong jeda hening</b><span>Jump cut otomatis, klip lebih padat</span></div><label class="sw"><input type="checkbox" id="bCut"><span></span></label></div></div>
      <div class="pn-sec"><h4>Musik latar <label class="sw"><input type="checkbox" id="bMu"><span></span></label></h4>
        <select class="in" id="bMuF">${music.length ? music.map(m => `<option value="${esc(m.file)}">${esc(m.name)}</option>`).join('') : '<option value="">— unggah musik di Proyek baru —</option>'}</select>
        <label>Volume<input type="range" id="bMuV" min="3" max="60"></label></div>`;
    $('#bWm', box).checked = w.enabled; $('#bWmT', box).value = w.text || ''; $('#bWmO', box).value = Math.round((w.opacity ?? .8) * 100);
    chipGroup($('#bWmP', box), w.position, v => { S.watermark.position = v; markDirty(); });
    const decorationMode = S.decoration?.mode || (S.emoji?.enabled ? 'smart_emoji' : 'none');
    chipGroup($('#bDec', box), decorationMode, v => { S.decoration = { ...(S.decoration || {}), mode: v, provenance: v === 'none' ? null : 'keyword', max_active: 1 }; S.emoji = { ...(S.emoji || {}), enabled: v === 'smart_emoji', provenance: 'keyword' }; $('#bEmo', box).checked = v === 'smart_emoji'; markDirty(); });
    $('#bEmo', box).checked = decorationMode === 'smart_emoji'; $('#bPb', box).checked = !!S.progress_bar?.enabled; $('#bPbC', box).value = S.progress_bar?.color || '#FFC933';
    $('#bCta', box).checked = !!S.cta?.enabled; $('#bCtaT', box).value = S.cta?.text || ''; $('#bCut', box).checked = !!S.cut_silence;
    $('#bMu', box).checked = !!S.music?.enabled; $('#bMuF', box).value = S.music?.file || ''; $('#bMuV', box).value = Math.round((S.music?.volume ?? .15) * 100);
    const on = (id, fn, ev = 'input') => $(id, box).addEventListener(ev, e => { fn(e.target); markDirty(); });
    on('#bWm', t => S.watermark.enabled = t.checked); on('#bWmT', t => S.watermark.text = t.value); on('#bWmO', t => S.watermark.opacity = +t.value / 100);
    on('#bEmo', t => { S.emoji = { ...S.emoji, enabled: t.checked, provenance: 'keyword' }; S.decoration = { ...(S.decoration || {}), mode: t.checked ? 'smart_emoji' : 'none', provenance: t.checked ? 'keyword' : null, max_active: 1 }; }); on('#bPb', t => S.progress_bar = { ...S.progress_bar, enabled: t.checked }); on('#bPbC', t => S.progress_bar = { ...S.progress_bar, color: t.value });
    on('#bCta', t => S.cta = { ...S.cta, enabled: t.checked }); on('#bCtaT', t => S.cta = { ...S.cta, text: t.value }); on('#bCut', t => S.cut_silence = t.checked);
    on('#bMu', t => S.music = { ...S.music, enabled: t.checked && !!$('#bMuF', box).value }); on('#bMuF', t => S.music = { ...S.music, file: t.value }, 'change'); on('#bMuV', t => S.music = { ...S.music, volume: +t.value / 100 });
    $('#bWmF', box).onchange = async e => { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const r = await api('/api/upload', { method: 'POST', body: fd }); S.watermark.image = r.path; S.watermark.enabled = true; markDirty(); buildBrandTab(); } catch (err) { toast(err.message, true); } };
    const x = $('#bWmX', box); if (x) x.onclick = () => { S.watermark.image = ''; markDirty(); buildBrandTab(); };
  }

  function buildClipTab() {
    const box = $('.st-tab[data-tab="clip"]'), c = cur;
    if (!c) { box.innerHTML = '<p class="muted">Pilih klip di deretan bawah.</p>'; return; }
    const lay = (c.overrides && c.overrides.layout) || '';
    const opts = [...new Set([...(c.title_options || []), ...((c.post || {}).title_options || [])])].filter(Boolean).slice(0, 5);
    const bd = c.breakdown || {}, labels = { hook: 'Hook', novelty: 'Novelty', emotion_humor: 'Emosi', standalone_clarity: 'Clarity', payoff: 'Payoff', quotability: 'Quotability', visual_activity: 'Visual', information_density: 'Density', clean_ending: 'Ending' };
    const post = c.post || {};
    box.innerHTML = `<div class="pn-sec"><div class="clip-head"><span class="sc ${isHot(c) ? 'hot' : ''}">${c.manual ? 'manual' : score10(c) + '/10'}</span><b>#${esc(String(c.rank || '–'))} · ${esc(statusLabel[c.status] || c.status)}</b><span class="muted">${fmt(c.start)}–${fmt(c.end)} · ${Math.round(c.end - c.start)} dtk</span></div>
        ${c.resolution ? `<p class="ready-line"><small>HASIL</small> <b>${esc(c.resolution)}</b> <span class="muted">· ${esc(c.encoder || '')}${c.upscale > 1.3 ? ` · diperbesar ${c.upscale}×` : ''}</span></p><p class="ready-line"><small>Template yang digunakan</small> <b>${esc(c.template_name || 'Belum tercatat')}</b> <span class="muted">· ${esc(CAPTION_SIZE_LABELS[c.caption_render?.size_level] || 'Kustom')} · ${esc(c.caption_render?.font || 'font belum tercatat')} · 1 layer subtitle · ${esc(String(c.caption_render?.ass_size || '–'))} ASS · ${esc(String(c.effective_caption_height_pct || '–'))}% tinggi</span></p>` : ''}
        <p class="ready-line"><small>CONTENT READINESS</small> <b>${c.readiness ?? c.score ?? 0}/100</b> <span class="muted">· alat review editorial · confidence ${Math.round((c.confidence ?? .5) * 100)}%</span></p>
        ${[...(c.warnings || []), ...(c.render_warnings || [])].length ? `<p class="warn">${esc([...(c.warnings || []), ...(c.render_warnings || [])].join(' · '))}</p>` : ''}
        ${c.error ? `<p class="err">${esc(c.error.slice(-400))}</p>` : ''}
        <label>Judul & hook<input class="in" id="cTitle" maxlength="80"></label>
        <div class="chips" id="cOpts">${opts.map(t => `<button type="button">${esc(t)}</button>`).join('')}${llmOn() ? '<button type="button" class="ai" id="cAi">✦ Generate title (AI)</button>' : ''}</div>
        <div class="row2"><label>Mulai (dtk)<div class="inrow"><button class="btn ghost sm" data-n="s-">−</button><input class="in" id="cS" type="number" step="0.1"><button class="btn ghost sm" data-n="s+">+</button></div></label>
          <label>Selesai (dtk)<div class="inrow"><button class="btn ghost sm" data-n="e-">−</button><input class="in" id="cE" type="number" step="0.1"><button class="btn ghost sm" data-n="e+">+</button></div></label></div>
        <label>Crop mode klip ini<select class="in" id="cLay"><option value="">Ikut proyek (${esc(S.layout)})</option><option value="portrait">Portrait 9:16</option><option value="square">Square 1:1</option><option value="blur">Blur background</option><option value="split">Split gaming</option><option value="landscape">Landscape 16:9</option></select></label>
        <div class="acts"><button class="btn ghost sm" id="cCrop">✂ Crop studio</button><button class="btn ghost sm" id="cWords">✎ Editor caption</button></div></div>
      <div class="pn-sec"><h4>Caption posting & hashtag</h4><textarea class="in" rows="4" id="cPost"></textarea>
        <div class="acts"><button class="btn ghost sm" id="cCopy">Salin</button><button class="btn ghost sm" id="cPostSave">Simpan</button>${llmOn() ? '<button class="btn ghost sm" id="cPostAi">✦ Buat dengan AI</button>' : ''}</div></div>
      <div class="pn-sec"><h4>Kenapa dipilih</h4><p class="muted">${esc(c.reason || '—')}</p><div class="score-grid">${Object.entries(labels).filter(([k]) => typeof bd[k] === 'number').map(([k, l]) => `<span><b>${l}</b><i style="--v:${Math.max(0, Math.min(100, bd[k]))}%"></i><em>${bd[k]}</em></span>`).join('')}</div></div>
      <div class="pn-actions"><button class="btn" id="cSave">${c.status === 'done' ? 'Simpan & render ulang' : 'Simpan & render klip ini'}</button>
        <div class="acts">${c.status === 'done' ? `<a class="btn ghost sm" download="${esc((c.title || c.id).replace(/[\\/:*?"<>|]+/g, '').slice(0, 60))}.mp4" href="/files/${P.id}/${c.file}?v=${c.version}">⬇ MP4</a><a class="btn ghost sm" download href="/files/${P.id}/${c.srt || c.id + '.srt'}?v=${c.version}">⬇ SRT</a>` : ''}
          <button class="btn ghost sm" id="cPin">${c.pinned ? 'Unpin' : 'Pin'}</button><button class="btn ghost sm" id="cBan">${c.banned ? 'Unban' : 'Ban'}</button><button class="btn ghost sm danger" id="cDel">Hapus</button></div></div>`;
    $('#cTitle', box).value = c.title || ''; $('#cS', box).value = c.start; $('#cE', box).value = c.end; $('#cLay', box).value = lay;
    $('#cPost', box).value = [post.caption, (post.hashtags || []).join(' ')].filter(Boolean).join('\n\n');
    $('#cTitle', box).oninput = tick;
    $$('#cOpts button:not(.ai)', box).forEach(b => b.onclick = () => { $('#cTitle', box).value = b.textContent; tick(); });
    const ai = $('#cAi', box); if (ai) ai.onclick = async () => { ai.disabled = true; try { const r = await api(`/api/projects/${P.id}/clips/${c.id}/ai?kind=titles`, { method: 'POST' }); $('#cOpts', box).prepend(...r.titles.map(t => { const x = document.createElement('button'); x.type = 'button'; x.textContent = t; x.onclick = () => { $('#cTitle', box).value = t; tick(); }; return x; })); } catch (e) { toast(e.message, true); } finally { ai.disabled = false; } };
    $$('[data-n]', box).forEach(b => b.onclick = () => { const k = b.dataset.n, inp = $(k[0] === 's' ? '#cS' : '#cE', box); inp.value = (+inp.value + (k[1] === '+' ? .5 : -.5)).toFixed(1); });
    const patch = (changes, rerender = true) => api(`/api/projects/${P.id}/clips/${c.id}`, { method: 'PATCH', body: { changes, rerender } }).then(r => { toast(rerender ? 'Render dimulai' : 'Tersimpan'); load(r); }).catch(e => toast(e.message, true));
    $('#cSave', box).onclick = async () => {
      if (styleDirty) await saveStyle(false);
      const ch = { title: $('#cTitle', box).value, selected: true }, s = +$('#cS', box).value, e = +$('#cE', box).value;
      if (s !== c.start || e !== c.end) { if (e - s < 1) return toast('Durasi minimal 1 detik', true); ch.start = s; ch.end = e; }
      const nl = $('#cLay', box).value; if (nl !== lay) ch.overrides = { layout: nl || S.layout };
      patch(ch);
    };
    $('#cCrop', box).disabled = !P.media; $('#cWords', box).disabled = !P.media;
    $('#cCrop', box).onclick = () => cropStudio(P, c, S, patch, load);
    $('#cWords', box).onclick = () => captionEditor(P, c, S, words, w => patch({ words: w }));
    $('#cCopy', box).onclick = async () => { try { await navigator.clipboard.writeText($('#cPost', box).value); } catch { $('#cPost', box).select(); document.execCommand('copy'); } toast('Caption disalin'); };
    $('#cPostSave', box).onclick = () => { const v = $('#cPost', box).value, tags = v.match(/#[\p{L}\p{N}_]+/gu) || []; patch({ post: { ...post, caption: v.replace(/#[\p{L}\p{N}_]+/gu, '').trim(), hashtags: tags } }, false); };
    const pai = $('#cPostAi', box); if (pai) pai.onclick = async () => { pai.disabled = true; try { const r = await api(`/api/projects/${P.id}/clips/${c.id}/ai?kind=post`, { method: 'POST' }); $('#cPost', box).value = [r.caption, r.hashtags.join(' ')].join('\n\n'); } catch (e) { toast(e.message, true); } finally { pai.disabled = false; } };
    const act = (a, v) => api(`/api/projects/${P.id}/candidates/${c.id}/action`, { method: 'POST', body: { action: a, value: v } }).then(load).catch(e => toast(e.message, true));
    $('#cPin', box).onclick = () => act('pinned', !c.pinned); $('#cBan', box).onclick = () => act('banned', !c.banned);
    $('#cDel', box).onclick = async () => { if (!confirm(`Hapus klip "${c.title || c.id}"?`)) return; await api(`/api/projects/${P.id}/clips/${c.id}`, { method: 'DELETE' }); cur = null; load(); };
  }

  function selectClip(id) {
    cur = clipOf(id) || null; vid.pause();
    buildClipTab(); drawStrip(); showPreview();
    const el = cardEls.get(id); if (el) el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }

  /* ---------- muat & polling ---------- */
  async function load(data) {
    try { P = data && data.id ? data : await api('/api/projects/' + pid); }
    catch (e) { view.innerHTML = `<section class="page"><div class="empty">${esc(e.message)}</div></section>`; clearInterval(pollT); return; }
    P.clips = P.candidates || P.clips || [];
    if (!S || !styleDirty) S = structuredClone(P.settings);
    $('#sTitle').textContent = P.title;
    const m = P.media;
    $('#sMeta').textContent = [P.source.includes('uploads') ? 'File unggahan' : P.source, m ? `${fmt(m.duration)} · ${m.width}×${m.height}` : '', m?.remote ? 'mode hemat disk' : '', P.language ? 'bahasa ' + P.language : '', P.transcript_source || '', P.engine ? 'pemilih ' + P.engine : ''].filter(Boolean).join(' · ');
    const busyProj = ['queued', 'running', 'rendering'].includes(P.status);
    $('#sProg').hidden = !busyProj; $('#sBar').style.width = P.progress * 100 + '%';
    $('#sFootMsg').textContent = P.message; $('#sFootPct').textContent = Math.round(P.progress * 100) + '%';
    $('#sDot').className = 'status-dot ' + (P.status === 'error' ? 'bad' : busyProj ? 'busy' : 'ok');
    $('#sCancel').hidden = !['queued', 'running'].includes(P.status); $('#sRetry').hidden = !['error', 'cancelled'].includes(P.status);
    const warn = [P.asr_warning, P.llm_warning].filter(Boolean).join(' · '); $('#sWarn').hidden = !warn; $('#sWarn').textContent = warn;
    const auto = [P.settings.recipe === 'auto' && P.settings.recipe_applied ? `Resep otomatis: ${(RECIPES?.[P.settings.recipe_applied]?.label) || P.settings.recipe_applied}` : '', P.settings.layout_reason, P.download_saved, P.clip_target && P.settings.auto_render ? `${P.clip_target} klip terbaik dirender otomatis` : ''].filter(Boolean).join(' · ');
    $('#sAuto').hidden = !auto; $('#sAuto').textContent = '⚡ ' + auto;
    $('#sErr').hidden = !P.error; if (P.error) $('#sErr pre').textContent = P.error;
    $('#sZip').toggleAttribute('disabled', !P.clips.some(c => c.status === 'done'));
    $('#sSplit').hidden = S.layout !== 'split' || !m;
    if (!P.clips.length) {
      $('#sEmpty').hidden = false;
      $('#sEmpty b').textContent = P.status === 'error' ? 'Proses gagal' : P.status === 'cancelled' ? 'Dibatalkan' : P.message;
      $('#sEmpty .spin').hidden = !busyProj;
    }
    if (!$('.st-tab[data-tab="style"]').children.length) { buildStyleTab(); buildBrandTab(); }
    const keep = cur && clipOf(cur.id);
    if (keep) {
      const changed = JSON.stringify([keep.status, keep.version, keep.start, keep.end, keep.title, keep.pinned, keep.banned, keep.selected]) !== JSON.stringify([cur.status, cur.version, cur.start, cur.end, cur.title, cur.pinned, cur.banned, cur.selected]);
      cur = keep;
      const editing = document.activeElement?.closest('.st-tab[data-tab="clip"]');
      if (changed && !editing) { buildClipTab(); showPreview(); }
    } else if (P.clips.length) { cur = null; drawStrip(); selectClip(ordered()[0].id); }
    drawStrip();
    if (prevStatus && prevStatus !== 'done' && P.status === 'done') notify('ClipperCuan', `${P.title}: klip siap`);
    prevStatus = P.status;
    const busy = busyProj || P.clips.some(c => ['queued', 'rendering'].includes(c.status));
    clearInterval(pollT); if (busy) pollT = setInterval(load, 1500);
  }
  addEventListener('keydown', function keys(e) {
    if (!document.body.contains(phone)) return removeEventListener('keydown', keys);
    if (e.target.closest('input,textarea,select,dialog')) return;
    if (e.key === ' ') { e.preventDefault(); $('#sPlay').click(); } else if (e.key === 'ArrowRight') $('#sNext').click(); else if (e.key === 'ArrowLeft') $('#sPrev').click();
  });
  await getRecipes().catch(() => null);
  await load();
}

/* ================= CROP STUDIO ================= */
function cropStudio(P, C, S, patch, reload) {
  const m = P.media, dur = C.end - C.start;
  let lay = (C.overrides && C.overrides.layout) || S.layout;
  if (!['portrait', 'square'].includes(lay)) lay = 'portrait';
  const crop0 = { zoom: 1, y: .5, ...(S.crop || {}), ...((C.overrides || {}).crop || {}) };
  let zoom = +crop0.zoom || 1, cy = crop0.y ?? .5, t = 0;
  let keys = (C.crop_keys?.length ? C.crop_keys : [[0, .5]]).map(k => [...k]);
  const d = $('#dlg'); d.classList.add('full');
  openDlg((b, close) => {
    const done = () => { d.classList.remove('full'); close(); };
    b.innerHTML = `<div class="cs-head"><div><small class="eyebrow">CROP STUDIO · KEYFRAME FRAMING</small><h2>${esc(C.title || C.id)}</h2></div>
      <div class="acts"><div class="seg sm" id="csAsp"><button data-v="portrait">9:16</button><button data-v="square">1:1</button></div><button class="btn ghost sm" id="csAll" title="Pakai zoom & posisi vertikal ini untuk semua klip">⇉ Apply to all</button><button class="btn sm" id="csSave">Apply crop</button><button class="btn ghost sm" id="csClose">Tutup ×</button></div></div>
      <div class="cs-body"><div class="cs-stage"><div class="cs-frame"><img alt="Frame video"><div class="cs-box" tabindex="0"><span id="csLbl">9:16</span><i class="g1"></i><i class="g2"></i></div></div>
        <div class="cs-bar"><button class="btn sm" id="csPlay" title="Putar frame">▶</button><span id="csT" class="muted"></span><span class="sp"></span><button class="btn ghost sm" id="csAdd">＋ Keyframe</button><button class="btn ghost sm danger" id="csDel">× Keyframe</button></div>
        <div class="cs-tl" id="csTl"><div class="ph"></div></div>
        <p class="hint">Geser kotak untuk membingkai wajah/scene, lalu tambah keyframe untuk menguncinya. Tiap keyframe menahan framing sampai keyframe berikutnya (tanpa drifting). Panah ← → menggeser kotak.</p></div>
        <aside class="cs-side"><small class="eyebrow">LIVE OUTPUT</small><canvas id="csOut" width="270" height="480"></canvas>
          <label>Zoom / resize crop <b id="csZv"></b><input type="range" id="csZ" min="100" max="250"></label><p class="hint">Perkecil jendela crop untuk melewati watermark, bar hitam, atau stiker di tepi.</p>
          <label>Posisi vertikal <b id="csYv"></b><input type="range" id="csY" min="0" max="100"></label>
          <div class="cs-keys"><span>KEYFRAMES</span><b id="csN"></b></div><div id="csList" class="cs-list"></div>
          <button class="btn ghost sm" id="csReset">Reset ke tengah</button><button class="btn ghost sm" id="csAuto">Auto: ikuti wajah</button></aside></div>`;
    const img = $('img', b), box = $('.cs-box', b), frame = $('.cs-frame', b), tl = $('#csTl', b), out = $('#csOut', b);
    let cx = .5, playT = null;
    const aspect = () => lay === 'square' ? 1 : 9 / 16;
    const wFrac = () => Math.min(m.height * aspect() / zoom / m.width, 1), hFrac = () => Math.min(1 / zoom, 1);
    const held = tt => { const s = [...keys].sort((a, c) => a[0] - c[0]); let v = s[0][1]; for (const k of s) if (k[0] <= tt + 1e-6) v = k[1]; return v; };
    const place = () => {
      const w = wFrac(), h = hFrac(); cx = Math.max(w / 2, Math.min(1 - w / 2, cx));
      Object.assign(box.style, { width: w * 100 + '%', height: h * 100 + '%', left: (cx - w / 2) * 100 + '%', top: (1 - h) * cy * 100 + '%' });
      $('#csLbl', b).textContent = lay === 'square' ? '1:1' : '9:16';
      $('#csZv', b).textContent = Math.round(zoom * 100) + '%'; $('#csYv', b).textContent = Math.round(cy * 100) + '%';
      drawOut();
    };
    const drawOut = () => {
      const g = out.getContext('2d'); out.height = lay === 'square' ? 270 : 480;
      if (!img.naturalWidth) return;
      const w = wFrac() * img.naturalWidth, h = hFrac() * img.naturalHeight, x = (cx - wFrac() / 2) * img.naturalWidth, y = (img.naturalHeight - h) * cy;
      g.drawImage(img, x, y, w, h, 0, 0, out.width, out.height);
    };
    img.onload = drawOut;
    const draw = () => {
      $$('.kf', tl).forEach(n => n.remove());
      keys.forEach(k => { const n = document.createElement('button'); n.type = 'button'; n.className = 'kf' + (Math.abs(k[0] - t) < .3 ? ' cur' : ''); n.style.left = (k[0] / dur * 100) + '%'; n.title = k[0].toFixed(1) + ' dtk'; n.onclick = e => { e.stopPropagation(); seek(k[0]); }; tl.append(n); });
      $('.ph', tl).style.left = (t / dur * 100) + '%'; $('#csT', b).textContent = `${t.toFixed(1)}s / ${dur.toFixed(1)}s`;
      $('#csN', b).textContent = keys.length;
      $('#csList', b).innerHTML = keys.length <= 1 && keys[0][0] === 0 && keys[0][1] === .5 ? '<p class="hint">Belum ada keyframe — crop tengah statis.</p>' : keys.map(k => `<span>${k[0].toFixed(1)}s → ${Math.round(k[1] * 100)}%</span>`).join('');
    };
    const seek = tt => { t = Math.max(0, Math.min(dur, Math.round(tt * 2) / 2)); img.src = `/api/projects/${P.id}/frame?t=${(C.start + t).toFixed(1)}`; cx = held(t); place(); draw(); };
    tl.onclick = e => { const r = tl.getBoundingClientRect(); seek((e.clientX - r.left) / r.width * dur); };
    let drag = null;
    box.onpointerdown = e => { box.setPointerCapture(e.pointerId); drag = { x: e.clientX, y: e.clientY, cx, cy }; };
    box.onpointermove = e => { if (!drag) return; cx = drag.cx + (e.clientX - drag.x) / frame.clientWidth; const free = 1 - hFrac(); if (free > .001) cy = Math.max(0, Math.min(1, drag.cy + (e.clientY - drag.y) / frame.clientHeight / free)); place(); };
    box.onpointerup = () => drag = null;
    box.onkeydown = e => { if (['ArrowLeft', 'ArrowRight'].includes(e.key)) { cx += e.key === 'ArrowLeft' ? -.01 : .01; place(); e.preventDefault(); } };
    chipGroup($('#csAsp', b), lay, v => { lay = v; place(); });
    $('#csZ', b).value = Math.round(zoom * 100); $('#csZ', b).oninput = e => { zoom = +e.target.value / 100; place(); };
    $('#csY', b).value = Math.round(cy * 100); $('#csY', b).oninput = e => { cy = +e.target.value / 100; place(); };
    $('#csAdd', b).onclick = () => { const ex = keys.find(k => Math.abs(k[0] - t) < .3); if (ex) ex[1] = cx; else keys.push([t, cx]); keys.sort((a, c) => a[0] - c[0]); draw(); toast('Keyframe dikunci'); };
    $('#csDel', b).onclick = () => { const i = keys.findIndex(k => Math.abs(k[0] - t) < .3); if (i >= 0 && keys.length > 1) { keys.splice(i, 1); draw(); } else toast('Pindah ke keyframe untuk menghapusnya', true); };
    $('#csReset', b).onclick = () => { keys = [[0, .5]]; zoom = 1; cy = .5; $('#csZ', b).value = 100; $('#csY', b).value = 50; seek(t); };
    $('#csPlay', b).onclick = () => { if (playT) { clearInterval(playT); playT = null; $('#csPlay', b).textContent = '▶'; return; } $('#csPlay', b).textContent = '❚❚'; playT = setInterval(() => { if (t >= dur) t = -.5; seek(t + .5); }, 500); };
    const stop = () => { clearInterval(playT); };
    $('#csClose', b).onclick = () => { stop(); done(); };
    $('#csAuto', b).onclick = () => { stop(); patch({ crop_keys: null, overrides: { layout: lay, crop: { zoom, y: cy, hold: false } } }); done(); };
    $('#csSave', b).onclick = () => { stop(); patch({ crop_keys: keys.map(k => [+k[0].toFixed(2), +k[1].toFixed(4)]), overrides: { layout: lay, crop: { zoom, y: cy, hold: true } } }); done(); };
    $('#csAll', b).onclick = async () => { stop(); try { await api(`/api/projects/${P.id}/rerender`, { method: 'POST', body: { settings: { crop: { zoom, y: cy } } } }); toast('Zoom & posisi diterapkan ke semua klip'); done(); reload(); } catch (e) { toast(e.message, true); } };
    d.addEventListener('close', () => { stop(); d.classList.remove('full'); }, { once: true });
    seek(0);
  });
}

/* ================= EDITOR CAPTION (per kata) ================= */
function captionEditor(P, C, S, absWords, onSave) {
  const base = C.words?.length ? C.words : (absWords || []).map(w => ({ ...w, s: +(w.s - C.start).toFixed(3), e: +(w.e - C.start).toFixed(3) }));
  const words = base.map(w => ({ ...w, style: { ...(w.style || {}) } }));
  const cfg = merge(S, C.overrides || {}), sel = new Set();
  const d = $('#dlg'); d.classList.add('full');
  openDlg((b, close) => {
    const done = () => { d.classList.remove('full'); close(); };
    b.innerHTML = `<div class="cs-head"><div><small class="eyebrow">CAPTION EDITOR · PER-WORD STYLING</small><h2>${esc(C.title || C.id)}</h2></div><div class="acts"><button class="btn ghost sm" id="ceAll">Pilih semua</button><button class="btn ghost sm" id="ceNone">Batal pilih</button><button class="btn sm" id="ceSave">✓ Apply & render</button><button class="btn ghost sm" id="ceClose">Tutup ×</button></div></div>
      <div class="ce-body"><div class="ce-cues" id="ceCues"></div>
        <div class="ce-stage"><div class="st-phone" id="cePhone"><video playsinline controls preload="metadata"></video><img alt="" hidden><div class="cc-title"></div><div class="cc-cap"></div><div class="cc-wm" hidden></div><div class="cc-pb" hidden></div></div></div>
        <aside class="ce-side"><small class="eyebrow">PILIH KATA, LALU BERI GAYA</small><p class="muted" id="ceSel">0 kata dipilih · klik kata, Ctrl/⌘+klik untuk banyak</p>
          <label>Font<select class="in" id="ceFont"><option value="">Ikut gaya</option>${INFO.fonts.map(f => `<option>${esc(f)}</option>`).join('')}</select></label>
          <div class="row2"><label>Warna<input type="color" class="in color" id="ceCol" value="#C6FF3D"></label><label>Ukuran <b id="ceScV">130%</b><input type="range" id="ceSc" min="70" max="180" value="130"></label></div>
          <div class="acts"><button class="btn ghost sm" id="ceApplyFont">Terapkan font</button><button class="btn ghost sm" id="ceApplyCol">Terapkan warna</button><button class="btn ghost sm" id="ceApplySc">Terapkan ukuran</button></div>
          <div class="acts"><button class="btn ghost sm" id="ceEmph">★ Jadikan kata kunci</button><button class="btn ghost sm" id="ceClear">Hapus gaya</button></div>
          <p class="hint">Ketik langsung di daftar kiri untuk memperbaiki ejaan; kosongkan untuk menghapus kata. Kata kunci (★) memakai font aksen pada gaya "Subtract &amp; font".</p></aside></div>`;
    const phone = $('#cePhone', b), vid = $('video', phone);
    if (C.status === 'done' && C.file && !P.media?.remote) { vid.src = `/api/projects/${P.id}/source#t=${C.start},${C.end}`; }
    else if (!P.media?.remote) vid.src = `/api/projects/${P.id}/source#t=${C.start},${C.end}`;
    else { vid.hidden = true; const im = $('img', phone); im.hidden = false; im.src = `/api/projects/${P.id}/frame?t=${(C.start + 1).toFixed(1)}`; }
    phone.dataset.layout = cfg.layout;
    vid.addEventListener('loadedmetadata', () => { vid.currentTime = C.start; paint(); }, { once: true });
    vid.addEventListener('timeupdate', () => { if (vid.currentTime > C.end) vid.currentTime = C.start; });
    const t = () => vid.hidden ? 0 : vid.currentTime - C.start;
    const paint = () => paintOverlay(phone, cfg, words.filter(w => w.w), Math.max(0, t()), C.title);
    vid.addEventListener('timeupdate', paint);
    const lines = chunkWords(words, Math.max(1, +cfg.caption.words_per_line || 3), +cfg.caption.max_chars || 24);
    const cues = $('#ceCues', b);
    const redraw = () => {
      cues.replaceChildren(...lines.map(line => {
        const row = document.createElement('div'); row.className = 'ce-cue';
        const ts = document.createElement('button'); ts.type = 'button'; ts.className = 'ts'; ts.textContent = fmt(line[0].s) + '.' + String(Math.floor((line[0].s % 1) * 10));
        ts.onclick = () => { if (!vid.hidden) { vid.currentTime = C.start + line[0].s; } paint(); };
        row.append(ts);
        line.forEach(w => {
          const i = words.indexOf(w), inp = document.createElement('input'); inp.value = w.w; inp.size = Math.max(2, w.w.length);
          inp.className = 'ce-w' + (sel.has(i) ? ' sel' : '') + (w.style.emphasis ? ' em' : ''); if (w.style.color) inp.style.color = w.style.color;
          if (w.style.font) inp.style.fontFamily = ffam(w.style.font);
          inp.oninput = () => { w.w = inp.value.trim(); inp.size = Math.max(2, inp.value.length); paint(); };
          inp.onclick = e => { if (!(e.ctrlKey || e.metaKey || e.shiftKey)) sel.clear(); sel.has(i) && (e.ctrlKey || e.metaKey) ? sel.delete(i) : sel.add(i); $('#ceSel', b).textContent = `${sel.size} kata dipilih`; redraw(); if (!vid.hidden) vid.currentTime = C.start + w.s; };
          row.append(inp);
        });
        return row;
      }));
      paint();
    };
    const apply = p => { if (!sel.size) return toast('Pilih kata dulu', true); sel.forEach(i => Object.assign(words[i].style, p)); redraw(); };
    $('#ceSc', b).oninput = e => $('#ceScV', b).textContent = e.target.value + '%';
    $('#ceApplyFont', b).onclick = () => apply({ font: $('#ceFont', b).value || undefined });
    $('#ceApplyCol', b).onclick = () => apply({ color: $('#ceCol', b).value });
    $('#ceApplySc', b).onclick = () => apply({ scale: +$('#ceSc', b).value / 100 });
    $('#ceEmph', b).onclick = () => apply({ emphasis: true });
    $('#ceClear', b).onclick = () => { sel.forEach(i => words[i].style = {}); redraw(); };
    $('#ceAll', b).onclick = () => { words.forEach((_, i) => sel.add(i)); $('#ceSel', b).textContent = `${sel.size} kata dipilih`; redraw(); };
    $('#ceNone', b).onclick = () => { sel.clear(); $('#ceSel', b).textContent = '0 kata dipilih'; redraw(); };
    $('#ceClose', b).onclick = done;
    $('#ceSave', b).onclick = () => {
      const clean = words.filter(w => w.w).map(w => { const st = Object.fromEntries(Object.entries(w.style).filter(([, v]) => v !== undefined && v !== '')); const { style, ...r } = w; return Object.keys(st).length ? { ...r, style: st } : r; });
      onSave(clean); done();
    };
    d.addEventListener('close', () => d.classList.remove('full'), { once: true });
    if (!words.length) cues.innerHTML = '<p class="muted">Klip ini belum punya kata terdeteksi.</p>'; else redraw();
  });
}
