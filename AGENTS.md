# Panduan Agen — Content Creator Control Center

**Baca `AGENTS.md` ini terlebih dahulu sebelum menelusuri kode.** Semua path di bawah relatif terhadap root repositori. Untuk modul yang memiliki `AGENTS.md` sendiri, baca juga instruksi lokalnya sebelum bekerja di sana.

## 1. Tech Stack & Versi Utama

Repositori ini adalah kumpulan aplikasi konten dengan **dashboard/launcher bersama**, bukan satu aplikasi dengan satu dependency tree. Tidak ada `package.json` di root. Versi berikut berasal dari manifest; rentang versi bukan jaminan versi terpasang.

| Komponen | Stack dan acuan versi |
|---|---|
| Dashboard, Article Drafter, Video Studio, Analytics | Python 3.11+; backend HTTP, threading, JSON, serta pembuat DOCX memakai **stdlib**; frontend HTML/CSS/JavaScript biasa tanpa bundler |
| Clipper Cuan | Python 3.10–3.12 (CI: 3.12); FastAPI ≥0.110, Uvicorn ≥0.29, faster-whisper ≥1.1, yt-dlp ≥2026.1.1, OpenCV headless ≥4.8,<5, MCP ≥1.2,<2; `clippercuan/app/requirements.txt` |
| MoneyPrinterTurbo | Python ≥3.11, uv + `uv.lock`; Streamlit 1.59.1, FastAPI 0.136.3, MoviePy 2.2.1, OpenAI SDK 2.24.0; `apps/moneyprinterturbo/pyproject.toml` di bawah dashboard |
| Podcastfy | Python ^3.11; Poetry metadata 0.4.3; LangChain, provider LLM/TTS, FastAPI API; `pyproject.toml` dan `creator-dashboard/podcastfy-overrides.txt` |
| OpenCreator | Node.js 22+ menurut panduan setup, pnpm **9.15.0**; TypeScript, React ^18.3.1, React Router ^6.30.1, Vite ^6.0.7; daemon Fastify 5.12.2 + better-sqlite3 ^12.11.1; Electron desktop |
| Short Video Factory | Node.js ≥22.17, pnpm **10.12.4**; Vue ^3.5.17, Pinia ^3.0.3, Vue Router ^4.5.1, Vite ^7.0.3, TypeScript 5.6.2, Electron ^22.3.27, better-sqlite3 9.6.0 |
| Adapter render | HyperFrames ^0.8.195; Remotion 4.0.473 pada `opencreator/packages/stickman-remotion`; Lemo-Opuscar: Node ≥20, Python, Playwright, Three.js ^0.170.0 |

FFmpeg adalah prasyarat media bersama. Setiap aplikasi mempertahankan venv, package manager, konfigurasi provider, dan penyimpanannya sendiri; jangan menyatukan dependency Python/Node secara global.

## 2. Peta Folder Inti (Directory Map)

| Path | Fungsi spesifik / titik masuk |
|---|---|
| `README.md`, `CREATOR-DASHBOARD.md` | Penggunaan, port, konfigurasi provider dan launcher; bandingkan dengan kode karena sebagian catatan masih berorientasi Windows |
| `CONTEXT.md`, `docs/` | Kontrak domain Motion Plan, rancangan artikel, rencana integrasi, dan catatan status; bukan sumber kebenaran tunggal perilaku runtime |
| `setup-dashboard.bat`, `start-dashboard.bat` | Instalasi dan startup dashboard Windows; bukan skrip shell Linux |
| `package-release.ps1`, `DISTRIBUTION.md` | Pengemasan source bersih, pengecualian secret/dependency/data lokal |
| `creator-dashboard/server.py` | Entry HTTP dashboard; router manual, validasi katalog, lifecycle subprocess, health probe, log dan proxy Clipper |
| `creator-dashboard/tools.json` | Katalog sembilan tool termasuk adapter tersembunyi; working directory, command, port, URL health, kemampuan; bukan tempat secret |
| `creator-dashboard/static/` | Halaman `index.html`, `articles.html`, `videos.html`, `youtube-analytics.html`; JS/CSS per fitur; `shell.js` untuk shell UI |
| `creator-dashboard/article_drafter.py`, `humanizer.py` | Pipeline artikel bertahap, sitasi, prompt gambar, unggah gambar, pembuatan Markdown/DOCX; normalisasi gaya teks |
| `creator-dashboard/video_drafter.py` | Job animasi, riset, Scene Plan/Motion Plan, persetujuan storyboard, adapter render dan artefak |
| `creator-dashboard/google_search_research.py` | Worker terpisah: JSON stdin/stdout, Google Search grounding via Google GenAI |
| `creator-dashboard/youtube_analytics.py` | Analisis retensi dan hook berbasis heuristik; jangan anggap skor sebagai prediksi performa |
| `creator-dashboard/test_*.py` | Smoke HTTP dan tes fitur dashboard; sebagian berupa skrip mandiri, sebagian `unittest` |
| `creator-dashboard/bin/` | Shim launcher/package manager Windows |
| `creator-dashboard/apps/moneyprinterturbo/` | `webui/` Streamlit; `app/controllers`, `router.py`, `services`, `models`, `config`; `resource/` aset media |
| `creator-dashboard/apps/podcastfy/` | `podcastfy/content_parser/` ekstraksi sumber → `content_generator.py` → `text_to_speech.py`, `tts/`; API di `podcastfy/api/fast_app.py` |
| `creator-dashboard/apps/ai-youtube-shorts-generator/` | `main.py` CLI; `shorts_generator/` pipeline API, `local/` unduh/transkripsi/LLM/potong lokal |
| `creator-dashboard/apps/opencreator/` | Workspace pnpm; `apps/web/src/{app,features,runtime,host}` UI/routing/koneksi runtime/bridge; `apps/daemon/src/` API, agent, gateway, task, scheduler dan persistence; `apps/desktop/` Electron; `packages/` kontrak/config/template/render; `runtime/krillinai/` runtime Go |
| `creator-dashboard/apps/short-video-factory/` | `src/{views,components,router,store,lib,effect-engine}` UI Vue; `electron/` main/preload/IPC, provider dan SQLite; `build/scripts/` skrip build **source**, bukan hasil build |
| `creator-dashboard/apps/hyperframes/` | Entry HTML dan CLI preview/render HyperFrames |
| `creator-dashboard/apps/lemo-opuscar/` | `styles/<slug>/STYLE.md` kontrak gaya, `demo/` contoh; `styleboard/` katalog; `core/`, `tools/`, `scripts/` produksi film |
| `clippercuan/app/clipper/` | `__main__.py` UI server/CLI/MCP; `server.py` REST; `project.py` antrean/pipeline; `download.py`, `transcribe.py`, `asr.py`, `highlights.py`, `candidates.py` pemrosesan; `shots.py`, `facetrack.py`, `captions.py`, `render.py` framing/subtitle/FFmpeg; `delivery.py`, `postgen.py` hasil/paket posting |
| `clippercuan/app/clipper/{config.py,llm.py,web/}` | Lokasi data/default, pengaturan provider/LLM, frontend Clipper; `mcp_server.py` antarmuka agen |
| `clippercuan/app/tests/`, `.github/workflows/clippercuan-*.yml` | Tes Clipper, CI Python 3.12 + FFmpeg + pytest/ruff, build desktop |
| `clippercuan/docs/`, `clippercuan/site/` | Dokumentasi fitur/cloud/API agen; landing page statis terpisah dari UI aplikasi |

## 3. Alur Data, Routing, & Pola Arsitektur

### Dashboard dan fitur bawaan

- `static/*.html` → JS `fetch()` same-origin → `DashboardHandler` pada `server.py` (`ThreadingHTTPServer`, default loopback **3210**). Halaman berupa file statis, bukan SPA React/Vue. State UI berupa objek/variabel JS dan polling; tidak memakai Redux/Pinia di dashboard.
- `GET /api/tools`, `/api/tools/{id}/logs`; `POST /api/tools/{id}/{start|stop}` → `ManagedProcess` menjalankan command tetap dari `tools.json`. Browser tidak memasok shell command. Katalog publik menyembunyikan command/environment. Status menggabungkan proses, port dan health HTTP.
- `/api/clipper/{health|production}` mem-proxy status Clipper. Clipper tetap proses terpisah pada **8765**. Tool lain memiliki port/runtime sendiri; lihat `tools.json` untuk nilai aktual.
- `/api/articles` dan `/api/articles/jobs/{id}` → job thread + lock → kerangka → referensi → bagian paralel → prompt gambar → `.md`/`.docx`. Tahap disimpan ke `creator-dashboard/output/articles/`; endpoint resume/rebuild/gambar melanjutkan atau merakit ulang dokumen. Gambar diunggah kembali oleh pengguna.
- `/api/videos` dan `/api/videos/jobs/{id}` → brief/riset → Scene Plan → persetujuan → Storyboard → persetujuan → Render Adapter → `creator-dashboard/output/videos/`. Motion Plan mempertahankan timing, narasi, visual, motion/easing, transisi, teks layar, sound cue. UI melakukan polling; endpoint `edit`, `approve`, `revise` mengatur tahap.
- `/api/analytics/*` memanggil analisis Python. Dashboard dan Clipper menyimpan data terutama sebagai file/JSON, **tanpa database bersama**. Job Video Studio disimpan atomik di `output/videos/.jobs/`; job aktif dipulihkan sebagai `interrupted`, tahap persetujuan tetap tersimpan.
- Panggilan AI berlangsung di backend ke endpoint OpenAI-compatible (default lokal `http://localhost:20128/v1`). **Kode aktual** Article Drafter membaca `ARTICLE_LLM_{BASE_URL,API_KEY,MODEL}`; Video Studio membaca `VIDEO_LLM_{BASE_URL,API_KEY,MODEL}`. Jangan menganggap semua modul memakai variabel LLM yang sama.
- Worker Google Search membaca `GOOGLE_API_KEY` atau `GEMINI_API_KEY`. `runtime_config.py` memilih interpreter venv Windows/POSIX. Launcher Linux tersedia untuk Clipper, Podcastfy, dan MoneyPrinterTurbo; launcher lain yang memerlukan Windows ditolak dengan pesan eksplisit.
- Dashboard merupakan layanan lokal tanpa alur login pengguna; pertahankan binding `127.0.0.1`. Jangan mengirim credential ke frontend/API publik atau menyimpan secret ke katalog.

### Clipper Cuan

- UI `clipper/web/`, CLI dan MCP → REST/service `project.py` → antrean worker → unduh/probe → subtitle sumber/API/Whisper → kandidat/ranking → seleksi → framing/caption → FFmpeg → ekspor. Kandidat dan render adalah tahap berbeda; periksa konfigurasi aktual sebelum mengasumsikan auto-render.
- REST utama: `/api/projects`, `/api/projects/{pid}/...` (kandidat, caption, edit, batch-render, ekspor), `/api/settings`, `/api/system`; `/files/{pid}/{name}` menyajikan artefak.
- `config.py` menetapkan default data ke **root repo `.data/ClipperCuan/`**, dapat dioverride `CLIPPER_HOME`. Metadata `project.json` ditulis atomik; proyek, model, upload dan temp ada di bawah data root.
- `llm.py` membaca `LLM_*` dengan fallback `OPENAI_*`; provider opsional, ada penilaian lokal. Model Whisper diunduh saat dibutuhkan; instalasi dependency belum membuktikan model/provider tersedia.
- Middleware: bila `CLIPPER_TOKEN` diisi, wajib Bearer atau Basic auth; tanpa token memeriksa Host/Origin lokal. Binding nonlokal memerlukan token; jangan menghilangkan pemeriksaan ini.

### Aplikasi terbundel

- OpenCreator: React router/state/context di `apps/web/src/app/`; runtime client dan SSE di `src/runtime/` menghubungkan UI ke daemon, dengan Bearer token. Fastify mengelola service/agent dan SQLite; Electron menghubungkan kemampuan native melalui host bridge/preload/IPC. Kontrak bersama berada di `packages/protocol/`; baca `opencreator/AGENTS.md` sebelum mengubah subsistem ini.
- Short Video Factory: Vue Router + Pinia (`src/router/`, `src/store/`); bridge preload/IPC menuju Electron dan SQLite (`electron/sqlite/`). Provider dan data lokal terpisah dari dashboard.
- MoneyPrinterTurbo: UI Streamlit/API memanggil service produksi video. Podcastfy: ekstraksi sumber → teks percakapan → provider TTS → audio. Konfigurasi lokal masing-masing tetap terpisah; tidak ada autentikasi atau database tunggal untuk seluruh repo.

## 4. Daftar Folder/File yang Harus Diabaikan (Ignore List)

Abaikan **secara default saat pencarian arsitektur**, buka hanya jika relevan dengan tugas:

- Dependency/cache: `**/node_modules/`, `**/.venv/`, `**/venv/`, `**/__pycache__/`, `**/.pytest_cache/`, `**/.ruff_cache/`, `**/.mypy_cache/`, `**/.pnpm-store/`, `**/.uv-cache/`, `**/.runtime/`, `**/.git/`.
- Hasil build/tes: `**/dist/`, `**/dist-electron/`, `**/release/`, `**/coverage/`, `**/htmlcov/`, build output yang terverifikasi generated. **Jangan mengecualikan semua `build/` membabi buta**: Short Video Factory memiliki source `build/scripts/` yang dipakai instalasi/build.
- Data/media/log: `.data/`, `**/output/`, `**/outputs/`, `**/storage/`, `**/renders/`, `**/exports/`, `**/uploads/`, `**/cache/`, `**/.hyperframes/`, `**/.thumbnails/`, `*.log`, arsip distribusi, video/audio/font/model biner. Jangan mengecualikan direktori bernama `projects` secara global: OpenCreator punya source `apps/daemon/src/projects/`.
- Secret lokal: `.env`, `.env.*` selain `.env.example`, `config.toml`, `*.key`. Baca nama variabel dari contoh/config source; jangan mencetak nilai credential.
- Dokumen/aset besar yang tidak terkait: terjemahan README, screenshot, seluruh demo `lemo-opuscar/styles/`, katalog aset/preset, data fixture besar. Buka gaya/fixture spesifik bila tugas membutuhkannya.
- Lockfile (`pnpm-lock.yaml`, `package-lock.json`, `uv.lock`): jangan dump seluruh isi; baca terarah bila memeriksa resolusi versi atau masalah instalasi. Pertahankan lockfile saat install.

Mulai dengan `rg --files <folder-target>` dan `rg -n '<simbol>' <folder-target>`; batasi pencarian ke pemilik fitur sebelum memperluas ke `apps/` lain.

## 5. Aturan Kerja Agen

1. **Selalu baca root `AGENTS.md` ini terlebih dahulu sebelum membedah kode.** Lalu baca `AGENTS.md` turunan yang berlaku, terutama OpenCreator dan Lemo-Opuscar; instruksi lokal melengkapi panduan root untuk subtree tersebut.
2. Tetapkan pemilik perubahan: dashboard, Clipper, atau satu aplikasi terbundel. Jangan menganggap folder `apps/` sebagai dependency yang boleh diabaikan atau mengubah seluruh aplikasi untuk perbaikan satu fitur.
3. Periksa `git status --short`, manifest dan konfigurasi sumber yang relevan. Pertahankan perubahan pengguna. Gunakan checkout yang ada; buat worktree hanya bila diminta. Jangan mengedit dependency/build output.
4. Jangan membocorkan secret, memasukkan credential ke UI, atau menaruh data hasil render ke Git. Jaga validasi path, command allowlist, loopback binding, middleware auth, dan sanitasi respons publik.
5. Pertahankan kontrak Motion Plan dan persetujuan Scene Plan/Storyboard saat mengubah alur video. Dokumentasi lama dapat tertinggal; verifikasi dukungan adapter dan default pada kode aktual.
6. Uji sesuai lingkup: dashboard dari root dengan `python creator-dashboard/test_dashboard.py`, `python creator-dashboard/test_article_drafter.py`, atau `python -m unittest discover -s creator-dashboard -p 'test_*.py'`; Clipper dari `clippercuan/app` dengan `.venv/bin/python -m pytest -q tests` dan `.venv/bin/ruff check clipper tests --select F,E9`. Untuk aplikasi lain gunakan skrip manifest dan instruksi lokalnya; jangan menjalankan seluruh monorepo untuk perubahan dokumentasi kecil.
7. Pada Linux, jalankan dashboard dengan `CREATOR_DASHBOARD_NO_BROWSER=1 python creator-dashboard/server.py`; Clipper dari `clippercuan/app` dengan `.venv/bin/python -m clipper --port 8765 --strict-port --no-browser`. Jangan menganggap tombol launcher Windows atau provider eksternal sudah berfungsi hanya karena halaman dashboard terbuka.
8. Laporkan hanya validasi yang benar-benar dijalankan. Jika struktur, routing, konfigurasi atau workflow berubah, perbarui bagian relevan panduan ini tanpa memperpanjangnya dengan dump kode/log.

Implementasi lintas fitur: `security.py` meredaksi credential pada respons/log dan menolak redirect serta HTTP remote untuk panggilan LLM dashboard; `research_service.py` menjalankan worker riset terisolasi (opsional pada artikel); `video_job_store.py` menyimpan checkpoint privat mode 0600; `video_review.py` memeriksa stream/durasi hasil MP4. Caption editorial memakai `project.resolve_caption_track`; hasil render menandai revisi caption dan laporan delivery terpisah dari status render. Jangan klaim pemeriksaan metadata sebagai review visual atau verifikasi fakta.
