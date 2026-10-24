const form = document.querySelector('#draftForm');
const statusLine = document.querySelector('#formStatus');
const generateButton = document.querySelector('#generateButton');
const progressBox = document.querySelector('#progress');
let currentSlug = null;
let pollTimer = null;

function toast(message) {
  const el = document.querySelector('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 2600);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Permintaan gagal (${response.status})`);
  return data;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

function setStatus(message, isError = false) {
  statusLine.className = isError ? 'form-status error' : 'form-status';
  statusLine.textContent = message;
}

function setBusy(busy) {
  generateButton.disabled = busy;
}

function showProgress(job) {
  progressBox.hidden = job.status !== 'running';
  const percent = Math.min(100, Math.round((job.done / Math.max(job.total, 1)) * 100));
  document.querySelector('#bar').style.width = `${percent}%`;
  document.querySelector('#progressText').textContent = `${percent}% | ${job.message}`;
}

async function loadOptions() {
  const options = await api('/api/articles/options');
  const typeSelect = document.querySelector('#typeSelect');
  typeSelect.replaceChildren(...options.types.map(item => el('option', { value: item.key }, item.label)));
  typeSelect.value = options.defaultType;
  const styleSelect = document.querySelector('#styleSelect');
  styleSelect.replaceChildren(
    el('option', { value: options.randomStyle }, 'Acak (setiap gambar beda gaya)'),
    ...options.styles.map(style => el('option', { value: style }, style)));
  document.querySelector('#wordsInput').max = options.limits.maxWords;
  document.querySelector('#imageCount').max = options.limits.maxImages;
}

function renderArticle(article) {
  currentSlug = article.slug;
  document.querySelector('#emptyState').hidden = true;
  document.querySelector('#result').hidden = false;
  document.querySelector('#resultTitle').textContent = article.title;
  document.querySelector('#resultSummary').textContent = article.summary;
  const resumeBox = document.querySelector('#resumeBox');
  const complete = document.querySelector('#complete');
  resumeBox.hidden = article.complete;
  complete.hidden = !article.complete;
  if (!article.complete) {
    document.querySelector('#resumeText').textContent =
      `Belum selesai: ${article.sectionsDone}/${article.sectionsTotal || '?'} bagian tersimpan. Bagian yang sudah jadi tidak ditulis ulang.`;
    return;
  }
  document.querySelector('#resultPath').textContent =
    `${article.wordCount.toLocaleString('id-ID')} kata | ${article.referencesCount} rujukan | Folder: ${article.path}`;
  document.querySelector('#mdPreview').textContent = article.markdown;

  document.querySelector('#downloads').replaceChildren(...article.files.map(name =>
    el('a', { href: `/api/articles/${article.slug}/files/${name}`, download: name }, `Unduh ${name}`)));

  const list = document.querySelector('#imageList');
  if (!article.images.length) {
    list.replaceChildren(el('p', { className: 'muted small' }, 'Artikel ini tidak meminta gambar.'));
    return;
  }
  list.replaceChildren(...article.images.map(image => {
    const badge = el('span', { className: `badge${image.hasFile ? ' ok' : ''}` }, image.hasFile ? 'gambar terpasang' : 'belum ada gambar');
    const copy = el('button', { type: 'button' }, 'Salin prompt');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(image.prompt); toast('Prompt disalin'); }
      catch { toast('Gagal menyalin; blok teks lalu salin manual'); }
    });
    const file = el('input', { type: 'file', accept: 'image/png,image/jpeg' });
    file.addEventListener('change', () => upload(image.id, file));
    return el('article', { className: 'image-card' },
      el('header', {}, el('strong', {}, image.id), badge),
      el('div', { className: 'muted small' }, `${image.purpose || '-'} | rasio ${image.aspect}`),
      el('div', { className: 'muted small' }, `Gaya: ${image.style || '-'}`),
      el('pre', {}, image.prompt),
      el('div', { className: 'actions' }, copy, file));
  }));
}

async function upload(imageId, input) {
  const file = input.files[0];
  if (!file || !currentSlug) return;
  try {
    renderArticle(await api(`/api/articles/${currentSlug}/images/${encodeURIComponent(imageId)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: await file.arrayBuffer(),
    }));
    toast('Gambar terpasang, dokumen dibangun ulang');
  } catch (error) {
    input.value = '';
    toast(error.message);
  }
}

function watch(jobId) {
  clearTimeout(pollTimer);
  setBusy(true);
  const tick = async () => {
    try {
      const job = await api(`/api/articles/jobs/${encodeURIComponent(jobId)}`);
      currentSlug = job.slug;
      showProgress(job);
      if (job.status === 'running') { pollTimer = setTimeout(tick, 2000); return; }
      setBusy(false);
      progressBox.hidden = true;
      renderArticle(await api(`/api/articles/${job.slug}`));
      loadHistory();
      if (job.status === 'done') setStatus('Selesai.');
      else setStatus(job.error || 'Gagal.', true);
    } catch (error) {
      setBusy(false);
      progressBox.hidden = true;
      setStatus(error.message, true);
    }
  };
  tick();
}

async function resume(slug) {
  try {
    setStatus('Melanjutkan...');
    const job = await api(`/api/articles/${encodeURIComponent(slug)}/resume`, { method: 'POST' });
    watch(job.id);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadHistory() {
  const { articles } = await api('/api/articles');
  const history = document.querySelector('#history');
  if (!articles.length) { history.replaceChildren(el('li', {}, 'Belum ada.')); return; }
  history.replaceChildren(...articles.map(item => {
    let label = 'Buka';
    let action = async () => renderArticle(await api(`/api/articles/${item.slug}`));
    if (!item.complete && item.job) { label = 'Pantau'; action = async () => watch(item.job); }
    else if (!item.complete) { label = 'Lanjutkan'; action = async () => resume(item.slug); }
    const button = el('button', { type: 'button' }, label);
    button.addEventListener('click', async () => {
      try { await action(); if (label === 'Buka') window.scrollTo({ top: 0, behavior: 'smooth' }); }
      catch (error) { toast(error.message); }
    });
    return el('li', {}, el('span', {}, item.complete ? item.title : `${item.title} (belum selesai)`), button);
  }));
}

document.querySelector('#resumeButton').addEventListener('click', () => currentSlug && resume(currentSlug));

form.addEventListener('submit', async event => {
  event.preventDefault();
  setBusy(true);
  setStatus('Memulai...');
  try {
    const job = await api('/api/articles', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    setStatus('Artikel ditulis di latar belakang. Halaman ini boleh ditutup lalu dibuka lagi; lihat Artikel sebelumnya.');
    loadHistory();
    watch(job.id);
  } catch (error) {
    setBusy(false);
    setStatus(error.message, true);
  }
});

loadOptions().then(loadHistory).catch(error => toast(error.message));
