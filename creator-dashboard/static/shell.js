// Perilaku sidebar bersama untuk semua halaman dashboard.
(() => {
  const button = document.getElementById('sidebarToggle');
  if (!button) return;
  const KEY = 'ccSidebarCollapsed';
  const set = collapsed => {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    button.setAttribute('aria-label', collapsed ? 'Perluas sidebar' : 'Ciutkan sidebar');
    try { localStorage.setItem(KEY, collapsed ? '1' : '0'); } catch { /* storage diblokir: abaikan */ }
  };
  try { if (localStorage.getItem(KEY) === '1') set(true); } catch { /* abaikan */ }
  button.addEventListener('click', () => set(!document.body.classList.contains('sidebar-collapsed')));

  // [ = ringkas/perluas, Alt+1..3 = pindah halaman
  addEventListener('keydown', e => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.target.closest?.('input,textarea,select,dialog,[contenteditable]')) return;
    const go = { Digit1: '/', Digit2: '/videos.html', Digit3: '/articles.html' }[e.code];
    if (e.altKey && go) { e.preventDefault(); location.href = go; }
    else if (!e.altKey && e.key === '[') button.click();
  });

  // status Clipper Cuan (cross-origin, dibaca langsung dari service lokal)
  const dot = document.getElementById('sideDot'), title = document.getElementById('sideClipperTitle'), text = document.getElementById('sideClipperText');
  if (!dot) return;
  const check = async () => {
    try {
      const r = await fetch('/api/clipper/health', { cache: 'no-store' });
      const h = await r.json();
      dot.classList.toggle('off', !h.ok); title.textContent = 'Clipper Cuan siap';
      text.textContent = h.llm?.enabled ? 'AI 9Router aktif' : 'Mode analisis lokal';
    } catch {
      dot.classList.add('off'); title.textContent = 'Clipper Cuan mati';
      text.textContent = 'Jalankan service untuk memakai';
    }
  };
  check(); setInterval(check, 8000);
})();
