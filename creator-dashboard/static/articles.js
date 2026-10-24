const form = document.querySelector('#draftForm');
const statusLine = document.querySelector('#formStatus');
const generateButton = document.querySelector('#generateButton');
let currentSlug = null;

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

function renderArticle(article) {
  currentSlug = article.slug;
  document.querySelector('#emptyState').hidden = true;
  document.querySelector('#result').hidden = false;
  document.querySelector('#resultTitle').textContent = article.title;
  document.querySelector('#resultSummary').textContent = article.summary;
  document.querySelector('#resultPath').textContent = `Folder: ${article.path}`;
  document.querySelector('#mdPreview').textContent = article.markdown;

  const downloads = document.querySelector('#downloads');
  downloads.replaceChildren(...article.files.map(name =>
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
      el('header', {}, el('strong', {}, `${image.id}`), badge),
      el('div', { className: 'muted small' }, `${image.purpose || '-'} | rasio ${image.aspect}`),
      el('pre', {}, image.prompt),
      el('div', { className: 'actions' }, copy, file));
  }));
}

async function upload(imageId, input) {
  const file = input.files[0];
  if (!file || !currentSlug) return;
  try {
    const article = await api(`/api/articles/${currentSlug}/images/${encodeURIComponent(imageId)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: await file.arrayBuffer(),
    });
    renderArticle(article);
    toast('Gambar terpasang, dokumen dibangun ulang');
  } catch (error) {
    input.value = '';
    toast(error.message);
  }
}

async function loadHistory() {
  const { articles } = await api('/api/articles');
  const history = document.querySelector('#history');
  if (!articles.length) { history.replaceChildren(el('li', {}, 'Belum ada.')); return; }
  history.replaceChildren(...articles.map(item => {
    const open = el('button', { type: 'button' }, 'Buka');
    open.addEventListener('click', async () => {
      try { renderArticle(await api(`/api/articles/${item.slug}`)); window.scrollTo({ top: 0, behavior: 'smooth' }); }
      catch (error) { toast(error.message); }
    });
    return el('li', {}, el('span', {}, item.title), open);
  }));
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(form));
  generateButton.disabled = true;
  statusLine.className = 'form-status';
  statusLine.textContent = 'Menulis artikel... jangan tutup halaman ini.';
  try {
    renderArticle(await api('/api/articles', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }));
    statusLine.textContent = 'Selesai.';
    loadHistory();
  } catch (error) {
    statusLine.className = 'form-status error';
    statusLine.textContent = error.message;
  } finally {
    generateButton.disabled = false;
  }
});

loadHistory().catch(error => toast(error.message));
