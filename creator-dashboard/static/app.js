const state = { tools: [], filter: 'all', logToolId: null };
const iconMap = { sparkles: '✦', layers: '▦', clapperboard: '▶', mic: '◉', scissors: '✂', film: '🎞' };
const statusLabels = { ready: 'Siap', starting: 'Memulai', stopped: 'Berhenti', cli: 'CLI' };

const grid = document.querySelector('#toolGrid');
const refreshButton = document.querySelector('#refreshButton');
const startRecommended = document.querySelector('#startRecommended');
const modal = document.querySelector('#logModal');
const logTitle = document.querySelector('#logTitle');
const logOutput = document.querySelector('#logOutput');
const toast = document.querySelector('#toast');

async function request(url, options = {}) {
  const response = await fetch(url, { cache: 'no-store', ...options });
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  return payload;
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, character => {
    if (character.charCodeAt(0) === 38) return `&${'amp'};`;
    if (character.charCodeAt(0) === 60) return `&${'lt'};`;
    if (character.charCodeAt(0) === 62) return `&${'gt'};`;
    if (character.charCodeAt(0) === 34) return `&${'quot'};`;
    return `&${'#39'};`;
  });
}

function render() {
  const visible = state.tools.filter(tool => state.filter === 'all' || tool.type === state.filter);
  grid.innerHTML = visible.map((tool, index) => {
    const canStart = tool.type !== 'cli' && tool.status === 'stopped';
    const canStop = tool.managedRunning;
    const canOpen = Boolean(tool.url) && ['ready', 'starting'].includes(tool.status);
    const featured = state.filter === 'all' && index === 0 ? ' featured' : '';
    const glowColors = {
      blue: 'rgba(76,132,255,.17)',
      indigo: 'rgba(116,102,255,.17)',
      violet: 'rgba(154,124,255,.17)',
      rose: 'rgba(240,105,155,.13)',
      emerald: 'rgba(84,230,165,.13)',
      cyan: 'rgba(70,200,230,.15)'
    };
    const glow = glowColors[tool.color] || 'rgba(124,140,255,.14)';
    const command = tool.exampleCommand ? `<button type="button" data-copy="${escapeHtml(tool.exampleCommand)}">Salin command</button>` : '';
    return `
      <article class="tool-card${featured}" style="--card-glow:${glow}">
        <div class="card-top">
          <div class="tool-icon">${iconMap[tool.icon] || '◆'}</div>
          <span class="status ${tool.status}"><span class="status-dot"></span>${statusLabels[tool.status] || tool.status}</span>
        </div>
        <span class="tool-category">${escapeHtml(tool.category)}</span>
        <h3>${escapeHtml(tool.name)}</h3>
        <p class="tool-description">${escapeHtml(tool.description)}</p>
        <div class="capability-list">${tool.capabilities.slice(0, 5).map(item => `<span>${escapeHtml(item)}</span>`).join('')}</div>
        <div class="card-actions">
          ${tool.type === 'cli' ? command : `<button class="launch" type="button" data-start="${tool.id}" ${canStart ? '' : 'disabled'}>Jalankan</button>`}
          ${tool.url ? `<a class="${canOpen ? '' : 'disabled'}" href="${escapeHtml(tool.url)}" target="_blank" rel="noopener">Buka</a>` : ''}
          ${tool.type !== 'cli' ? `<button class="stop" type="button" data-stop="${tool.id}" ${canStop ? '' : 'disabled'}>Stop</button>` : ''}
          ${tool.type !== 'cli' ? `<button type="button" data-logs="${tool.id}">Log</button>` : ''}
        </div>
      </article>`;
  }).join('') || '<p>Tidak ada tool untuk filter ini.</p>';

  document.querySelector('#totalTools').textContent = state.tools.length;
  document.querySelector('#readyTools').textContent = state.tools.filter(tool => tool.status === 'ready').length;
  document.querySelector('#startingTools').textContent = state.tools.filter(tool => tool.status === 'starting').length;
  document.querySelector('#cliTools').textContent = state.tools.filter(tool => tool.type === 'cli').length;
}

async function refresh(silent = false) {
  try {
    const payload = await request('/api/tools');
    state.tools = payload.tools;
    render();
  } catch (error) {
    if (!silent) showToast(`Gagal membaca status: ${error.message}`);
  }
}

async function act(toolId, action) {
  const tool = state.tools.find(item => item.id === toolId);
  try {
    showToast(`${action === 'start' ? 'Menjalankan' : 'Menghentikan'} ${tool?.name || toolId}...`);
    const payload = await request(`/api/tools/${encodeURIComponent(toolId)}/${action}`, { method: 'POST' });
    showToast(payload.message);
    await refresh(true);
    if (action === 'start') {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        await refresh(true);
        const updated = state.tools.find(item => item.id === toolId);
        if (updated?.status === 'ready' || updated?.status === 'stopped') break;
      }
    }
  } catch (error) {
    showToast(`Operasi gagal: ${error.message}`);
    await refresh(true);
  }
}

async function openLogs(toolId) {
  const tool = state.tools.find(item => item.id === toolId);
  state.logToolId = toolId;
  logTitle.textContent = tool?.name || 'Log';
  modal.hidden = false;
  await updateLogs();
}

async function updateLogs() {
  if (!state.logToolId || modal.hidden) return;
  try {
    const payload = await request(`/api/tools/${encodeURIComponent(state.logToolId)}/logs`);
    logOutput.textContent = payload.logs.length ? payload.logs.join('\n') : 'Belum ada log. Jalankan tool untuk melihat output proses.';
    logOutput.scrollTop = logOutput.scrollHeight;
  } catch (error) {
    logOutput.textContent = `Gagal membaca log: ${error.message}`;
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 3600);
}

document.addEventListener('click', async event => {
  const element = event.target.closest('button, [data-close-modal]');
  if (!element) return;
  if (element.dataset.start) await act(element.dataset.start, 'start');
  if (element.dataset.stop) await act(element.dataset.stop, 'stop');
  if (element.dataset.logs) await openLogs(element.dataset.logs);
  if (element.dataset.copy) {
    await navigator.clipboard.writeText(element.dataset.copy);
    showToast('Command disalin ke clipboard.');
  }
  if (element.matches('[data-close-modal]')) { modal.hidden = true; state.logToolId = null; }
});

document.querySelectorAll('.filter').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.filter').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    state.filter = button.dataset.filter;
    render();
  });
});

refreshButton.addEventListener('click', () => refresh());
startRecommended.addEventListener('click', () => act('moneyprinterturbo', 'start'));
setInterval(() => refresh(true), 5000);
setInterval(updateLogs, 1200);
refresh();
