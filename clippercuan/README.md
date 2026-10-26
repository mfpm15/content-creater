# ClipperCuan — aplikasi AI clipper lokal

Ubah video panjang (link YouTube/TikTok/IG atau file) jadi klip vertikal siap upload, **di laptop sendiri**:
tanpa langganan, tanpa kuota, tanpa upload ke cloud.

## Cara pakai — paket siap pakai (tanpa Python)
Paket dibuat manual: tab **Actions → Build desktop app → Run workflow**, lalu unduh dari bagian *Artifacts*.
Jalankan `ClipperCuan.exe` (Windows) atau `ClipperCuan` (macOS: klik kanan → Open pada pertama kali).

## Cara pakai — di server cloud
Lihat [docs/cloud.md](docs/cloud.md): `docker build` + `docker run` dengan `CLIPPER_TOKEN`.

## Cara pakai — dari kode sumber (sekali klik)
1. Pasang **Python 3.10–3.12** dari https://www.python.org/downloads/ (Windows: centang *Add Python to PATH*).
2. Buka folder `app/` lalu:
   - **Windows:** klik dua kali `start.bat`
   - **macOS:** klik dua kali `start.command` (pertama kali: klik kanan → Open)
   - **Linux:** `./app/start.sh`
3. Pertama kali akan memasang komponen (±1–5 menit). Browser terbuka otomatis ke `http://127.0.0.1:8765`.
4. Tempel link / pilih file → atur gaya → **Mulai generate klip**.

FFmpeg sudah ikut terpasang otomatis. Model transkripsi Whisper diunduh sekali saat pertama dipakai (small ±480 MB).
Hasil tersimpan di folder `~/ClipperCuan/projects/` (tombol **Buka folder** di aplikasi).

## Fitur
| Fitur | Keterangan |
|---|---|
| Studio | Satu layar seperti aplikasi desktop: preview 9:16 dengan caption & judul tampil langsung, panel Instant style / Clip setting / Branding, deretan *Detected clips* (skor x/10, filter Hot/Terpilih/Rendered), bilah render |
| Resep gaya viral | 7 resep satu klik: Podcast Box merah, Podcast Hormozi, Quote glow, Review tech, Mobile Legends hype split, Edukasi word-by-word, Campaign clipping (`--recipe` di CLI, `recipe` di MCP) |
| Hemat disk | Link: hanya audio yang diunduh, potongan klip diambil saat render lalu dihapus (`--lite`). File lokal tidak diduplikasi |
| Sumber video | Link YouTube/TikTok/Instagram/dll (yt-dlp, maks 1080p) atau file lokal (drag & drop); cookies browser bila YouTube minta verifikasi |
| Subtitle otomatis | Mode Otomatis: subtitle YouTube → API cloud (Groq/OpenAI/9router) → Whisper lokal; timestamp per kata, 14+ bahasa, opsi terjemah ke Inggris |
| Cari momen | Skor hook (pertanyaan/angka/kata pemicu), kata emosional, energi audio, **aktivitas visual (scene & gerak dari keyframe)**, tempo bicara, kalimat utuh |
| Judul pembuka | Otomatis dari kalimat paling kuat; preset Duo glow (2 baris) / Bar / Outline / Neon / Clean; pilihan judul alternatif per klip |
| Caption | Plain, Karaoke, Word by word, **Subtract & font** (kata kunci serif/script miring) · Box highlight ON/OFF · efek Glow · 12 font · posisi vertikal bebas · animasi pop |
| Format | Portrait 9:16, Square 1:1, Blur background, Split gaming (facecam + gameplay), Landscape |
| Smart crop | Ikuti wajah otomatis + **Crop studio**: keyframe yang menahan framing, zoom/resize crop, posisi vertikal, 9:16/1:1, live output, Apply to all |
| Watermark | Teks atau logo PNG, posisi & transparansi |
| Editor klip | Ubah judul, potong ulang (±0,5 dtk), **editor caption layar penuh** (ejaan, font/warna/ukuran per kata, kata kunci, pilih semua), format per klip, pin/ban/hapus |
| Klip manual | Pilih sendiri potongan dari video (putar, tandai mulai/selesai) |
| Potong jeda hening | Jump cut otomatis berbasis timestamp kata — caption & crop ikut menyesuaikan |
| Split gaming visual | Seret & ubah ukuran kotak FACECAM / GAMEPLAY di atas frame video |
| Ekspor | MP4 per klip, subtitle .SRT, **Download semua (ZIP)** + file caption posting |
| Paket posting | Caption + hashtag otomatis per klip (bisa diedit, tombol Salin) |
| Galeri & riwayat | Riwayat proyek + **Galeri klip** lintas proyek (hover untuk putar), cari & hapus, status antrean |
| Template gaya | Simpan & pakai ulang kombinasi format/caption/judul/watermark |
| Batch | Banyak link sekaligus (satu per baris) → diproses berurutan |
| Emoji otomatis | Emoji muncul saat kata kunci diucapkan (uang 💰, rahasia 🤫, kaget 😱 — 50 emoji, ID/EN) |
| Progress bar & CTA | Garis progres berjalan + ajakan di akhir ("Follow untuk part berikutnya!") |
| Musik latar | Pustaka musik sendiri, volume, ducking otomatis (musik turun ±12 dB saat ada suara) |
| Pembicara aktif | Podcast 2+ orang: crop pindah ke wajah yang sedang bicara (YuNet + gerak bibir); tanpa wajah → ikuti gerakan |
| AI agent (MCP) | 11 tools untuk agent: buat klip, tunggu, edit, tambah/hapus klip, restyle, ekspor, template, cek sistem |
| Otomatisasi | Webhook saat selesai, folder pantau (inbox) auto-proses, ekspor otomatis ke folder, CLI `--json`, REST API `/docs` |
| Cek sistem & Bantuan | FFmpeg/libass, GPU, model terunduh, ruang disk; panduan & solusi masalah |
| Notifikasi | Notifikasi desktop + bunyi saat proyek selesai, estimasi sisa waktu |
| AI router (opsional) | 9router / API kompatibel OpenAI untuk memilih momen & judul (mati secara default) |
| Mode CLI | `python -m clipper cli <link/file> --clips 5 --layout portrait` |

## Kebutuhan perangkat
RAM 8 GB (disarankan 16 GB), Windows 10/11 64-bit, macOS 12+ (Intel/Apple Silicon), atau Linux. GPU NVIDIA dipakai otomatis jika ada.
Perkiraan waktu (CPU 4 core, model *small*): video 2 menit ≈ 1–1,5 menit untuk 3 klip.

## AI router (9Router)
Backend membaca `LLM_BASE_URL`/`OPENAI_BASE_URL`, `LLM_API_KEY`/`OPENAI_API_KEY`, dan `LLM_MODEL`/`OPENAI_MODEL`.
Default lokal memakai `http://localhost:20128/v1` serta model `ag/gemini-3.8-flash-medium`. Request chat dikirim ke
`/chat/completions`; credential tidak ditulis ke frontend atau repository. Pengaturan UI tetap tersedia, tetapi environment
menjadi sumber prioritas agar konsisten dengan dashboard. Jika router mati, aplikasi otomatis kembali ke skor lokal.

## Struktur
```
app/
  start.bat / start.command / start.sh   installer + launcher
  requirements.txt
  clipper/
    download.py    ambil video (yt-dlp / file)
    transcribe.py  Whisper + timestamp kata
    highlights.py  penilaian & pemilihan momen
    llm.py         klien 9router/OpenAI-compatible (opsional)
    facetrack.py   smart crop wajah → keyframe
    captions.py    subtitle ASS (caption/judul/watermark)
    render.py      ffmpeg: crop/blur/split + burn-in
    project.py     pipeline, antrean, riwayat, edit
    server.py      API lokal (127.0.0.1)
    web/           UI aplikasi
    fonts/         font OFL untuk caption
app/tests/           tes otomatis (cd app && python -m pytest -q tests)
docs/feature-map.md  peta fitur referensi → implementasi
docs/usulan-fitur.md fitur tambahan versi kita + usulan berikutnya
docs/agent-api.md    panduan AI agent: MCP, CLI, REST, webhook, inbox
docs/cloud.md        tanpa membebani laptop: subtitle cloud, server Docker + password
docs/validasi-2026-10.md audit ulang, bug yang diperbaiki, riset, dan backlog
(CI ada di ../.github/workflows/clippercuan-*.yml: tes otomatis + build paket manual)
site/                landing page (opsional, untuk jualan)
```

## Lisensi komponen
Whisper (MIT), faster-whisper (MIT), yt-dlp (Unlicense), FFmpeg (LGPL/GPL via imageio-ffmpeg), OpenCV (Apache-2.0),
font di `app/clipper/fonts` (SIL OFL: Anton, Bebas Neue, Poppins, Bangers, Montserrat, Barlow Condensed, Instrument Serif, Pinyon Script), emoji Twemoji (CC-BY 4.0), detektor wajah YuNet (MIT), MCP Python SDK (MIT). Pastikan Anda punya hak atas video yang Anda klip.
