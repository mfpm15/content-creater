const elements = {
  form: document.getElementById('videoForm'),
  engineNotice: document.getElementById('engineNotice'),
  formEngineTitle: document.getElementById('formEngineTitle'),
  topic: document.getElementById('topicInput'),
  script: document.getElementById('scriptInput'),
  styleSelect: document.getElementById('styleSelect'),
  aspectSelect: document.getElementById('aspectSelect'),
  durationSelect: document.getElementById('durationSelect'),
  modelSelect: document.getElementById('modelSelect'),
  generateBtn: document.getElementById('generateBtn'),
  formStatus: document.getElementById('formStatus'),
  statusContainer: document.getElementById('statusContainer'),
  statusStep: document.getElementById('statusStep'),
  progressBar: document.getElementById('progressBar'),
  videoContainer: document.getElementById('videoContainer'),
  videoActions: document.getElementById('videoActions'),
  downloadBtn: document.getElementById('downloadBtn'),
  inspectHtmlBtn: document.getElementById('inspectHtmlBtn'),
  historyList: document.getElementById('historyList'),
};

let pollTimer = null;

async function loadOptions() {
  try {
    const res = await fetch('/api/videos/options');
    if (!res.ok) throw new Error('Gagal memuat opsi video');
    const data = await res.json();

    elements.styleSelect.innerHTML = data.styles.map(s =>
      `<option value="${s.id}" ${s.id === data.defaultStyle ? 'selected' : ''}>${s.name} - ${s.description}</option>`
    ).join('');

    elements.aspectSelect.innerHTML = data.aspects.map(a => 
      `<option value="${a.id}" ${a.id === data.defaultAspect ? 'selected' : ''}>${a.label}</option>`
    ).join('');

    elements.durationSelect.innerHTML = data.durations.map(d =>
      `<option value="${d}" ${d === data.defaultDuration ? 'selected' : ''}>${d} Detik</option>`
    ).join('');

    if (data.models && data.models.length) {
      elements.modelSelect.innerHTML = data.models.map(m =>
        `<option value="${m.id}" ${m.id === data.defaultModel ? 'selected' : ''}>${m.name}</option>`
      ).join('');
    }
    updateEngineExperience();
  } catch (err) {
    elements.formStatus.textContent = err.message;
    elements.formStatus.className = 'form-status error';
  }
}

function updateEngineExperience() {
  elements.formEngineTitle.textContent = '1. Sutradarai Film Opuscar';
  elements.generateBtn.textContent = 'Sutradarai & Render Film Opuscar (MP4)';
}

async function loadHistory() {
  try {
    const res = await fetch('/api/videos');
    if (!res.ok) return;
    const data = await res.json();
    const videos = data.videos || [];
    if (!videos.length) {
      elements.historyList.innerHTML = '<p class="empty">Belum ada video tersimpan.</p>';
      return;
    }
    elements.historyList.innerHTML = videos.map(v => `
      <div class="history-card" onclick="selectVideo('${v.slug}')">
        <h4>${v.topic}</h4>
        <p>${v.formattedTime || ''} · ${v.duration || 5}s · ${(v.videoSize / 1024 / 1024).toFixed(1)} MB</p>
      </div>
    `).join('');
  } catch (err) {
    elements.historyList.innerHTML = '<p class="empty">Gagal memuat riwayat.</p>';
  }
}

async function selectVideo(slug) {
  try {
    const res = await fetch(`/api/videos/${encodeURIComponent(slug)}`);
    if (!res.ok) return;
    const meta = await res.json();
    showVideo(meta.videoUrl, meta.htmlUrl, meta.aspect?.id || '9:16');
  } catch (err) {
    console.error(err);
  }
}

function showVideo(videoUrl, htmlUrl, aspectId) {
  const isLandscape = aspectId === '16:9';
  elements.videoContainer.className = `video-preview-box ${isLandscape ? 'landscape' : ''}`;
  elements.videoContainer.innerHTML = `
    <video controls autoplay loop playsinline src="${videoUrl}">
      Browser Anda tidak mendukung tag video.
    </video>
  `;
  elements.downloadBtn.href = videoUrl;
  elements.inspectHtmlBtn.href = htmlUrl || '#';
  elements.videoActions.style.display = 'flex';
}

elements.form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    topic: elements.topic.value.trim(),
    script: elements.script.value.trim(),
    style: elements.styleSelect.value,
    aspect: elements.aspectSelect.value,
    duration: parseInt(elements.durationSelect.value, 10),
    model: elements.modelSelect ? elements.modelSelect.value : '',
  };

  if (!payload.topic) {
    elements.formStatus.textContent = 'Topik video wajib diisi.';
    elements.formStatus.className = 'form-status error';
    return;
  }

  elements.generateBtn.disabled = true;
  elements.formStatus.textContent = '';
  elements.statusContainer.style.display = 'block';
  elements.progressBar.style.width = '10%';
  elements.statusStep.textContent = 'Mengirim instruksi ke sistem...';

  try {
    const res = await fetch('/api/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || 'Gagal memulai job video');
    }

    const { jobId } = await res.json();
    startPolling(jobId, payload.aspect);
  } catch (err) {
    elements.generateBtn.disabled = false;
    elements.statusContainer.style.display = 'none';
    elements.formStatus.textContent = err.message;
    elements.formStatus.className = 'form-status error';
  }
});

function startPolling(jobId, aspectId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/videos/jobs/${encodeURIComponent(jobId)}`);
      if (!res.ok) throw new Error('Gagal mengambil status job');
      const job = await res.json();

      elements.statusStep.textContent = job.step || 'Memproses video...';
      elements.progressBar.style.width = `${job.progress || 20}%`;

      if (job.status === 'succeeded') {
        clearInterval(pollTimer);
        elements.generateBtn.disabled = false;
        elements.statusStep.textContent = 'Selesai! Video siap diputar.';
        elements.progressBar.style.width = '100%';
        if (job.video) {
          showVideo(job.video.videoUrl, job.video.htmlUrl, aspectId);
        }
        loadHistory();
      } else if (job.status === 'failed') {
        clearInterval(pollTimer);
        elements.generateBtn.disabled = false;
        elements.statusStep.textContent = `Gagal: ${job.error || 'Terjadi kesalahan saat render'}`;
        elements.progressBar.style.width = '100%';
        elements.progressBar.style.background = '#ef4444';
      }
    } catch (err) {
      console.error(err);
    }
  }, 2000);
}

loadOptions();
loadHistory();
