const elements = {
  form: document.getElementById('videoForm'),
  engineNotice: document.getElementById('engineNotice'),
  formEngineTitle: document.getElementById('formEngineTitle'),
  topic: document.getElementById('topicInput'),
  script: document.getElementById('scriptInput'),
  engineSelect: document.getElementById('engineSelect'),
  styleSelect: document.getElementById('styleSelect'),
  aspectSelect: document.getElementById('aspectSelect'),
  durationSelect: document.getElementById('durationSelect'),
  modelSelect: document.getElementById('modelSelect'),
  generateBtn: document.getElementById('generateBtn'),
  formStatus: document.getElementById('formStatus'),
  statusContainer: document.getElementById('statusContainer'),
  statusStep: document.getElementById('statusStep'),
  progressBar: document.getElementById('progressBar'),
  reviewPanel: document.getElementById('reviewPanel'),
  reviewTitle: document.getElementById('reviewTitle'),
  reviewDescription: document.getElementById('reviewDescription'),
  reviewGrid: document.getElementById('reviewGrid'),
  savePlanBtn: document.getElementById('savePlanBtn'),
  approveBtn: document.getElementById('approveBtn'),
  reviseBtn: document.getElementById('reviseBtn'),
  videoContainer: document.getElementById('videoContainer'),
  videoActions: document.getElementById('videoActions'),
  downloadBtn: document.getElementById('downloadBtn'),
  inspectHtmlBtn: document.getElementById('inspectHtmlBtn'),
  historyList: document.getElementById('historyList'),
};

let pollTimer = null;
let activeJobId = null;
let activeAspect = '9:16';
let activeReviewStage = null;
let activeRevision = 0;
let activeScenePlan = null;
let activeReviewEngine = null;
let resultSlug = null;
let engineRuntime = {};
let engineStyles = {};
let researchReady = false;
let brandCatalog = { revision: 0, kits: [] };
let brandsReady = false;
let motionConcepts = [];

function describeMotionConcept() {
  const selected = document.getElementById('motionConcept').value;
  const container = document.getElementById('motionConceptDetails');
  container.replaceChildren();
  for (const row of motionConcepts.filter(row => !selected || row.id === selected)) {
    const card = document.createElement('article');card.className = 'review-card';
    const title = document.createElement('h4');title.textContent = row.name;card.append(title);
    for (const key of ['idea', 'carry', 'look', 'excludes']) {const p = document.createElement('p');p.textContent = row[key];card.append(p);}
    container.append(card);
  }
}
document.getElementById('motionConcept').addEventListener('change', describeMotionConcept);
document.getElementById('motionExample').addEventListener('click', () => {
  elements.engineSelect.value = 'continuous';
  document.getElementById('motionConcept').value = 'trace';
  document.getElementById('motionVoice').value = 'music';
  document.getElementById('researchMode').value = 'provided';
  elements.topic.value = 'Dari ide menjadi langkah';
  elements.script.value = '0-4 Narasi: Mulai dari satu ide.\nTeks layar: Satu ide\nVisual: Penanda membuka jalur.\nSFX: click\n\n4-9 Narasi: Hubungkan langkah yang bermakna.\nTeks layar: Hubungkan langkah\nVisual: Penanda menelusuri hubungan.\nSFX: chime\n\n9-15 Narasi: Bangun hasil bersama.\nTeks layar: Bangun hasil\nVisual: Jalur menjadi satu rangkaian.\nSFX: click';
  elements.durationSelect.value = '15';
  describeMotionConcept();updateEngineExperience();
});

function displayBrands(data, selected = document.getElementById('brandSelect').value) {
  brandCatalog = data;
  const select = document.getElementById('brandSelect');
  select.replaceChildren(new Option('Tampilan bawaan', ''));
  for (const kit of data.kits) select.add(new Option(kit.name, kit.id));
  select.value = data.kits.some(kit => kit.id === selected) ? selected : '';
  brandsReady = true;
}

async function loadBrands() {
  brandsReady = false;
  try {
    const response = await fetch('/api/videos/brands');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Gagal memuat brand');
    displayBrands(data);
    document.getElementById('brandStatus').textContent = '';
  } catch (error) { document.getElementById('brandStatus').textContent = error.message; }
}

document.getElementById('brandSelect').addEventListener('change', event => {
  const kit = brandCatalog.kits.find(row => row.id === event.target.value);
  if (!kit) return;
  for (const key of ['name', 'wordmark', 'accent', 'background', 'text', 'font']) {
    document.getElementById(`brand${key[0].toUpperCase()}${key.slice(1)}`).value = kit[key];
  }
});
document.getElementById('reloadBrandsBtn').addEventListener('click', loadBrands);
document.getElementById('saveBrandBtn').addEventListener('click', async event => {
  const status = document.getElementById('brandStatus');
  if (!brandsReady) { status.textContent = 'Muat ulang kit dahulu agar perubahan tersimpan aman.'; return; }
  event.target.disabled = true;
  try {
    const brand = {};
    for (const key of ['name', 'wordmark', 'accent', 'background', 'text', 'font']) {
      brand[key] = document.getElementById(`brand${key[0].toUpperCase()}${key.slice(1)}`).value.trim();
    }
    const response = await fetch('/api/videos/brands', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revision: brandCatalog.revision, brand }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Gagal menyimpan brand');
    displayBrands(data, data.kits.at(-1)?.id);
    status.textContent = 'Kit tersimpan dan dipilih untuk pekerjaan baru.';
  } catch (error) { status.textContent = error.message; }
  finally { event.target.disabled = false; }
});

function escapeHtml(value) {
  const span = document.createElement('span');
  span.textContent = String(value ?? '');
  return span.innerHTML.replaceAll('"','&quot;').replaceAll("'",'&#39;');
}

function setWorkflowStep(stage) {
  document.querySelectorAll('[data-workflow-step]').forEach(node => {
    node.classList.toggle('active', node.dataset.workflowStep === stage);
  });
}

async function loadOptions() {
  try {
    const res = await fetch('/api/videos/options', { cache: 'no-store' });
    if (!res.ok) throw new Error('Gagal memuat opsi animasi');
    const data = await res.json();
    motionConcepts = data.motionConcepts || [];
    const conceptSelect = document.getElementById('motionConcept');
    conceptSelect.replaceChildren(new Option('Pilih satu konsep terlebih dahulu', ''));
    for (const concept of motionConcepts) conceptSelect.add(new Option(concept.name, concept.id));
    describeMotionConcept();
    engineRuntime=Object.fromEntries(data.engines.map(engine=>[engine.id,engine.runtimeMissing||[]]));
    engineStyles=Object.fromEntries(data.engines.map(engine=>[engine.id,engine.defaultStyle]));
    researchReady=!!data.research?.ready;
    const researchSelect = document.getElementById('researchMode');
    const webOption = researchSelect.querySelector('option[value="web"]');
    if (webOption) {
      webOption.disabled = !researchReady;
      webOption.textContent = researchReady
        ? 'Riset web + Motion Planner 9Router'
        : 'Riset web tidak tersedia — gunakan Motion Planner 9Router';
    }
    if (!researchReady && researchSelect.value === 'web') researchSelect.value = 'planner';
    elements.engineSelect.innerHTML = data.engines.map(engine =>
      `<option value="${escapeHtml(engine.id)}" ${engine.id === data.defaultEngine ? 'selected' : ''} ${engine.disabled ? 'disabled' : ''}>${escapeHtml(engine.name)}${engine.disabled ? ' - segera' : ''}</option>`
    ).join('');
    elements.styleSelect.innerHTML = data.styles.map(style =>
      `<option value="${escapeHtml(style.id)}">${escapeHtml(style.name)}</option>`
    ).join('');
    elements.aspectSelect.innerHTML = data.aspects.map(aspect =>
      `<option value="${escapeHtml(aspect.id)}" ${aspect.id === data.defaultAspect ? 'selected' : ''}>${escapeHtml(aspect.label)}</option>`
    ).join('');
    elements.durationSelect.innerHTML = data.durations.map(duration =>
      `<option value="${duration}" ${duration === data.defaultDuration ? 'selected' : ''}>${duration} Detik</option>`
    ).join('');
    elements.modelSelect.innerHTML = data.models.map(model =>
      `<option value="${escapeHtml(model.id)}" ${model.id === data.defaultModel ? 'selected' : ''}>${escapeHtml(model.name)} · ${escapeHtml(model.tier)}</option>`
    ).join('');
    updateEngineExperience();
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formStatus.className = 'form-status error';
  }
}

function updateEngineExperience() {
  const eng = elements.engineSelect.value;
  if(engineStyles[eng])elements.styleSelect.value=engineStyles[eng];
  elements.styleSelect.disabled=true;
  elements.styleSelect.title='Gaya mengikuti adapter. Variasikan shot melalui rencana adegan.';
  document.getElementById('continuousControls').hidden = !['continuous','remotion'].includes(eng);
  document.getElementById('continuousConceptFields').hidden = eng !== 'continuous';
  document.getElementById('motionConcept').required = eng === 'continuous';
  elements.formEngineTitle.textContent = '1. Buat Brief Animasi';
  elements.generateBtn.textContent = 'Buat Scene Plan';
  if (eng === 'continuous') {
    elements.engineNotice.textContent = 'Continuous Motion: satu dunia visual, elemen utama berlanjut, jeda gerak, dan render MP4 lokal. Pilih konsep sebelum membuat rencana.';
  } else if (eng === 'remotion') {
    elements.engineNotice.textContent = 'Remotion Editorial: diagram process/data/comparison atau konsep abstrak, warna brand dan caption pendek. Musik lokal tersedia; TTS opsional. Tanpa cue kata, caption memakai estimasi durasi, bukan alignment audio. Pilih kontrol render pada review adegan.';
  } else if (eng === 'threejs') {
    elements.engineNotice.innerHTML = `<strong style="color:#38bdf8">Three.js 3D WebGL Adapter</strong><br>Objek mekanis 3D per adegan dengan kamera terkontrol. Arahan di luar grammar memakai fallback editorial; periksa storyboard sebelum render.`;
  } else if (eng === 'lottie') {
    elements.engineNotice.innerHTML = `<strong style="color:#22d3ee">Lottie Motion Adapter</strong><br>Animasi vektor ringan bebas build dengan preview web interaktif dan ekspor lottie.json siap pakai.`;
  } else {
    elements.engineNotice.innerHTML = `<strong style="color:#a855f7">Opuscar / GSAP Cinematic</strong><br>Ilustrasi prosedural dengan kontrol gerak ilustrasi, lighting dan transisi pada review adegan (Output MP4). Ritme dan kualitas cerita tetap perlu ditinjau.`;
  }
  const researchSelect=document.getElementById('researchMode');
  if (!researchReady && researchSelect.value === 'web') researchSelect.value='planner';
  const mode=researchSelect.value;
  const provided=mode==='provided';
  elements.script.required=provided;
  // Model selalu dapat dipilih. Pada mode planner/web model menghasilkan treatment;
  // pada mode naskah lokal pilihan disimpan untuk perpindahan mode berikutnya.
  elements.modelSelect.disabled=false;
  elements.modelSelect.setAttribute('aria-disabled', 'false');
  const note=document.createElement('p');
  const planningNote = mode === 'web'
    ? 'Riset web akan memberi konteks bersumber, lalu model terpilih menyusun arahan kreatif, Scene Plan, dan Storyboard.'
    : provided
      ? 'Rencana lokal dari naskah tanpa panggilan model. Periksa fakta dan arahan visual sebelum menyetujui.'
      : 'Cukup masukkan judul. Model terpilih akan bertindak sebagai sutradara, penulis narasi, dan storyboard artist untuk membuat rencana video lengkap tanpa mengarang klaim faktual spesifik.';
  note.textContent=(engineRuntime[eng]?.length?`Runtime belum siap: ${engineRuntime[eng].join(', ')}. `:'')+planningNote;
  elements.engineNotice.append(note);
}

elements.engineSelect.addEventListener('change', updateEngineExperience);
document.getElementById('researchMode').addEventListener('change',updateEngineExperience);

async function loadHistory() {
  try {
    const res = await fetch('/api/videos');
    if (!res.ok) return;
    const data = await res.json();
    const videos = data.videos || [];
    if (!videos.length) {
      elements.historyList.innerHTML = '<p class="empty">Belum ada animasi tersimpan.</p>';
      return;
    }
    elements.historyList.innerHTML = videos.map(video => `
      <article class="history-card" data-project="${escapeHtml(video.slug)}">
        <button type="button" data-open="${escapeHtml(video.slug)}" style="width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:0;cursor:pointer">
          <h4>${escapeHtml(video.topic)}</h4>
          <p>${escapeHtml(video.formattedTime || '')} · ${video.duration || 5}s · ${escapeHtml(video.engine || 'opuscar')}</p>
        </button>
        <button type="button" class="danger-button" data-delete="${escapeHtml(video.slug)}" style="margin-top:10px">Hapus Project</button>
      </article>
    `).join('');
    elements.historyList.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => selectVideo(button.dataset.open)));
    elements.historyList.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', () => deleteVideo(button.dataset.delete)));
  } catch {
    elements.historyList.innerHTML = '<p class="empty">Gagal memuat riwayat.</p>';
  }
}

async function selectVideo(slug) {
  try {
    const res = await fetch(`/api/videos/${encodeURIComponent(slug)}`);
    if (!res.ok) return;
    showResult(await res.json());
  } catch (error) {
    console.error(error);
  }
}

async function deleteVideo(slug) {
  if (!window.confirm(`Hapus project "${slug}" beserta seluruh hasil render? Tindakan ini tidak dapat dibatalkan.`)) return;
  const response = await fetch(`/api/videos/${encodeURIComponent(slug)}`, { method: 'DELETE' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    elements.formStatus.textContent = data.error || 'Gagal menghapus project';
    elements.formStatus.className = 'form-status error';
    return;
  }
  elements.videoActions.style.display = 'none';
  elements.videoContainer.innerHTML = '<p style="color:var(--muted);font-size:13px">Project telah dihapus.</p>';
  loadHistory();
}

function showResult(result, aspectId) {
  resultSlug = result.slug;
  document.getElementById("aspectVariants").hidden = !resultSlug;
  const isLandscape = (aspectId || result.aspect?.id) === '16:9';
  elements.videoContainer.className = `video-preview-box ${isLandscape ? 'landscape' : ''}`;
  elements.videoContainer.style.aspectRatio=({'9:16':'9 / 16','16:9':'16 / 9','1:1':'1 / 1','4:5':'4 / 5'})[aspectId||result.aspect?.id]||'9 / 16';
  if (result.engine === 'lottie' || result.lottieUrl) {
    elements.videoContainer.innerHTML = `<iframe sandbox="allow-scripts" title="Preview animasi Lottie" src="${escapeHtml(result.htmlUrl)}" style="width:100%;height:100%;border:0"></iframe>`;
    elements.downloadBtn.href = result.lottieUrl;
    elements.downloadBtn.textContent = 'Unduh lottie.json';
  } else {
    elements.videoContainer.innerHTML = `<video controls playsinline preload="metadata" src="${escapeHtml(result.videoUrl)}">Browser Anda tidak mendukung video.</video>`;
    elements.downloadBtn.href = result.videoUrl;
    elements.downloadBtn.textContent = 'Unduh Video MP4';
  }
  elements.inspectHtmlBtn.href = result.htmlUrl || '#';
  elements.videoActions.style.display = 'flex';
  let bundle=document.getElementById('downloadBundle');
  if(!bundle){bundle=document.createElement('a');bundle.id='downloadBundle';bundle.className='secondary-button';bundle.download='production-bundle.zip';bundle.textContent='Unduh paket produksi';elements.videoActions.append(bundle)}
  bundle.href=`/api/videos/${encodeURIComponent(result.slug)}/bundle`;
  elements.videoActions.style.flexWrap='wrap';bundle.style.flex='1 1 100%';bundle.style.textAlign='center';
  let reviewBox=document.getElementById('mediaReviewResult');
  if(!reviewBox){reviewBox=document.createElement('section');reviewBox.id='mediaReviewResult';elements.videoActions.after(reviewBox)}
  reviewBox.replaceChildren();
  if(result.review){
    const heading=document.createElement('h3');heading.textContent='Pemeriksaan hasil render';
    const status=document.createElement('p');status.textContent=`${result.review.status==='passed_media_checks'?'Pemeriksaan media selesai':result.review.status==='needs_attention'?'Ada temuan untuk ditinjau':'Pemeriksaan belum lengkap atau gagal'}. Audio: ${result.review.audio?.status||'belum diukur'}. Visual: ${result.review.visual_review?.status||'belum diukur'}. Tetap periksa video secara manual.`;
    reviewBox.append(heading,status);
    if(result.review.motion_review){
      const motion=result.review.motion_review,p=document.createElement('p');
      p.textContent=`Gerak kontinu: ${motion.boundaries.length}/${motion.boundary_count_expected} batas diperiksa pada elemen utama. Seek ulang pada sampel ${motion.repeat_sample_seconds}s: ${motion.deterministic_repeat?'piksel sama':'berubah'}. ${motion.boundaries.length?'Identitas/geometri carrier diukur; kualitas cerita tetap perlu ditinjau.':'Tanpa batas adegan, kontinuitas antaradegan belum diukur.'} Tanpa shutter motion blur.`;
      reviewBox.append(p);
      if(motion.rendered_pixel_motion?.status==='measured'){
        const measured=document.createElement('p');measured.textContent=`Perubahan gambar rendah pada ${(motion.rendered_pixel_motion.low_change_fraction*100).toFixed(1)}% sampel resolusi kecil. Objek kecil dapat terlewat; angka ini bukan penilaian kualitas.`;reviewBox.append(measured);
      }
    }
    for(const issue of result.review.issues||[]){const text=document.createElement('p');text.textContent=issue;reviewBox.append(text)}
    for(const row of Object.values(result.review.delivery||{})){
      const text=document.createElement('p');text.textContent=`${row.label}: ${row.status==='passed_working_profile'?'profil kerja media terpenuhi':row.issues.map(issue=>issue.message).join('; ')}. Profil referensi, bukan verifikasi ketentuan resmi platform.`;reviewBox.append(text);
    }
    if(result.review.remotion){const text=document.createElement('p');text.textContent='Remotion: frame asli tersedia di bawah. Caption tanpa cue kata memakai estimasi durasi, bukan alignment audio. Tetap periksa keterbacaan dan isi.';reviewBox.append(text)}
    for(const name of result.review.visual_review?.screenshots||[]){if(!/^review-frame-\d{1,2}\.png$/.test(name))continue;const link=document.createElement('a');link.href=`/api/videos/${encodeURIComponent(result.slug)}/${name}`;link.textContent=`${name} · `;link.target='_blank';link.rel='noopener';reviewBox.append(link)}
  }
}

function sceneEditor(scene, index) {
  const field = (name, label, multiline = false) => `<label>${label}${multiline ? `<textarea data-scene="${index}" data-field="${name}">${escapeHtml(scene[name] || '')}</textarea>` : `<input data-scene="${index}" data-field="${name}" value="${escapeHtml(scene[name] || '')}">`}</label>`;
  const controls = scene.renderControls || {};
  const select = (name, label, choices) => `<label>${label}<select data-render-scene="${index}" data-render-field="${name}">${choices.map(value => `<option value="${value}" ${value === (controls[name] || 'legacy') ? 'selected' : ''}>${value}</option>`).join('')}</select></label>`;
  const renderControls = ['opuscar','threejs','remotion'].includes(activeReviewEngine) ? `<details><summary>Kontrol gambar yang diterapkan saat render</summary>
    <p>2D: gerak ilustrasi dan filter lighting; 3D: kamera dan intensitas lampu. Transisi mengatur panel adegan (HUD pada 3D). Pada Opuscar mekanis, objek dan aksi yang dikenali diterjemahkan menjadi gambar; periksa hasil style frames. Arahan di luar kosakata renderer tetap membutuhkan review.</p>
    ${select('camera','Kamera render',['legacy','locked','push-in','pull-out','pan-left','pan-right','orbit'])}
    ${select('lighting','Lighting render',['legacy','soft','dramatic'])}${select('transition','Transisi render',['legacy','fade','cut','slide'])}
    <label>Kekuatan kamera (0–1)<input type="number" min="0" max="1" step="0.05" data-render-scene="${index}" data-render-field="strength" value="${escapeHtml(controls.strength ?? .5)}"></label></details>` : '';
  return `<article class="review-card scene-editor">
    <h4>Adegan ${index + 1} · ${escapeHtml(scene.start)}-${escapeHtml(scene.end)}s</h4>
    <div class="editor-row">${field('start','Mulai')}${field('end','Selesai')}</div>
    ${field('narration','Narasi',true)}${field('onScreenText','Teks layar')}${field('visual','Visual shot',true)}
    <div class="editor-row">${field('visualFamily','Visual family')}${field('shotPurpose','Tujuan shot')}</div>
    ${field('directionSubject','Objek utama')}${field('action','Aksi')}${field('setting','Setting')}${field('composition','Komposisi',true)}
    <div class="editor-row">${field('foreground','Foreground')}${field('midground','Midground')}</div>
    ${renderControls}${field('background','Background')}${field('camera','Arahan kamera',true)}${field('lighting','Arahan lighting')}
    <div class="editor-row">${field('colorMood','Color mood')}${field('transition','Transisi')}</div>
    ${field('typography','Tipografi')}${field('continuityToken','Objek penghubung antaradegan')}${field('continuity','Kontinuitas',true)}${field('soundCue','Sound cue')}
    ${['remotion','lottie'].includes(activeReviewEngine) ? `<details><summary>Diagram berlabel (opsional)</summary>
      <p>Gunakan label dari naskah: proses 2–5 langkah, perbandingan 2 sisi. Kosongkan untuk visual editorial.</p>
      <textarea data-diagram="${index}" rows="4" placeholder='{"kind":"process","labels":["Input","Hasil"]}'>${escapeHtml(scene.diagram ? JSON.stringify(scene.diagram,null,2) : '')}</textarea></details>` : ''}
    <details><summary>Timing visual per kata (opsional)</summary>
      <p>Tempel seluruh kata narasi beserta timestamp dalam detik dari awal video. Ini timing yang Anda berikan, bukan alignment audio otomatis. Angka dan negasi harus tetap lengkap.</p>
      <label>Daftar JSON [{"word":"Halo","start":0,"end":0.5}]
        <textarea data-cues="${index}" rows="4">${escapeHtml(JSON.stringify(scene.wordCues || [], null, 2))}</textarea>
      </label>
      <label>Indeks kata pemicu visual (mulai 0; kosong = bawaan)
        <input data-cue-index="${index}" type="number" min="0" step="1" value="${escapeHtml(scene.visualCueWord ?? '')}">
      </label>
      <small>Lottie: bentuk dan judul; Opuscar: judul dan panel visual; Three.js: judul dan awal aksi objek mekanis. Efek lain dan waktu narasi tidak diubah. Timing perlu dibandingkan dengan audio hasil render.</small>
    </details>
  </article>`;
}

function researchMarkup(research) {
  if (!research) return '<div class="review-card"><h4>Research belum tersedia</h4></div>';
  const sources = (research.sources || []).map(source => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">[${source.id}] ${escapeHtml(source.title)}</a><small style="display:block;color:var(--muted)">${escapeHtml(source.publisher)} · ${escapeHtml(source.quality)}</small></li>`).join('');
  return `<article class="review-card research-card"><h4>Research & Sources · ${escapeHtml(research.provider)}</h4><p style="white-space:pre-wrap">${escapeHtml(research.summary)}</p><details open><summary>${research.sourceCount || 0} sumber grounding</summary><ol>${sources}</ol></details></article>`;
}

function renderReview(job) {
  elements.approveBtn.disabled = false;
  activeReviewEngine = job.engine;
  activeScenePlan = structuredClone(job.scenePlan);
  activeJobId = job.jobId;
  activeRevision = job.revision || 0;
  activeAspect = job.aspect || activeAspect;
  elements.reviewPanel.style.display = 'block';
  if (job.status === 'awaiting_scene_plan') {
    activeReviewStage = 'scene_plan';
    setWorkflowStep('scene_plan');
    elements.reviewTitle.textContent = 'Review Narasi & Scene Plan';
    elements.reviewDescription.textContent = 'Periksa strategi kreatif, sumber bila tersedia, struktur hook hingga payoff, timing, narasi, visual, kamera, pencahayaan, transisi, audio, dan continuity sebelum membuat Storyboard.';
    elements.reviewGrid.innerHTML = researchMarkup(job.research) + (job.scenePlan?.scenes || []).map(sceneEditor).join('');
    elements.approveBtn.textContent = 'Setujui Scene Plan & Buat Storyboard';
    elements.reviseBtn.style.display = 'none';
  } else {
    activeReviewStage = 'storyboard';
    setWorkflowStep('storyboard');
    elements.reviewTitle.textContent = 'Review Storyboard';
    elements.reviewDescription.textContent = 'Periksa setiap kartu shot sebagai keputusan produksi: komposisi, kedalaman, aksi, kamera, lighting, tipografi, transisi, sound cue, dan kesinambungan. Setujui hanya jika seluruh film sudah koheren.';
    elements.reviewGrid.innerHTML = (job.scenePlan?.scenes || []).map(sceneEditor).join('');
    elements.approveBtn.textContent = 'Setujui Storyboard & Mulai Render';
    elements.reviseBtn.style.display = 'inline-flex';
  }
  if (job.visualReview && job.status === 'awaiting_storyboard') {
    const card=document.createElement('section');card.className='review-card';
    const title=document.createElement('h4');title.textContent='Review visual dari renderer';card.append(title);
    const note=document.createElement('p');note.textContent=job.visualReview.status==='sampled'
      ? 'Periksa gambar tiap shot sebelum menyetujui. Pemeriksaan otomatis mencakup layout dan pengulangan frame; makna, estetika, serta audio tetap perlu review.'
      : 'Review visual belum lulus. Perbaiki arahan melalui editor, simpan, lalu setujui ulang Scene Plan untuk membuat preview baru.';
    card.append(note);
    elements.approveBtn.disabled=job.visualReview.status!=='sampled';
    for(const issue of job.visualReview.issues||[]) {
      const p=document.createElement('p');p.textContent=`${Number.isInteger(issue.scene)?'Adegan '+(issue.scene+1)+': ':''}${issue.reason}`;card.append(p);
    }
    if(job.visualContactSheet && /^\/api\/videos\/[a-z0-9-]+\/contact-sheet\.png$/.test(job.visualContactSheet)) {
      const image=document.createElement('img');image.src=job.visualContactSheet;image.alt='Contact sheet storyboard';image.style.width='100%';card.append(image);
    }
    const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Lihat semua style frames';details.append(summary);
    const gallery=document.createElement('div');gallery.style='display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px';
    for(const [index,url] of (job.visualFrames||[]).entries()) {
      if(!/^\/api\/videos\/[a-z0-9-]+\/review-frame-\d{1,3}\.png$/.test(url))continue;
      const image=document.createElement('img');image.src=url;image.alt=`Style frame adegan ${index+1}`;image.loading='lazy';image.style.width='100%';gallery.append(image);
    }
    details.append(gallery);card.append(details);
    elements.reviewGrid.prepend(card);
  }
  if (job.scenePlan?.brand) {
    const note = document.createElement('p');
    note.textContent = `Brand pekerjaan: ${job.scenePlan.brand.name} (salinan tetap)`;
    elements.reviewGrid.prepend(note);
  }
  if(job.engine==='remotion'){
    const note=document.createElement('p');note.textContent=`Remotion · audio ${job.scenePlan?.audioMode==='music'?'musik lokal tanpa dubbing':'TTS'}. Caption tanpa cue kata dibagi dengan estimasi; periksa terhadap audio. Keluarga selain process/data/comparison memakai diagram konsep.`;
    elements.reviewGrid.prepend(note);
  }
  const narrativeCard=document.createElement('section');narrativeCard.className='review-card';
  const narrativeTitle=document.createElement('h4');narrativeTitle.textContent='Narasi utuh · sumber urutan scene';
  const narrativeText=document.createElement('p');narrativeText.style.whiteSpace='pre-wrap';
  narrativeText.textContent=(job.scenePlan?.scenes || []).map(scene=>scene.narration).join('\n\n');
  narrativeCard.append(narrativeTitle,narrativeText);elements.reviewGrid.prepend(narrativeCard);
  if(job.status==='awaiting_storyboard' && job.productionPacket){
    const prompts=document.createElement('section');prompts.className='review-card';
    const title=document.createElement('h4');title.textContent='Prompt produksi per shot';prompts.append(title);
    for(const shot of job.productionPacket.shots){
      const details=document.createElement('details'),summary=document.createElement('summary'),text=document.createElement('pre');
      summary.textContent=`${shot.scene} · ${shot.start}–${shot.end}s`;text.style.whiteSpace='pre-wrap';text.textContent=shot.prompt;
      details.append(summary,text);
      for(const limitation of shot.limitations){const note=document.createElement('p');note.textContent=limitation;details.append(note);}
      prompts.append(details);
    }
    elements.reviewGrid.append(prompts);
  }
  const rateCard=document.createElement('label');rateCard.className='review-card';
  rateCard.textContent='Frame rate output';
  const rateSelect=document.createElement('select');rateSelect.id='reviewFps';
  for(const rate of [30,60]){const option=new Option(`${rate} fps`,String(rate));option.selected=rate===(job.scenePlan?.fps ?? 30);rateSelect.add(option);}
  rateCard.append(rateSelect);elements.reviewGrid.prepend(rateCard);
  if (job.scenePlan?.creativeDirection) {
    const section = document.createElement('section');section.className = 'review-card';
    const title = document.createElement('h4');title.textContent = 'Arahan kreatif';section.append(title);
    for (const [key, value] of Object.entries(job.scenePlan.creativeDirection)) {
      const p = document.createElement('p');p.textContent = `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`;section.append(p);
    }
    elements.reviewGrid.prepend(section);
  }
  if (job.scenePlan?.motionDesign) {
    const note = document.createElement('p');
    const cfg = job.scenePlan.motionDesign;
    note.textContent = `Film kontinu: ${motionConcepts.find(c => c.id === cfg.concept)?.name || cfg.concept}. Carrier berlanjut; audio ${cfg.voiceMode === 'music' ? 'prosedural tanpa dubbing' : 'TTS'}. Timing tetap memerlukan review.`;
    elements.reviewGrid.prepend(note);
    const sheet=job.scenePlan.motionBeatSheet;
    if(sheet){
      const card=document.createElement('section');card.className='review-card';
      const title=document.createElement('h4');title.textContent='Beat sheet · ritme dan carry';card.append(title);
      for(const beat of sheet.beats){const p=document.createElement('p');p.textContent=`${beat.start}–${beat.end}s · elemen utama berlanjut · tahan diam ${beat.holdStart.toFixed(2)}–${beat.holdEnd.toFixed(2)}s · ${beat.picture}`;card.append(p)}
      for(const text of sheet.advisories){const p=document.createElement('p');p.textContent=text;card.append(p)}
      elements.reviewGrid.prepend(card);
    }
  }
}

function collectEditedPlan() {
  const scenes = structuredClone(activeScenePlan?.scenes || []);
  elements.reviewGrid.querySelectorAll('[data-scene]').forEach(input => {
    const index = Number(input.dataset.scene);
    scenes[index] ||= {};
    const value = ['start','end'].includes(input.dataset.field) ? Number(input.value) : input.value.trim();
    scenes[index][input.dataset.field] = value;
  });
  elements.reviewGrid.querySelectorAll('[data-cues]').forEach(input => {
    const index = Number(input.dataset.cues);
    let cues;
    try { cues = JSON.parse(input.value || '[]'); }
    catch { throw new Error(`JSON timestamp adegan ${index + 1} tidak valid`); }
    if (!Array.isArray(cues)) throw new Error(`Timestamp adegan ${index + 1} harus berupa daftar`);
    if (cues.length || scenes[index].wordCues) scenes[index].wordCues = cues;
    const cueIndex = elements.reviewGrid.querySelector(`[data-cue-index="${index}"]`).value;
    if (cueIndex !== '') scenes[index].visualCueWord = Number(cueIndex);
    else delete scenes[index].visualCueWord;
  });
  elements.reviewGrid.querySelectorAll('[data-diagram]').forEach(input => {
    const index=Number(input.dataset.diagram);
    if(!input.value.trim()){delete scenes[index].diagram;return;}
    try {scenes[index].diagram=JSON.parse(input.value);}
    catch {throw new Error(`JSON diagram adegan ${index+1} tidak valid`);}
  });
  const controls = new Map();
  elements.reviewGrid.querySelectorAll('[data-render-scene]').forEach(input => {
    const index = Number(input.dataset.renderScene);
    if (!controls.has(index)) controls.set(index, {});
    controls.get(index)[input.dataset.renderField] = input.dataset.renderField === 'strength' ? Number(input.value) : input.value;
  });
  for (const [index, value] of controls) {
    if (scenes[index].renderControls || ['camera','lighting','transition'].some(key => value[key] !== 'legacy')) scenes[index].renderControls = value;
  }
  const plan={ ...structuredClone(activeScenePlan), scenes };
  const rate=Number(document.getElementById("reviewFps")?.value ?? plan.fps ?? 30);
  if(plan.fps!==undefined || rate!==30)plan.fps=rate;
  return plan;
}

async function saveEditedPlan() {
  const response = await fetch(`/api/videos/jobs/${encodeURIComponent(activeJobId)}/edit`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage: activeReviewStage, revision: activeRevision, scenePlan: collectEditedPlan() }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Gagal menyimpan perubahan');
  renderReview(data);
  elements.formStatus.textContent = 'Perubahan scene plan dan storyboard tersimpan.';
  elements.formStatus.className = 'form-status success';
}

elements.savePlanBtn.addEventListener('click', async () => {
  elements.savePlanBtn.disabled = true;
  try { await saveEditedPlan(); }
  catch (error) { elements.formStatus.textContent = error.message; elements.formStatus.className = 'form-status error'; }
  finally { elements.savePlanBtn.disabled = false; }
});

async function postJobAction(action, body) {
  const response = await fetch(`/api/videos/jobs/${encodeURIComponent(activeJobId)}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, revision: activeRevision }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Aksi workflow gagal');
  elements.reviewPanel.style.display = 'none';
  startPolling(activeJobId, activeAspect);
}

elements.approveBtn.addEventListener('click', async () => {
  elements.approveBtn.disabled = true;
  try {
    await saveEditedPlan();
    await postJobAction('approve', { stage: activeReviewStage });
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formStatus.className = 'form-status error';
  } finally {
    elements.approveBtn.disabled = false;
  }
});

elements.reviseBtn.addEventListener('click', async () => {
  try {
    await postJobAction('revise');
  } catch (error) {
    elements.formStatus.textContent = error.message;
    elements.formStatus.className = 'form-status error';
  }
});

elements.form.addEventListener('submit', async event => {
  event.preventDefault();
  const payload = {
    topic: elements.topic.value.trim(),
    script: elements.script.value.trim(),
    engine: elements.engineSelect.value,
    style: elements.styleSelect.value,
    aspect: elements.aspectSelect.value,
    duration: parseInt(elements.durationSelect.value, 10),
    fps: Number(document.getElementById("fpsSelect").value),
    creativeBrief: document.getElementById("creativeBriefInput").value.trim(),
    model: elements.modelSelect.value,
    researchMode: document.getElementById('researchMode').value,
    brandId: document.getElementById('brandSelect').value,
    motionConcept: document.getElementById('motionConcept').value,
    voiceMode: document.getElementById('motionVoice').value,
  };
  if (!payload.topic) {
    elements.formStatus.textContent = 'Topik animasi wajib diisi.';
    elements.formStatus.className = 'form-status error';
    return;
  }
  elements.generateBtn.disabled = true;
  elements.formStatus.textContent = '';
  elements.reviewPanel.style.display = 'none';
  elements.statusContainer.style.display = 'block';
  elements.progressBar.style.background = '';
  elements.progressBar.style.width = '5%';
  elements.statusStep.textContent = 'Mengirim brief ke motion planner...';
  setWorkflowStep('brief');
  try {
    const response = await fetch('/api/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Gagal memulai workflow animasi');
    activeJobId = data.jobId;
    activeAspect = payload.aspect;
    startPolling(activeJobId, activeAspect);
  } catch (error) {
    elements.generateBtn.disabled = false;
    elements.statusContainer.style.display = 'none';
    elements.formStatus.textContent = error.message;
    elements.formStatus.className = 'form-status error';
  }
});

function startPolling(jobId, aspectId) {
  if (pollTimer) clearInterval(pollTimer);
  const poll = async () => {
    try {
      const response = await fetch(`/api/videos/jobs/${encodeURIComponent(jobId)}`);
      if (!response.ok) throw new Error('Gagal mengambil status job');
      const job = await response.json();
      elements.statusStep.textContent = job.step || 'Memproses animasi...';
      elements.progressBar.style.width = `${job.progress || 5}%`;
      if (job.status === 'researching') {
        setWorkflowStep('research');
      } else if (job.status === 'writing_narration') {
        setWorkflowStep('narration');
      } else if (job.status === 'planning_scenes') {
        setWorkflowStep('scene_plan');
      } else if (job.status === 'awaiting_scene_plan' || job.status === 'awaiting_storyboard') {
        clearInterval(pollTimer);
        renderReview(job);
      } else if (job.status === 'rendering') {
        setWorkflowStep('render');
      } else if (job.status === 'succeeded') {
        clearInterval(pollTimer);
        elements.generateBtn.disabled = false;
        elements.reviewPanel.style.display = 'none';
        elements.statusStep.textContent = 'Selesai. Hasil animasi siap.';
        elements.progressBar.style.width = '100%';
        setWorkflowStep('render');
        if (job.video) showResult({...job.video,review:job.review}, aspectId);
        loadHistory();
      } else if (job.status === 'interrupted' || job.status === 'failed') {
        clearInterval(pollTimer);
        elements.generateBtn.disabled = false;
        elements.statusStep.textContent = `Gagal: ${job.error || 'Terjadi kesalahan saat proses'}`;
        elements.progressBar.style.width = '100%';
        elements.progressBar.style.background = '#ef4444';
      }
    } catch (error) {
      console.error(error);
    }
  };
  poll();
  pollTimer = setInterval(poll, 1500);
}

loadOptions();
loadBrands();
loadPendingJobs();
loadHistory();

async function loadPendingJobs() {
  const container = document.getElementById('pendingJobs');
  try {
    const response = await fetch('/api/videos/jobs');
    if (!response.ok) throw new Error('Gagal memuat pekerjaan tersimpan');
    const { jobs } = await response.json();
    container.replaceChildren();
    for (const job of jobs) {
      if (!['interrupted', 'failed', 'awaiting_scene_plan', 'awaiting_storyboard'].includes(job.status)) continue;
      const button = document.createElement('button');
      button.className = 'secondary-button';
      button.textContent = `${job.topic} — ${job.status.startsWith('awaiting_') ? 'Buka review' : 'Lanjutkan'}`;
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const resume = ['interrupted', 'failed'].includes(job.status);
          const result = await fetch(`/api/videos/jobs/${encodeURIComponent(job.jobId)}${resume ? '/resume' : ''}`,
            resume ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: job.revision || 0 }) } : {});
          const data = await result.json();
          if (!result.ok) throw new Error(data.error || 'Gagal membuka pekerjaan');
          activeJobId = data.jobId; activeAspect = data.aspect;
          elements.statusContainer.style.display = 'block';
          if (data.status.startsWith('awaiting_')) renderReview(data);
          else startPolling(data.jobId, data.aspect);
          await loadPendingJobs();
        } catch (error) {
          elements.formStatus.textContent = error.message;
        } finally { button.disabled = false; }
      });
      container.append(button);
    }
  } catch (error) { container.textContent = error.message; }
}

document.getElementById('createAspectBtn').addEventListener('click', async event => {
  if (!resultSlug) return;
  event.target.disabled = true;
  try {
    const response = await fetch(`/api/videos/${encodeURIComponent(resultSlug)}/aspects`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({aspects:[document.getElementById('variantAspect').value]})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Gagal membuat variasi');
    elements.formStatus.textContent = `${result.jobs.length} variasi menunggu review pada daftar pekerjaan tersimpan.`;
    await loadPendingJobs();
  } catch(error) { elements.formStatus.textContent=error.message; }
  finally { event.target.disabled=false; }
});
