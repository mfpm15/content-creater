# Content Creator Control Center

Satu dashboard lokal untuk menjalankan, memantau, dan membuka lima tool pembuat konten (video, podcast, dan workspace kreator) dari satu tempat.

> Deskripsi singkat repo (untuk kolom About GitHub):
> **Dashboard lokal untuk menjalankan MoneyPrinterTurbo, Podcastfy, OpenCreator, Short Video Factory, dan AI YouTube Shorts Generator, dengan LLM lewat gateway OpenAI-compatible.**

## Isi

| Tool | Fungsi | Tipe | Alamat |
|---|---|---|---|
| MoneyPrinterTurbo | Topik menjadi video faceless (naskah, suara, subtitle, footage, BGM) | Web (Streamlit) | http://127.0.0.1:8501 |
| Podcastfy | Website, PDF, teks, atau video menjadi percakapan podcast | API (FastAPI) | http://127.0.0.1:8080/docs |
| OpenCreator | Workspace kreator: script, image, video, dubbing, agent, workflow | Web (Vite) | http://127.0.0.1:19861 |
| Short Video Factory | Editor desktop: template, subtitle, efek, render batch | Desktop (Electron) | jendela Electron |
| SupoClip | Video panjang menjadi klip vertikal 9:16 (pilih momen oleh LLM, skor viral, subtitle, editor) | Web (Docker Compose) | http://127.0.0.1:3107 |
| AI YouTube Shorts Generator | Potong video panjang menjadi Shorts dengan highlight dari LLM | CLI | dijalankan manual |

Dashboard sendiri berjalan di http://127.0.0.1:3210. Dari sana tiap tool bisa di-start, di-stop, dicek status kesiapannya, dan dilihat lognya.

## Struktur

```
content-creater/
├─ README.md
├─ start-dashboard.bat      # jalankan dashboard
├─ setup-dashboard.bat      # install dependensi semua tool
├─ CREATOR-DASHBOARD.md     # catatan detail dashboard
└─ creator-dashboard/
   ├─ server.py             # backend dashboard (Python stdlib)
   ├─ tools.json            # daftar tool + perintah start
   ├─ static/               # UI (index.html, styles.css, app.js)
   ├─ bin/pnpm.cmd          # shim pnpm untuk Windows tanpa corepack enable
   ├─ test_dashboard.py     # smoke test
   └─ apps/                 # kelima tool (source masing-masing)
```

## Kebutuhan

- Windows 10/11
- Python 3.11+ dan [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (corepack tersedia)
- FFmpeg di PATH
- Opsional: gateway LLM OpenAI-compatible, misalnya 9Router di `http://localhost:20128/v1`
- Docker Desktop, hanya untuk SupoClip (butuh Postgres dan Redis)

## Mulai cepat

```bat
setup-dashboard.bat
start-dashboard.bat
```

Lalu buka http://127.0.0.1:3210 dan klik Start pada tool yang dibutuhkan.

Cek dashboard:

```bat
python creator-dashboard\test_dashboard.py
```

## Konfigurasi LLM

Semua tool diarahkan ke satu endpoint OpenAI-compatible:

- Base URL: `http://localhost:20128/v1`
- Model: `ag/gemini-3.8-flash-high`
- API key: isi sesuai gateway Anda (gateway lokal bisa menerima placeholder)

File konfigurasi lokal tidak ikut di repo (diabaikan oleh `.gitignore`). Setelah clone, buat sendiri:

| Tool | File |
|---|---|
| MoneyPrinterTurbo | `creator-dashboard/apps/moneyprinterturbo/config.toml` (salin dari `config.example.toml`) |
| Podcastfy | `creator-dashboard/apps/podcastfy/.env` |
| AI YouTube Shorts Generator | `creator-dashboard/apps/ai-youtube-shorts-generator/.env` (salin dari `.env.example`) |
| SupoClip | `creator-dashboard/apps/supoclip/.env` (salin dari `.env.example`; set `LLM=openai:<model>`, `OPENAI_API_KEY`, `OPENAI_BASE_URL=http://host.docker.internal:20128/v1`, `TRANSCRIPTION_PROVIDER=whisper`, dan ganti semua secret) |
| OpenCreator, Short Video Factory | default LLM ada di source (`creator-services.ts`, `src/lib/llm/config.ts`), ubah di UI tiap tool |

Jangan commit API key.

## Catatan

- Generasi gambar/video (Nano Banana, Veo) belum terpasang. Gateway 9Router belum punya provider gambar, dan MoneyPrinterTurbo belum punya adapter Google native.
- OpenCreator menjalankan build paket terlebih dahulu sebelum Vite, jadi start pertama lebih lama.
- Dashboard hanya menjalankan perintah yang tertulis di `tools.json`, tidak menerima perintah dari browser. Biarkan terikat ke `127.0.0.1`.
- Font macOS besar (`STHeiti*.ttc`) tidak ikut di repo.

## Lisensi

Kode dashboard di `creator-dashboard/` (kecuali `apps/`) milik pemilik repo ini. Setiap tool di `creator-dashboard/apps/` memakai lisensi aslinya, lihat file `LICENSE` dan README di folder masing-masing. Source tool sudah dimodifikasi lokal (default LLM, launcher), jadi tetap hormati lisensi dan atribusi upstream.
