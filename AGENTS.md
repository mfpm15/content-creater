# Panduan Agen — Content Creator Control Center

**Baca `AGENTS.md` ini terlebih dahulu sebelum menelusuri kode.** Semua path di bawah relatif terhadap root repositori. Untuk modul yang memiliki `AGENTS.md` sendiri, baca juga instruksi lokalnya sebelum bekerja di sana.

## Panduan khusus Video Studio Faceless

Untuk perubahan yang memengaruhi perencanaan shot, dubbing, aset, atau kualitas video, baca **creator-dashboard/skills/faceless-video-director/SKILL.md** dan **docs/FACELESS-VIDEO-STUDIO-2026-11-07.md**. Skill adalah panduan produksi internal, bukan pengganti pengujian hasil MP4. Kode pihak ketiga tidak boleh diimpor tanpa verifikasi lisensi kode **dan** aset secara terpisah. Workflow visual harus mempertahankan approval dan metadata hak pakai.

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
| Adapter render | HyperFrames ^0.8.195; Remotion 4.0.540 pada adapter `video-studio-remotion`; OpenCreator Stickman tetap memiliki runtime terisolasi sendiri; Lemo-Opuscar: Node ≥20, Python, Playwright, Three.js ^0.170.0 |

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
| `creator-dashboard/animation_clock.py` | Clock bersama GSAP/CSS/WebGL dan bridge kontrak frame HyperFrames/Opuscar; menjaga suppressed seek tetap menggambar |
| `creator-dashboard/continuous_motion.py` | Adapter SVG/MP4 kontinu: konsep, beat sheet, render browser/FFmpeg lokal, probe carrier dan perubahan piksel |
| `creator-dashboard/creative_profile.py`, `benchmark_media.py` | Validasi/katalog brand dan cue kata eksplisit; CLI benchmark lokal terpisah untuk hash, audio dan precision/recall cut |
| `creator-dashboard/{tavily_research,research_service}.py` | Riset web lewat Tavily REST langsung (`TAVILY_API_KEY` dari `.env` lokal, dimuat `server.py`); hasil `verified:false`, bukan fact-check. Google grounding sudah dihapus |
| `creator-dashboard/{analytics_import,analytics_learning}.py` | Pemetaan CSV eksplisit, retensi per scene, observasi lokal 24h/7d dan keputusan eksperimen |
| `creator-dashboard/article_storage.py` | Penulisan privat, staging dokumen, journal commit dan rollback/recovery artikel; dipakai revisi, diagram, unggah gambar dan rebuild |
| `creator-dashboard/{article_tools,evidence,source_reader,local_diagrams}.py` | Ledger kutipan/klaim, revisi bagian dengan backup/persetujuan, fetch HTTPS allowlist, diagram SVG/PNG untuk DOCX |
| `creator-dashboard/{lottie_adapter,visual_review,video_review}.py` | Preview dari JSON Lottie yang diekspor; review media dan screenshot midpoint browser opsional |
| `creator-dashboard/youtube_analytics.py` | Analisis retensi dan hook berbasis heuristik; jangan anggap skor sebagai prediksi performa |
| `creator-dashboard/test_*.py` | Smoke HTTP dan tes fitur dashboard; sebagian berupa skrip mandiri, sebagian `unittest` |
| `creator-dashboard/bin/` | Shim launcher/package manager Windows |
| `creator-dashboard/apps/moneyprinterturbo/` | `webui/` Streamlit; `app/controllers`, `router.py`, `services`, `models`, `config`; `resource/` aset media |
| `creator-dashboard/apps/podcastfy/` | `podcastfy/content_parser/` ekstraksi sumber → `content_generator.py` → `text_to_speech.py`, `tts/`; API di `podcastfy/api/fast_app.py` |
| `creator-dashboard/apps/ai-youtube-shorts-generator/` | `main.py` CLI; `shorts_generator/` pipeline API, `local/` unduh/transkripsi/LLM/potong lokal |
| `creator-dashboard/apps/opencreator/` | Workspace pnpm; `apps/web/src/{app,features,runtime,host}` UI/routing/koneksi runtime/bridge; `apps/daemon/src/` API, agent, gateway, task, scheduler dan persistence; `apps/desktop/` Electron; `packages/` kontrak/config/template/render; `runtime/krillinai/` runtime Go |
| `creator-dashboard/apps/short-video-factory/` | `src/{views,components,router,store,lib,effect-engine}` UI Vue; `electron/` main/preload/IPC, provider dan SQLite; `build/scripts/` skrip build **source**, bukan hasil build |
| `creator-dashboard/remotion_adapter.py`, `apps/video-studio-remotion/` | Scene Plan → manifest 30 fps → komposisi React asli → MP4 + PNG review; npm lockfile tersendiri, tanpa daemon OpenCreator |
| `creator-dashboard/{audio_mastering,video_delivery}.py` | Loudnorm dua tahap; evaluasi profil media Video Studio memakai JSON platform yang sama dengan Clipper |
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
- `references/`: salinan lokal 8 repo pihak ketiga (292 MB, tidak ikut Git). Jangan ikut dipindai saat mencari kode proyek, dan jangan diimpor. Baca hanya bila tugas menyangkut ide dari repo itu; mulai dari `docs/REFERENCES.md`.
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

### Repo referensi (`references/`, katalog di `docs/REFERENCES.md`)

- Delapan repo dipelajari untuk ClipperCuan: `ffmpeg-skill`, `ghost-editor`, `claude-shorts`, `openmontage`, `animate`, `handy`, `agent-reach`, `youtube-automation-agent`. Salinan lokal opsional di `references/` (diabaikan Git; bisa tidak ada pada checkout baru). Versi (commit), lisensi, apa yang dipelajari, apa yang sudah dipakai, dan cara memasang ulang tercatat di [`docs/REFERENCES.md`](docs/REFERENCES.md).
- Perlakukan sebagai bahan bacaan: ambil ide, angka, alur kerja. Jangan salin kode dan jangan menambah dependency ke folder itu. `openmontage` berlisensi **AGPL-3.0**: ide saja, tidak ada kode atau aset.
- Status penyerapan terkini: [`docs/FEATURE-COVERAGE.md`](docs/FEATURE-COVERAGE.md). Snap hening opt-in (`silence.py`), review take/hook (`editorial.py`), cursor eksperimental (`cursor.py`), studi referensi lokal (`reference_study.py`), zona aman dan ekspor per platform sudah diintegrasikan. Heuristik baru belum tervalidasi pada video nyata.
- Angka dari referensi bukan jaminan. Uji pada video nyata sebelum dipakai sebagai default (contoh: ambang crossfade di `shots.py` dikalibrasi pada satu video).
- Catatan kerja dan isu terbuka: [`docs/STATUS-2026-11-01.md`](docs/STATUS-2026-11-01.md); rencana: [`docs/PLAN-TERPADU-2026-10.md`](docs/PLAN-TERPADU-2026-10.md), [`clippercuan/docs/plan-referensi-2026-10.md`](clippercuan/docs/plan-referensi-2026-10.md).

Implementasi lintas fitur: `security.py` meredaksi credential pada respons/log dan menolak redirect serta HTTP remote untuk panggilan LLM dashboard; `research_service.py` menjalankan worker riset terisolasi (opsional pada artikel); `video_job_store.py` menyimpan checkpoint privat mode 0600; `video_review.py` memeriksa stream/durasi hasil MP4. Caption editorial memakai `project.resolve_caption_track`; hasil render menandai revisi caption dan laporan delivery terpisah dari status render. Jangan klaim pemeriksaan metadata sebagai review visual atau verifikasi fakta.

Video Studio: `GET /api/videos/jobs` menemukan pekerjaan tersimpan; `POST /api/videos/jobs/{id}/resume` memulihkan review. API edit/approve/revise/resume wajib menyertakan `revision`; konflik mengembalikan 409. Mengubah storyboard membatalkan persetujuan sebelumnya. Analytics menerima `units=auto|percent|ratio`; mode auto menolak kolom ambigu dan UI menyediakan pilihan satuan eksplisit.

Ekspor Clipper per platform: `platform_specs.json` adalah sumber bersama validator/overlay/preset (profil referensi, bukan ketentuan resmi yang diverifikasi). `caption_geometry.py` merender mask libass pada setiap frame; ekspor memakai semua teks ASS tambahan (caption/title/CTA/watermark teks). Teks bawaan sumber, watermark gambar dan dekorasi tidak termasuk. `platform_export.py` memakai antrean worker, encode H.264/AAC + loudness dua tahap, dan pemeriksaan delivery sebelum unduhan. Varian berada di `projects/<id>/variants/` dan hanya diunduh lewat endpoint tervalidasi, terikat hash MP4/ASS; render lama tanpa hash perlu dirender ulang. Unduhan MP4/ZIP asli tetap merupakan jalur mentah yang terpisah. Permintaan browser yang mengubah data harus memiliki origin tepat (skema/host/port); reverse proxy TLS harus meneruskan skema melalui konfigurasi proxy tepercaya.

Fitur review tambahan: `/api/articles/{slug}/{evidence|rewrite|apply-rewrite|diagram}` mempertahankan revision/digest dan persetujuan; usulan tersimpan muncul kembali di `get_article`. `/api/articles/source` opsional dan default nonaktif tanpa `RESEARCH_SOURCE_HOSTS`. `/api/analytics/import[/inspect]` memakai pemetaan pengguna (bukan schema native tervalidasi), `/observations` menyimpan evaluasi/approval lokal. `/api/videos/{slug}/aspects` membuat job review baru dari salinan plan, termasuk 4:5. `/api/projects/{pid}/study` hanya sampel video lokal 1–120 detik, tanpa fetch otomatis. Jangan menyebut grid musik prosedural sebagai beat detection eksternal, estimasi pacing sebagai alignment kata, atau ledger sumber sebagai verifikasi fakta otomatis.

Audit lanjutan: dashboard memeriksa Host/Origin HTTP tepat termasuk port dan menolak framing request ambigu; bind non-loopback ditolak. Redaksi respons dilakukan pada tree sebelum encoding JSON, bukan pada string JSON. File video divalidasi lalu di-stream dari satu descriptor dengan byte-range/HEAD; file statis tersembunyi, directory listing dan symlink keluar root ditolak. `article_storage.py` merender dokumen di staging, menyimpan journal+backup sebelum publikasi, lalu me-rollback commit terputus saat `_dir` dibaca. Jangan melewati helper ini untuk perubahan artikel. Tes wajib memakai JOB_DIR/VIDEOS_DIR sementara, bukan output pengguna.

Video Studio mendukung `researchMode=planner|web|provided` (default planner sejak pembaruan 2 November). Mode provided wajib naskah dan memakai rencana lokal tanpa provider; tetap melalui dua persetujuan dan tidak memverifikasi fakta. Lottie bisa selesai lokal. MP4 memeriksa runtime sebelum render, menghapus credential aplikasi dari environment renderer, menonaktifkan telemetry dan memakai satu worker; proxy/CA/runtime guard dipertahankan. Waktu adegan finite 0–600 detik, maksimal 200 adegan. Review opsional yang timeout tidak menghilangkan artefak; hasil diberi `unmeasured`. Pemanggilan metode timeline browser harus mengembalikan void/bool, bukan objek GSAP yang cyclic.

Untuk MP4, audio/narasi dibuat dan divalidasi sebelum render visual agar kegagalan layanan suara tidak menghabiskan render. Mux memilih video dari input visual dan audio dari hasil mix secara eksplisit, serta menghapus metadata/chapter sumber.

Target akhir pengguna: **Windows 10/11 x64**; cloud Linux adalah lingkungan pengembangan. `setup-core.bat` menyiapkan empat produk inti dengan venv Windows; `setup-dashboard.bat --core` setara, tanpa argumen memasang aplikasi tambahan. `start-dashboard.bat` memprioritaskan venv dashboard. `runtime_config.find_browser` mencari Chrome/Edge di PATH, Program Files dan LocalAppData. `package-release.ps1` memanggil `package_source.py`; jangan menghapus source `build/` Short Video Factory atau `src/.../projects/`. Izin privat Windows bergantung ACL folder; 0600 hanya klaim POSIX. Laporkan pengujian path/ZIP terpisah dari smoke test langsung pada laptop Windows 10/11 pengguna yang belum dijalankan.

Alur instalasi pilihan pengguna adalah GitHub clone/pull, bukan ekstraksi ZIP. Gunakan `git pull --ff-only` dan pertahankan perubahan/data lokal. Workflow `.github/workflows/windows-core.yml` menguji installer CMD, launcher dan smoke HTTP native Windows dari path berspasi; jangan mengklaim hasil Windows sukses sebelum run selesai. Checkpoint menolak symlink/junction secara eksplisit karena Windows tidak menyediakan O_NOFOLLOW POSIX.

`GET /api/health` adalah liveness dashboard tanpa probe aplikasi lain. Katalog `/api/tools` memeriksa layanan secara paralel dan mempertahankan urutan. Pada Windows, port loopback tertutup dapat menghabiskan timeout koneksi; jangan memakai katalog sebagai health check dua detik. CI mengecek liveness dahulu, lalu memvalidasi katalog terpisah dengan timeout 15 detik.

Bukti Windows core: GitHub Actions run 41300095514 (commit kode b051455) **Success**, mencakup installer, 39 tes terpilih, smoke HTTP dan launcher CMD pada path berspasi. Jangan mengartikan hasil tersebut sebagai verifikasi GPU/TTS daring/seluruh aplikasi tambahan di laptop. Panduan pengguna tetap clone/pull GitHub.

Paket hasil Video Studio: `video_bundle.py`, `GET /api/videos/{slug}/bundle`, tombol Unduh paket produksi. Hanya hasil selesai yang dapat dipaketkan; allowlist artefak, manifest SHA256 byte ekspor, redaksi teks/field credential, batas 2 GiB dan 4 MB per artefak teks, penolakan symlink/junction, satu persiapan arsip bersamaan. Unduhan ZIP di-stream dan direktori temporer dibersihkan; konfigurasi/metadata privat/job tidak diekspor. Ini paket hasil konten, bukan instalasi aplikasi (tetap Git clone/pull).

Handoff juga menyertakan audio mix/voice/music yang tersedia pada allowlist. Review MP4 baru menyimpan `artifact_sha256`; manifest mengikat review ke hash video yang diekspor. Hasil lama ditandai `not_recorded`; video yang telah berubah ditandai `stale_review`, tanpa mengklaim review masih berlaku.

Paket produksi telah lulus CI Windows native run 41317023982 (kode a20076f), termasuk tujuh tes bundle. Source instalasi tetap GitHub; ZIP bundle hanya untuk hasil konten.

Brand kit Video Studio: `GET/POST /api/videos/brands`, katalog `output/brand-kits.json` (maksimal 50, revision wajib, nama sama memperbarui), atomic private write, path symlink/junction ditolak. Plan menyimpan snapshot warna/font sistem/wordmark teks; edit UI wajib mempertahankan seluruh plan termasuk brand/cue. Jangan menerima CSS, font URL atau logo remote. Material 3D tidak seluruhnya mengikuti kit; font tidak di-embed.

`wordCues` menerima `{word,start,end}` atau alias Clipper `{w,s,e}`, detik absolut video. Isi angka/desimal/negasi dan urutan/batas adegan divalidasi; `visualCueWord` indeks mulai 0. Ini input timestamp, bukan forced alignment terhadap audio TTS. Pemicu: bentuk/judul Lottie, judul/panel Opuscar, reticle Three.js. Perubahan storyboard tetap membatalkan approval. Preview Lottie mengikuti urutan layer standar (layer pertama terdepan), termasuk background/wordmark; setiap layer teks wajib menyertakan `t.m` (grouping/alignment) agar player standar dapat merender. Uji isi SVG aktual, bukan hanya `isLoaded`.

Studi referensi Clipper menambahkan `timeline_thirds` berisi bukti per bagian waktu sama, bukan segmentasi cerita. Benchmark publik dan pemetaan enam situs kini ada di `docs/benchmarks/README.md`; fixture hanya di `.data/benchmarks/`, tidak di Git. Tambahan referensi kode Whisper MIT/PySceneDetect BSD-3-Clause hanya ide/tes, tanpa dependency baru. Sampel film menemukan 4/5 cut acuan; jangan menganggap threshold sudah terkalibrasi luas. Sesuai pengguna, jangan menambahkan upload audio pribadi atau manajemen antrean render pada pengembangan ini; CSV asli tetap ditunda.

Pengembangan brand/cue (`117044e`) lulus native Windows run 41322161629 **Success**: setup, tes terpilih termasuk brand/timing, HTTP dan launcher path berspasi. Regresi lokal: 105 tes dashboard, 194 Clipper. Tetap bedakan dari uji provider/GPU laptop.

## 6. Handoff Clipper Cuan — 2 November 2026

Bagian ini adalah catatan kelanjutan kerja untuk agen berikutnya. Baca bersama aturan umum di atas, lalu verifikasi ulang keadaan Git dan runtime sebelum mengubah kode.

### Sudah dikerjakan

- Pipeline unduhan mode Full diperkuat dengan timeout CDN, retry unduhan/fragment, fragment paralel, pesan progres yang lebih jelas, dan dukungan melanjutkan file parsial.
- Metadata sumber otomatis tersedia melalui `source-info.json` dan dapat dimasukkan sebagai watermark sumber pada hasil klip.
- Proyek uji Anthropic `20261102-104242-4e8d` berhasil mengunduh sumber 2560x1440, menjalankan Whisper lokal, membuat kandidat, dan menyelesaikan 10 hasil render lama tanpa error. Data proyek berada di `.data/ClipperCuan/` dan tidak boleh masuk Git.
- Caption publikasi tidak lagi mencampur bahasa. Video Inggris memakai hook, isi, CTA, dan hashtag Inggris; video Indonesia memakai seluruh elemen dalam bahasa Indonesia. Mode `auto` mengikuti bahasa transkrip yang terdeteksi.
- Setiap kandidat baru memiliki `summary` singkat untuk menjelaskan inti klip. Metadata 15 kandidat proyek Anthropic lama juga telah diperbarui tanpa merender ulang MP4.
- Model editorial utama untuk pemilihan momen, judul, ringkasan, dan paket posting adalah `ms/GPT-5.6-Think-Deeper`; fallback `cc/claude-sonnet-5-5` lalu `cc/claude-haiku-5-5`. Model Gemini (`ag/gemini-*`) dan Claude Opus (`cc/claude-opus-*`) ditiadakan atas arahan pengguna (7 Nov 2026); jangan ditambahkan kembali ke rantai/katalog. Worker riset Google Search (`gemini-2.5-flash`, grounding) tetap terpisah dan opsional.
- Auto-render untuk mode Full dan Hemat Disk dibatasi maksimal **Top 5 berdasarkan ranking** melalui `project.auto_picks()`. Kandidat peringkat 6 dan seterusnya tetap `draft_candidate` dan hanya dirender setelah dipilih pengguna.
- Perubahan utama sudah berada pada commit `9c34637e88ef71d05baba450abff7258bac762c5` di `origin/main` dengan pesan `Improve ClipperCuan pipeline and cap auto-render to top 5`.
- Validasi terakhir: compile Python lulus; 202 tes Clipper lulus; 56 tes Creator Dashboard lulus dan 6 dilewati sesuai environment; smoke test `/api/health` lulus; kontrak runtime Top 5 lulus; pemeriksaan diff dan secret tidak menemukan masalah.

### Sedang dikerjakan

- Tidak ada migrasi atau render aktif yang wajib ditunggu pada saat handoff ini.
- Service lokal terakhir berjalan pada `127.0.0.1:8765` dengan 9Router dan GPT-5.6 Think Deeper, tetapi agen berikutnya wajib memeriksa ulang karena status proses lokal tidak persisten lintas sesi atau restart.
- Fokus saat ini adalah observasi stabilitas pada penggunaan nyata setelah perubahan Top 5, terutama mode Hemat Disk, kegagalan URL stream sementara, dan alur pengguna memilih kandidat peringkat 6 ke bawah.

### Akan dikerjakan berikutnya

1. Jalankan satu proyek baru mode Full dan satu proyek baru mode Hemat Disk dengan `auto_render=True`; buktikan hanya rank 1–5 yang berubah menjadi queued/rendering/done dan rank 6 ke bawah tetap draft.
2. Uji tombol/manual API pemilihan kandidat rank 6 ke bawah, lalu pastikan hanya kandidat yang dipilih yang dirender dan hasil Top 5 lama tidak berubah.
3. Tinjau UI Studio agar batas auto-render Top 5 dijelaskan secara eksplisit kepada pengguna, termasuk pesan bahwa kandidat lain tetap tersedia untuk render manual.
4. Tambahkan pengujian integrasi yang memeriksa state proyek setelah auto-render, bukan hanya unit test `auto_picks()`.
5. Pantau log download/render mode Hemat Disk untuk URL kedaluwarsa, retry, dan penggunaan ruang. Jangan mengubah pipeline stabil tanpa reproduksi dan regression test.
6. Bila mengubah ranking, caption, download, atau render, pertahankan GPT-5.6 Think Deeper sebagai model utama, caption satu bahasa, summary kandidat, watermark sumber, dan batas auto-render Top 5.

### Instruksi wajib bagi agen berikutnya

1. Mulai dengan `git pull --ff-only`, `git status --short`, dan baca `AGENTS.md`. Jangan menimpa perubahan lokal pengguna.
2. Jangan menghapus atau memasukkan `.data/`, video sumber, audio, model Whisper, log, project JSON runtime, credential, atau hasil render ke Git.
3. Jangan merender ulang proyek lama hanya untuk memperbarui caption/summary. Perbarui metadata secara atomik jika memang diperlukan dan buat backup atau temporary replacement.
4. Pertahankan pemisahan kandidat dan render. Membuat 10–15 kandidat diperbolehkan; yang otomatis masuk antrean render tetap maksimal lima kandidat terbaik.
5. Kandidat manual, pinned, atau yang dipilih pengguna dapat dirender setelah tahap otomatis, tetapi jangan otomatis mengantrikan rank 6 ke bawah.
6. Setelah perubahan Clipper, dari `clippercuan/app` jalankan minimal:
   - `python -m compileall -q clipper tests`
   - `python -m pytest -q`
   - smoke test `/api/health`
   - pemeriksaan langsung bahwa `auto_picks()` mengembalikan rank 1–5 untuk sepuluh kandidat sehat.
7. Jika perubahan menyentuh Creator Dashboard, jalankan tes dashboard terkait. Jangan menyatakan seluruh monorepo lulus bila hanya subset yang dijalankan.
8. Sebelum commit, jalankan `git diff --check`, periksa diff untuk secret/data runtime, dan pastikan tidak ada file media atau `.env` yang staged.
9. Gunakan commit yang fokus dan push ke `origin/main` hanya setelah semua validasi relevan lulus. Setelah push, bandingkan `git rev-parse HEAD` dengan `git ls-remote origin refs/heads/main` dan pastikan working tree bersih.
10. Laporkan secara terpisah: perubahan kode, validasi otomatis, smoke test runtime, hasil render nyata, dan hal yang belum diuji. Jangan menyebut metadata check sebagai review visual atau uji kualitas video manusia.

## 7. Continuous Motion — 2 November 2026

- Baca `docs/ONETAKE-STUDIO.md` dan status `docs/STATUS-2026-11-02.md` untuk cara mencoba, sumber dan batas. Studi OneTake PolyForm Noncommercial hanya prinsip; tidak menyalin library/template/font/film/aset. Adapter baru ditulis sendiri, bukan klaim seluruh OneTake atau lisensi komersial atas kodenya.
- Engine/style `continuous`/`continuous_motion`: tiga konsep dipilih eksplisit di brief, `motionDesign` + `motionBeatSheet` disimpan pada plan. Durasi wajib tercakup tanpa gap; `assemble` maksimal 12 beat. Edit UI/API mempertahankan metadata dan dua approval; creativeDirection kini dipertahankan normalizer, bukan hilang saat edit.
- `voiceMode=music|tts` hanya untuk adapter kontinu; musik tidak memanggil provider/TTS dan manifest voice kosong. Naskah provided tetap lokal; pilihan model hanya dipakai planner/web. Tolak motionDesign pada edit adapter lama agar tidak mematikan voice secara tidak sengaja.
- Renderer memerlukan Playwright, browser dan FFmpeg dari setup core yang sudah ada. Satu komposisi disajikan lewat server loopback temporer dengan path acak/Host tepat, tanpa menyajikan folder. Request browser lain ditolak, environment credential disaring, sandbox default aktif, satu browser/encoder dua thread, timeout dan cleanup file parsial. Tidak ada antrean baru.
- `__seek(t)` absolut, satu carrier SVG, pause/seek bridge `__timelines.video`, tanpa CDN/random/CSS animation. Review menyimpan geometri setiap batas terjadwal, hash piksel repeat pada satu sampel, midpoint overflow dan perubahan luminansi video terenkode 10 fps/lebar160. Ini pemeriksaan terbatas, bukan semantik/seluruh frame atau jaminan estetika. Tidak ada shutter motion blur/4K60/replika UI otomatis.
- `download.source_identity` menormalkan separator Windows sebelum mengambil stem; jangan menaruh path Windows/UNC atau folder pribadi pada label sumber. Ranking/model/caption satu bahasa dan Top 5 dari handoff di atas tetap dipertahankan.
- KreasiPintar tambahan pengguna belum terbaca (proxy 403). Jangan mengklaim telah mempelajari fitur/hasil halamannya. Upload audio pribadi/manajemen antrean tetap di luar lingkup.

Optimisasi Continuous Motion: `__renderKey` harus mencakup semua dependency visual yang berubah (beat/transisi/viewport saat ini; palet/data statis). Renderer menyimpan hanya satu PNG terakhir dan tetap mengirim seluruh frame ke encoder; tanpa key string valid selalu capture normal. Jika menambahkan animasi/aset berbasis waktu, perbarui key atau matikan reuse agar tidak membekukan gerakan. Tes wajib membandingkan hash frame terdekode cache vs tanpa cache. MP4 hasil menu memakai preload metadata tanpa autoplay/loop. Sesuai arahan terbaru pengguna, jangan memutar media saat melanjutkan pekerjaan; gunakan tes/render/analisis file.

CI optimisasi gerak `0ee7fb8`: Windows native run 41408700428 **Success**, termasuk tes kesetaraan frame cache/tanpa cache. Regresi lokal 116 dashboard dan 202 Clipper lulus; integrasi sebelumnya `8ec9c9d` juga lulus Windows 41407046842 serta Clipper 41407047005. Jangan memutar media ketika melanjutkan tugas sesuai arahan pengguna.

Audit renderer: baca `docs/RENDERER-AUDIT-2026-11-02.md`. Video Studio Three.js memakai CDN 0.160.0, berbeda dari manifest Lemo ^0.170.0; GSAP 3.13.0, HyperFrames terpasang 0.8.195. `animation_clock.py` menyinkronkan CSS WAAPI scene-relative dan draw WebGL pada render/totalTime GSAP, termasuk suppressed seek. Jangan mengganti objek GSAP registry dengan stub: HyperFrames memakai interface/chaining aslinya. Template juga mengekspos DUR/render/READY untuk kontrak core Lemo; produksi tetap HyperFrames. Bintang 3D di-seed, buffer disimpan untuk screenshot; uji repeat/reload piksel. Pada audit awal, Remotion hanya alur Stickman/OpenCreator dan runtime belum dipasang. Kini Remotion Editorial sudah menjadi engine Video Studio melalui adapter asli; baca bagian 8. Launcher preview Stickman lama tetap memerlukan timeline valid. Kontrol eksplisit scenes[].renderControls kini diterapkan oleh scene_render.py pada GSAP/Three.js; camera/lighting/transition berupa kalimat bebas tetap catatan. Jangan menyebut seluruh arahan sudah dilaksanakan renderer. Tidak memutar media dalam audit ini.

Audit clock renderer `e17d95a` lulus Windows native run 41416880214 **Success**. Lokal: 119 tes dashboard dan smoke HTTP lulus; SDK GSAP 3.13.0/Three.js 0.160.0 diuji frame statis software WebGL, bukan playback/GPU laptop. Rincian gap dan pengembangan lanjut ada pada dokumen audit, sebagai catatan sebelum adapter Remotion Editorial ditambahkan; field kamera/lighting bebas tetap arahan.


Perbaikan lintas menu: baca `docs/INTEGRATION-REVIEW-2026-11-02.md`. `creator-dashboard/scene_render.py` memvalidasi camera/lighting/transition allowlist dan strength finite 0–1; normalizer/editor/prompt/generator menerapkannya hanya pada opuscar/threejs, tetap dua approval. Transformasi ilustrasi diinisialisasi identitas agar seek sebelum tween konsisten; kamera/lampu 3D ditulis dari waktu absolut dan direset pada tiap adegan/gap. `evidence.py` menambahkan diagnostik angka literal/sitasi gabungan/rujukan, tanpa mengubah attestation atau mengklaim fact-check. `clipper/preflight.py` memeriksa rentang/track caption efektif, dipakai batch/render dan endpoint baca saja `.../clips/{cid}/preflight`; tambah/edit menolak waktu nonfinite. Auto picks hanya menyaring lima posisi teratas, banned tidak pernah menjadi fallback, tanpa picks kembali candidates_ready. Tes state pipeline meliputi rank 6 tetap draft lalu dipilih manual. Tidak merender ulang artefak lama atau menambah upload audio/manajemen antrean.

Validasi perubahan lintas menu `0832ee6`: 126 tes dashboard dan 223 tes Clipper lokal lulus; 24 kasus frame statis SDK GSAP/Three.js lulus; smoke UI empat engine/artikel dengan fixture lulus tanpa playback. CI native Windows 41422103700 dan Clipper 41422103657 **Success**. Bukti/metode/batas: `docs/INTEGRATION-REVIEW-2026-11-02.md`, `docs/benchmarks/studio-controls-audit-20261102.json`. Jangan menyamakan smoke fixture, pemeriksaan literal angka, dan frame statis Linux dengan verifikasi fakta atau benchmark GPU laptop Windows.

## 8. Produksi terpadu Remotion, FFmpeg dan Article

Baca `docs/UNIFIED-PRODUCTION-2026-11-02.md` untuk peta delapan referensi, pemanggilan kode dan bukti/batas. Engine `remotion`/style `remotion_editorial` memakai SDK 4.0.540, React 18.3.1, TypeScript 5.7.3 di `apps/video-studio-remotion`, bukan daemon/worker Stickman. Versi 4.0.540 menggantikan 4.0.473 untuk menutup advisory transitif pada `esbuild`, `ws`, dan `zod`; pertahankan semua paket Remotion pada versi persis yang sama. `setup-core.bat` memasang runtime tambahan dari lockfile. Pertahankan dependency terisolasi, jangan menyatukan pnpm workspace. Validasi lokal paket: `npm ci`, `npm audit --omit=dev`, `npm run typecheck`, `npm test`; CI Windows juga menjalankan pipeline MP4 nyata dari path berspasi.

Manifest 30 fps divalidasi di Python dan Node: coverage penuh, frame integer, preset/warna/font allowlist, tanpa URL/script/aset remote. Renderer menerima JSON privat, browser terpasang, environment disaring; timeout/cleanup termasuk proses anak. Family process/data/comparison; lainnya concept. Caption tanpa wordCues adalah estimasi potongan teks, bukan alignment suara. Mode audio plan `audioMode=music|tts` hanya untuk Remotion, wajib dipertahankan saat edit/varian rasio; musik sepenuhnya lokal. Dua approval/revision tetap wajib. Frame pertama berisi konten, PNG midpoint dan repeat diuji; DOM review hanya komposisi terlihat pada interval stabil, bukan kalkulator tersembunyi atau seluruh kualitas semantik.

`audio_mastering.py` memakai loudnorm dua tahap lalu audio hasil encode diukur lagi. `video_delivery.py` membaca `clipper/platform_specs.json` untuk pemeriksaan per platform (profil referensi, bukan aturan resmi); hasil ada pada review. Warning Clipper sekarang needs_attention meskipun format ok, ditampilkan sebagai hasil terakhir, tanpa render ulang proyek lama. `article_tools.improvement_plan` membuat prioritas lokal; tombol UI menyiapkan proposal bahasa melalui guard angka/sitasi/negasi dan digest lama. Jangan mengubahnya menjadi apply/fact-check/auto-publish tanpa review.

Validasi lokal: 134 tes dashboard, 227 Clipper, typecheck/suite Node, HTTP/health dan UI fixture lima engine/proposal artikel lulus. Empat MP4 nyata termasuk 1080×1920: 60 frame/2 detik, H.264/YUV420/BT.709, -14 LUFS; bukti teks di `docs/benchmarks/remotion-studio-20261102.json`. Tanpa playback, provider daring, audio pribadi atau pengelola antrean baru. CI Windows final 41431931788 (`7fc4dcb`) dan Clipper 41430689180 (`530f809`, kode Clipper tetap identik) **Success**. Windows mewajibkan runtime Remotion sebelum tes agar integration encode tidak bisa terlewati karena runtime hilang. Jangan menyamakan benchmark sintetis Linux dengan kualitas cerita atau GPU laptop pengguna.

Implementasi utama Remotion `530f809`: Windows native 41430689110 dan Clipper 41430689180 **Success**. Koreksi metrik menjaga tanda minus/plus/desimal, memilih angka judul sebelum narasi agar tidak menggandakan statistik, dan menolak ekstraksi ekor token mata uang; regression ada di Python/Node. Benchmark empat rasio diperbarui setelah koreksi. Koreksi `d934aca` dan gate `7fc4dcb` lulus Windows final 41431931788 **Success**; kode Clipper tetap sama.

Perbaikan Opuscar 3 November: `docs/OPUSCAR-FIXES-2026-11-03.md`. Generator menghapus dekorasi radar/grid/orbit global dan grafik data hardcoded; metrik literal mempertahankan tanda/desimal. Subtitle berada dalam flow layout dan judul diukur maksimal tiga baris. Tes browser `test_opuscar_layout.py` memakai SDK GSAP 3.13.0 lokal melalui `GSAP_TEST_SCRIPT`; jangan samakan kelulusan fixture layout dengan penyelesaian re-architecture subject/action pada audit handoff. Renderer keluarga visual lama masih dipakai.

Renderer Opuscar terarah: baca `docs/OPUSCAR-DIRECTED-REVIEW-2026-11-03.md` dan treatment pasangannya. `opuscar_scene_spec.py`, `opuscar_primitives.py`, `opuscar_actions.js` menyediakan grammar mekanis terbatas; `directionSubject` menyimpan subjek produksi panjang terpisah dari label lama, `continuityToken` mengikat prop antar-shot. Semua job Opuscar membuat review PNG sebelum approval Storyboard. `visualReview.digest` terikat HTML/drawing code; edit membatalkan review/approval; API dan worker menolak review hilang/stale/gagal. Jangan bypass gate atau menganggap `sampled` sebagai verifikasi semantik. `opuscar_preview.py` membuat stills tanpa TTS/full encode dan menolak overwrite folder. Regresi browser memakai `GSAP_TEST_SCRIPT` GSAP 3.13.0; toleransi raster 2/255 pada ≤1% piksel dicatat terpisah dari DOM identik. Fixture 19 shot adalah rekonstruksi audit, bukan naskah produksi 109 detik. Tidak memutar media.

Audit lintas engine 4 November: baca `docs/ENGINE-QUALITY-2026-11-04.md`. Three.js kini memakai geometri native per subjek mekanis di `three_scene.js`, bukan icosahedron/grid/partikel global; absolute pose, material terpisah per shot dan crossfade objek wajib tetap deterministik. `scene_diagram.py` memvalidasi diagram eksplisit Remotion/Lottie (`process` 2–5 label, `comparison` 2 label, maksimal 48 karakter); pertahankan normalisasi/editor/storyboard/validator Node dan dua approval. Jangan mengarang langkah proses bila diagram tidak tersedia. Tes Three.js nyata membutuhkan `GSAP_TEST_SCRIPT` dan `THREE_TEST_SCRIPT` dengan SDK pinned. Lottie diuji juga memakai player resmi 5.12.2; tetap subset, bukan implementasi seluruh Lottie. Empat MP4 1080×1920 diuji tanpa playback; batas kualitas/Windows/produksi asli tercatat dalam dokumen, jangan mengklaim semua arahan prosa sudah dirender.


Lanjutan Three.js: jumlah 1–12 pada grammar tidak boleh dipotong tujuh; `visualCueWord` menunda awal fase aksi objek melalui `cueOffset`, sementara transisi memakai waktu scene. Slide menggerakkan objek dan overlay; origin objek wajib di-reset tiap seek. Regresi `test_three_scenes.py` menguji jumlah 12, pose sebelum/sesudah cue, slide dan repeat. Detail/bukti di `docs/ENGINE-QUALITY-2026-11-04.md`.

Video Studio 60 fps: baca `docs/VIDEO-STUDIO-60FPS.md`. `frame_rate.py` memvalidasi integer 30/60; job baru default60, plan/job lama tanpa fps fallback30. Jangan memakai FPS hardcoded pada adapter/seek/caption/keyframe atau menggandakan kecepatan animasi. Brief, normalizer, editor, varian rasio, metadata, HyperFrames, Remotion, Continuous dan Lottie wajib mempertahankan fps. Review MP4 mencocokkan fps terukur. Tes `test_frame_rate.py` mencakup legacy/default/varian, timing layer dan kesetaraan cache60; tidak merender ulang proyek lama.

Preproduksi narasi-first: baca `docs/VIDEO-PREPRODUCTION-2026-11-04.md`. `video_preproduction.py` menjaga narasi utuh sebelum scene planning dan menyusun paket prompt per shot. Job baru `pipelineVersion=2`; API/worker memverifikasi paket terikat plan/engine/aspect sebelum audio/render. Dua approval tetap berlaku; edit membatalkan paket dan memperbarui narasi. `creativeBrief` terpisah dari teks suara. Fallback lokal harus mengelompokkan seluruh naskah, tidak memotong setelah 12 kalimat. Ekspor allowlist/bundle menambah `narration.json` dan `production-prompts.json`. Prompt prosa bukan executable atau jaminan semua arahan diterapkan. Tes `test_video_preproduction.py` wajib; riset primer dan bukti/batas ada di dokumen.

Suara gratis baru: `speech_settings.py` + `speech_worker.py`, dokumentasi `docs/VIDEO-STUDIO-VOICE-2026-11-04.md`. Job UI baru default Edge-TTS 7.3.1, Indonesia Ardi; opsi Inggris Guy/tanpa suara. Musik latar otomatis mati pada plan `speech`; SFX pendek diperbolehkan sesuai klarifikasi pengguna. Preferensi terbaru pengguna memperbolehkan musik, SFX dan elemen lain bila meningkatkan kualitas hasil; musik nonaktif adalah default implementasi saat ini, bukan larangan pengguna. Jangan memakai fallback berbayar. Pertahankan naskah pengguna, timing scene, paket approval, proxy/CA/TLS dan pengaturan suara pada edit/varian. Lottie menyertakan WAV terpisah bila TTS dipilih. Plan legacy tanpa speech mempertahankan perilaku lama. Katalog daring berhasil, tetapi sintesis audit ID/EN menghasilkan NoAudioReceived; jangan mengklaim suara neural nyata telah lolos atau memutar media. `test_speech_settings.py` wajib.

SFX: `sound_effects.py` menghasilkan efek pendek sesuai cue, dengan volume rendah/ducking narasi; tidak ada musik kontinu. `speech.sfx` defaulttrue pada job baru, missing pada setting lama fallbackfalse; mode none menonaktifkan seluruh audio. Pertahankan flag pada editor/varian/paket approval. Tes `test_sound_effects.py` memeriksa jendela senyap/determinisme dan suite suara menguji mix FFmpeg; bundle boleh memuat `sound-effects.wav`.

Prioritas kualitas akhir (klarifikasi terbaru pengguna): musik/SFX/elemen pendukung boleh dipilih berdasarkan kebutuhan cerita. Nilai kesesuaian narasi–visual, pacing, kontinuitas, keterbacaan dan kejernihan suara; jangan menambah efek hanya untuk memenuhi jumlah. Bedakan hasil tes teknis dari review kualitas video. Preferensi ini menggantikan pembatasan musik sebelumnya, tanpa otomatis mengubah audio proyek yang telah disetujui.

Kontrak renderer: baca `docs/RENDERER-CONTRACT-2026-11-04.md`. `renderer_contract.py` memasok kemampuan native kepada scene planner dan diagnostik `rendererReview`; API/worker pipeline2 menolak error sebelum audio/render, warning fallback tetap dapat ditinjau. Simpan edit memperbarui diagnostik. Paket prompt memuat laporan yang terikat plan. Pemilihan fallback Opuscar/metrik literal kini shared; jaga kesesuaian generator dengan diagnostik. Token aksi resmi (termasuk expand) diterima parser tanpa mengabaikan pasangan objek/aksi. Tes `test_renderer_contract.py` wajib. Supported adalah cakupan implementasi, bukan jaminan kualitas semantik/estetika.
