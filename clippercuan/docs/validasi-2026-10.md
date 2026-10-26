# Validasi ulang ClipperCuan — 26 Oktober 2026

Metode: baca seluruh kode inti, jalankan 36 tes yang ada, lalu jalankan alur nyata (video sintetis → transkrip → kandidat → render → selesai) yang **belum pernah diuji tes lama**. Riset eksternal hanya dipakai untuk keputusan teknis; angka performa dari blog pihak ketiga diperlakukan sebagai heuristik.

## Bug yang ditemukan dan sudah diperbaiki
| # | Tingkat | Temuan | Perbaikan |
|---|---|---|---|
| 1 | **Kritis** | `clips` dan `candidates` tersimpan sebagai dua salinan. Render/edit hanya menulis `clips`, UI/worker membaca `candidates` → proyek **tidak pernah berstatus done**, webhook/ekspor otomatis tidak jalan, CLI menggantung selamanya. Memilih ulang/pin kandidat juga menimpa hasil render. | Satu daftar bersama (`_unify_clips`) + migrasi proyek lama; `rerank` mempertahankan field render/edit dan tidak membuang klip yang sudah dirender/manual. |
| 2 | **Kritis** | CLI, MCP, dan inbox memakai `auto_render=False` (bawaan baru) → berhenti di "kandidat siap" tanpa klip. | Ketiganya memakai `auto_render=True`. |
| 3 | Tinggi | Webhook `project.done` terkirim sebelum render dan ekspor otomatis kosong; render gagal membuat proyek macet di "rendering". | `_finish_renders`: status akhir + notifikasi sekali setelah render terakhir; kegagalan dilaporkan; event baru `project.candidates_ready`. |
| 4 | Tinggi | "Render ulang semua" merender semua kandidat (termasuk yang tidak dipilih). | Hanya klip terpilih/sudah dirender/manual. |
| 5 | Sedang | Regex di raw-string (`\\b`, `\\s`): penalti ketergantungan konteks tidak pernah aktif, opsi judul tidak memecah kalimat. | Diperbaiki + tes. |
| 6 | Sedang | Subtitle YouTube otomatis tanpa tanda baca → semua klip dianggap "tidak berakhir bersih". | Jeda ≥0,45 dtk dipakai sebagai batas kalimat bila transkrip tidak berpunctuation. |
| 7 | Sedang | Kata ganti/negasi umum (kamu, aku, tidak…) menaikkan skor hook di hampir semua kalimat. | Dipindah ke bobot kecil (0,03). Variabel mati dihapus. |
| 8 | Sedang | Server lokal tanpa token rentan DNS-rebinding/CSRF lintas situs; mode server bisa membaca file mana pun lewat `source`. | Middleware Host/Origin lokal (`CLIPPER_ALLOWED_HOSTS` untuk tambahan); di mode token path file dibatasi ke folder data. |
| 9 | Sedang | Unduhan YouTube: yt-dlp kini butuh runtime JavaScript + `yt-dlp-ejs`. | `yt-dlp[default]`, deteksi deno/node/bun/quickjs, `remote_components=ejs:github`, Node di Dockerfile. |
| 10 | Sedang | Dockerfile mengunduh model Whisper ke `/opt/models` yang tidak pernah dibaca. | Ke `/data/models`. |
| 11 | Sedang | Workflow CI berada di `clippercuan/.github` sehingga **tidak pernah dijalankan GitHub**, dan path `app` salah. | Dipindah ke `.github/workflows/` root + CI tes otomatis (pytest + ruff F/E9). |
| 12 | Kecil | `/files/<pid>` dengan id aneh → 500. Model `large-v3-turbo` tidak ada di UI. | 404; opsi turbo ditambahkan. |

Hasil: 42 tes lulus (6 baru, termasuk uji render end-to-end dengan FFmpeg).

## Riset (ringkas)
- **yt-dlp/YouTube:** dokumentasi yt-dlp-ejs menyebut JS runtime (Deno/Node/Bun/QuickJS) wajib untuk tantangan player; tanpa itu unduhan makin sering gagal. Sumber: https://www.mintlify.com/yt-dlp/ejs , https://github.com/yt-dlp/yt-dlp/issues/15897
- **Whisper:** `large-v3-turbo` (decoder 4 layer, ±8× lebih cepat dari large) tersedia di faster-whisper. Tidak ada benchmark independen bahasa Indonesia di CPU; **jangan mengubah default `small` tanpa uji pada audio Anda sendiri**. Sumber: https://medium.com/axinc-ai/whisper-large-v3-turbo-high-accuracy-and-fast-speech-recognition-model-be2f6af77bdc
- **Hook Shorts:** panduan kreator menyebut metrik "Viewed vs swiped away" di YouTube Studio; ambang 30%/50%/70% berasal dari blog pihak ketiga, bukan dokumentasi resmi — jangan dijadikan klaim produk. Sumber: https://vidiq.com/blog/post/youtube-shorts-algorithm/

## Backlog yang belum dikerjakan (butuh keputusan/uji)
1. Benchmark WER Whisper small vs turbo pada 5–10 video Indonesia nyata, lalu tentukan default per perangkat (GPU/CPU).
2. Sinyal visual untuk skor (deteksi pergantian scene/gerak) — saat ini "visual_activity" hanya turunan energi audio.
3. Pool kandidat LLM dibatasi 30 dan tidak dipecah per segmen waktu (`chunk_ranges` ada tetapi belum dipakai) → video >1 jam kurang terwakili.
4. `build-desktop` perlu dicoba nyata di Windows/macOS (belum bisa dijalankan dari sini); `creator-dashboard/tools.json` memakai perintah `cmd` khusus Windows.
5. Validasi nilai `settings` (layout/posisi tidak valid masih menyebabkan KeyError saat render).
6. Ruff gaya (B904, B905, S-rules) masih banyak; tidak mengubah perilaku, sengaja tidak disentuh.
