'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = value => {
  const node = document.createElement('span');
  node.textContent = String(value ?? '');
  return node.innerHTML.replaceAll('"', '&quot;').replaceAll("'", '&#39;');
};
const fmtTime = seconds => {
  const value = Math.max(0, Number(seconds) || 0);
  const mins = Math.floor(value / 60);
  const secs = (value % 60).toFixed(value % 1 ? 1 : 0).padStart(2, '0');
  return `${mins}:${secs}`;
};

function toast(message, bad = false) {
  const box = $('#toast');
  box.textContent = message;
  box.classList.toggle('bad', bad);
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 3200);
}

async function post(path, body) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function busy(form, enabled) {
  const button = $('button[type="submit"]', form);
  button.disabled = enabled;
  button.textContent = enabled ? 'Menganalisis…' : button.dataset.label;
}

$$('.analytics-tabs button').forEach(button => button.addEventListener('click', () => {
  $$('.analytics-tabs button').forEach(item => item.classList.toggle('active', item === button));
  $$('.analytics-panel').forEach(panel => {
    const visible = panel.dataset.panel === button.dataset.tab;
    panel.classList.toggle('active', visible);
    panel.hidden = !visible;
  });
}));

$$('.analysis-form').forEach(form => {
  const button = $('button[type="submit"]', form);
  button.dataset.label = button.textContent;
});

$('#retentionFile').addEventListener('change', event => {
  const file = event.target.files[0];
  $('#retentionFileName').textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : 'Maksimal 2 MB';
});

$('#retentionForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = $('#retentionFile').files[0];
  if (!file) return toast('Pilih file CSV retention terlebih dahulu.', true);
  if (file.size > 2_000_000) return toast('CSV melebihi batas 2 MB.', true);
  busy(form, true);
  try {
    const result = await post('/api/analytics/retention', {
      csv: await file.text(),
      transcript: $('#retentionTranscript').value,
      duration: $('#retentionDuration').value || null,
      units: $('#retentionUnits').value,
      scenes: $('#retentionScenes').value.trim() ? ((value) => value.scenes || value)(JSON.parse($('#retentionScenes').value)) : null,
    });
    const s = result.summary;
    const events = result.events.length ? result.events.map(item => `<article class="event-row ${item.kind}"><span>${item.kind === 'cliff' ? '↓ CLIFF' : '↑ SPIKE'}</span><strong>${fmtTime(item.second)}</strong><b>${item.change > 0 ? '+' : ''}${item.change}%</b><p>${escapeHtml(item.spoken || 'Tambahkan SRT untuk melihat ucapan pada titik ini.')}</p></article>`).join('') : '<p class="result-note">Tidak ditemukan perubahan tajam berdasarkan ambang diagnostik.</p>';
    const sceneSummary = result.scenes?.map(scene => `${scene.scene}: ${scene.average_sample_retention ?? 'tanpa data'}% (${scene.samples} sampel)`).join(' · ');
    const warnings = [...result.warnings, ...(sceneSummary ? [sceneSummary] : [])].map(item => `<li>${escapeHtml(item)}</li>`).join('');
    $('#retentionResult').innerHTML = `<div class="score-head"><div><small>RATA-RATA SAMPEL</small><strong>${s.average}%</strong></div><span>Diagnostik, bukan bukti sebab-akibat</span></div><div class="metric-strip"><div><small>AWAL</small><b>${s.start}%</b></div><div><small>AKHIR</small><b>${s.end}%</b></div><div><small>DROP 0–3 DETIK</small><b>${s.hook_drop}%</b></div><div><small>SAMPEL</small><b>${s.sample_count}</b></div></div><p class="result-note">Satuan: ${escapeHtml(result.normalization.units)}. Kolom lain: ${escapeHtml(result.normalization.unknown_columns.join(", ") || "tidak ada")}.</p><h3>Titik perubahan terkuat</h3><div class="event-list">${events}</div>${warnings ? `<h3>Catatan</h3><ul class="issue-list">${warnings}</ul>` : ''}`;
  } catch (error) {
    toast(error.message, true);
  } finally { busy(form, false); }
});

$('#packageForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  busy(form, true);
  try {
    const result = await post('/api/analytics/package', { title: $('#packageTitle').value, thumbnail: $('#packageThumbnail').value, transcript: $('#packageTranscript').value });
    const issues = result.issues.map(item => `<li class="${escapeHtml(item.level)}"><span>${item.level === 'ok' ? '✓' : item.level === 'error' ? '!' : '•'}</span>${escapeHtml(item.message)}</li>`).join('');
    $('#packageResult').innerHTML = `<div class="score-head"><div><small>EDITORIAL SCORE</small><strong>${result.score}</strong></div><span>Heuristik, bukan prediksi CTR</span></div><div class="metric-strip"><div><small>KARAKTER JUDUL</small><b>${result.metrics.title_chars}</b></div><div><small>KATA THUMBNAIL</small><b>${result.metrics.thumbnail_words}</b></div><div><small>KATA BERULANG</small><b>${result.metrics.overlap.length}</b></div></div><h3>Hasil pemeriksaan</h3><ul class="issue-list">${issues}</ul>`;
  } catch (error) { toast(error.message, true); }
  finally { busy(form, false); }
});

$('#hookForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  busy(form, true);
  try {
    const result = await post('/api/analytics/hook', { hook: $('#hookText').value });
    const checks = Object.entries(result.checks).map(([name, pass]) => `<li class="${pass ? 'ok' : 'warning'}"><span>${pass ? '✓' : '•'}</span>${escapeHtml(name.replaceAll('_', ' '))}</li>`).join('');
    const suggestions = result.suggestions.map(item => `<li>${escapeHtml(item)}</li>`).join('');
    $('#hookResult').innerHTML = `<div class="score-head"><div><small>REVIEW SCORE</small><strong>${result.score}</strong></div><span>Formula: ${escapeHtml(result.formula)}</span></div><h3>Pemeriksaan</h3><ul class="check-grid">${checks}</ul><h3>Saran editorial</h3><ul class="issue-list">${suggestions}</ul><p class="result-note">Skor ini hanya alat review. Validasi performa melalui retention setelah video dipublikasikan.</p>`;
  } catch (error) { toast(error.message, true); }
  finally { busy(form, false); }
});

let mappedCsv = null;
const mappingLabels = {time:'Waktu (detik)',retention:'Retensi',video_id:'ID video',views:'Views',likes:'Likes',comments:'Komentar',shares:'Shares',average_watch_seconds:'Rata-rata ditonton (detik)',completion_percent:'Completion (%)'};
$('#mappedFile').onchange = () => { mappedCsv=null; $('#mappingFields').replaceChildren(); };
$('#inspectCsv').onclick = async () => {
  try {
    const file=$('#mappedFile').files[0]; if(!file||file.size>2000000) throw new Error('Pilih CSV maksimal 2 MB');
    mappedCsv=await file.text(); const data=await post('/api/analytics/import/inspect',{csv:mappedCsv});
    $('#mappingFields').innerHTML=Object.entries(mappingLabels).map(([name,label])=>`<label>${escapeHtml(label)}<select data-map="${name}"><option value="">Tidak dipakai</option>${data.headers.map(h=>`<option value="${escapeHtml(h)}">${escapeHtml(h)}</option>`).join('')}</select></label>`).join('');
    $('#mappedResult').textContent=JSON.stringify({preview:data.preview,rows:data.row_count},null,2);
  } catch(error){toast(error.message,true)}
};
$('#mappedForm').onsubmit=async event=>{event.preventDefault();try{
  if(!mappedCsv)throw new Error('Baca header CSV terlebih dahulu');
  const mapping=Object.fromEntries($$('[data-map]').map(node=>[node.dataset.map,node.value]));
  const result=await post('/api/analytics/import',{csv:mappedCsv,platform:$('#mappedPlatform').value,mapping,units:$('#mappedUnits').value});
  $('#mappedResult').textContent=JSON.stringify(result,null,2);
}catch(error){toast(error.message,true)}};
async function loadObservations(){
  try {
    const response=await fetch('/api/analytics/observations');if(!response.ok)throw new Error('Gagal memuat observasi');
    const data=await response.json();$('#observationList').replaceChildren();
    for(const row of data.observations){
      const card=document.createElement('article'),text=document.createElement('p');text.textContent=`${row.video_id} · ${row.platform} · ${row.window} · ${row.status}: ${row.proposal}`;card.append(text);
      const metrics=document.createElement('pre');metrics.textContent=JSON.stringify(row.metrics,null,2);card.append(metrics);
      for(const [label,approve] of [['Setujui eksperimen',true],['Tolak',false]]){
        const button=document.createElement('button');button.type='button';button.textContent=label;
        button.onclick=async()=>{try{await post(`/api/analytics/observations/${encodeURIComponent(row.id)}/decision`,{revision:row.revision,approve});await loadObservations()}catch(error){toast(error.message,true)}};card.append(button);
      }
      $('#observationList').append(card);
    }
  }catch(error){toast(error.message,true)}
}
$('#observationForm').onsubmit=async event=>{event.preventDefault();try{
  const metrics={views:Number($('#observationViews').value)};if($('#observationCompletion').value!=='')metrics.completion_percent=Number($('#observationCompletion').value);
  await post('/api/analytics/observations',{video_id:$('#observationVideo').value,platform:$('#observationPlatform').value,window:$('#observationWindow').value,metrics});await loadObservations();
}catch(error){toast(error.message,true)}};
loadObservations();
