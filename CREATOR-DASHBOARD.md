 # Creator Control Center

Dashboard lokal ini menjadi pintu masuk untuk lima repository yang sekarang tersusun di `creator-dashboard\apps`:

- **MoneyPrinterTurbo** untuk membuat video faceless dari topik.
- **OpenCreator** untuk workspace kreator dan workflow berbasis Agent.
- **Remotion Studio** untuk video editor visual berbasis React (timeline, preview, layer dragging).
- **HyperFrames Studio** untuk HTML-native video editor & renderer (seekable GSAP timeline, no build step).
- **Lemo-Opuscar Studio** untuk katalog 59 preset gaya film prosedural (Canvas/WebGL + foley audio).
- **Short Video Factory** untuk editor desktop, template, dan finishing.
- **Podcastfy** untuk mengubah sumber menjadi podcast berbentuk percakapan.
- **AI YouTube Shorts Generator** untuk memotong video panjang menjadi highlight vertikal.
- **Clipper Cuan** untuk klip vertikal lokal, subtitle, smart crop, dan pemilihan momen memakai 9Router opsional.

Dashboard berjalan hanya di `127.0.0.1:3210`. Dashboard tidak mengirimkan API key atau file media ke service lain. Provider yang dikonfigurasi di masing-masing tool tetap dapat mengirim data ke penyedia AI sesuai pengaturannya.

## Quick start

### 1. Setup dependensi

Klik dua kali:

```bat
setup-dashboard.bat
```

Setup ini menjalankan:

- `uv sync --frozen` untuk MoneyPrinterTurbo;
- virtual environment Python 3.11 untuk Podcastfy, instalasi editable dari `pyproject.toml`, serta dependency API `FastAPI 0.103.0`, `Uvicorn 0.23.2`, `PyYAML 6.0.2`, dan `Playwright`; jalur ini digunakan karena `requirements.txt` upstream mengandung pin lama yang tidak dapat diselesaikan secara konsisten dan dependency API maupun ekstraktor situs belum tercantum lengkap dalam dependency utama proyek;
- virtual environment Python 3.11 untuk AI YouTube Shorts Generator;
- `corepack pnpm install --frozen-lockfile` untuk OpenCreator dan Short Video Factory. Setup tidak menjalankan `corepack enable`, sehingga tetap dapat digunakan oleh akun Windows non-administrator saat Node.js terpasang di `C:\Program Files\nodejs`.

Python sistem saat inventarisasi adalah 3.14.6. Repository Python tersebut ditargetkan ke Python 3.10/3.11, sehingga setup menggunakan lingkungan Python 3.11 terpisah melalui `uv`.

### 2. Jalankan dashboard

Klik dua kali:

```bat
start-dashboard.bat
```

Browser akan membuka:

```text
http://127.0.0.1:3210
```

Menutup terminal dashboard dengan `Ctrl+C` juga menghentikan proses yang diluncurkan dashboard.

## Port default

```text
Creator Control Center        3210
MoneyPrinterTurbo WebUI       8501
Podcastfy API                 8080
OpenCreator Web              19861
Remotion Studio               3300
HyperFrames Studio            4000
Lemo-Opuscar Studio           3500
Clipper Cuan                  8765
9Router                       20128
```

Short Video Factory berjalan sebagai aplikasi Electron, bukan service web. Statusnya dinilai dari process tree yang dikelola dashboard, bukan dari port HTTP. AI YouTube Shorts Generator adalah CLI pipeline, sehingga dashboard menyediakan command yang dapat disalin.

## Cara menggunakan setiap kartu

- **Jalankan** memulai proses tool di background.
- **Buka** membuka WebUI atau dokumentasi API setelah service siap.
- **Stop** menghentikan process tree yang dimulai dashboard.
- **Log** menampilkan output proses untuk troubleshooting.
- Status diperbarui setiap lima detik.

Dashboard hanya memakai konfigurasi tool yang diizinkan di `creator-dashboard/tools.json`. Browser tidak dapat mengirim command arbitrer ke shell.

## Konfigurasi API key

Setiap project tetap menggunakan konfigurasi aslinya. Dashboard dan Clipper Cuan memakai fallback environment bersama: `LLM_BASE_URL` lalu `OPENAI_BASE_URL`, `LLM_API_KEY` lalu `OPENAI_API_KEY`, serta `LLM_MODEL` lalu `OPENAI_MODEL`. Default lokal: `http://localhost:20128/v1` dan `ag/gemini-3.8-flash-medium`. API key diwariskan hanya ke proses backend dan tidak dikirim lewat HTML, JavaScript, katalog tool, atau API publik.

Contoh tersedia di `.env.example`. Jangan commit `.env`. Set environment Windows sebelum menjalankan dashboard:

```bat
set LLM_BASE_URL=http://localhost:20128/v1
set LLM_API_KEY=isi_secret_lokal
set LLM_MODEL=ag/gemini-3.8-flash-medium
start-dashboard.bat
```

### Clipper Cuan

Setup venv terisolasi sekali lewat `clippercuan\app\start.bat`, lalu hentikan service awal bila perlu. Setelah itu kartu dashboard menjalankan `.venv\Scripts\python.exe` dengan working directory `clippercuan\app` pada `http://127.0.0.1:8765`. Health endpoint: `/api/health`; OpenAPI: `/docs`.

### MoneyPrinterTurbo

Salin konfigurasi contoh sebelum pemakaian pertama bila `config.toml` belum tersedia:

```bat
copy creator-dashboard\apps\moneyprinterturbo\config.example.toml creator-dashboard\apps\moneyprinterturbo\config.toml
```

Kemudian isi provider LLM, TTS, Pexels, atau provider lain yang benar-benar akan digunakan. Jangan commit `config.toml` jika berisi secret.

### Podcastfy

Buat `creator-dashboard\apps\podcastfy\.env` dan isi hanya provider yang digunakan, misalnya:

```dotenv
OPENAI_API_KEY=
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
```

Podcastfy API tersedia di `http://127.0.0.1:8080/docs` setelah dijalankan.

### AI YouTube Shorts Generator

Salin file contoh:

```bat
copy creator-dashboard\apps\ai-youtube-shorts-generator\.env.example creator-dashboard\apps\ai-youtube-shorts-generator\.env
```

Untuk mode API isi `MUAPI_API_KEY`. Untuk mode lokal dengan 9Router, isi `OPENAI_API_KEY`, `OPENAI_BASE_URL`, dan `OPENAI_MODEL`. Model default disiapkan sebagai `ag/gemini-3.8-flash-medium`; ganti ke `ag/gemini-3.8-flash-high` bila membutuhkan penilaian highlight yang lebih teliti. Nilai Base URL harus memakai endpoint OpenAI-compatible yang diberikan 9Router. Setelah itu install dependensi local mode:

```bat
uv pip install --python creator-dashboard\apps\ai-youtube-shorts-generator\.venv\Scripts\python.exe -r creator-dashboard\apps\ai-youtube-shorts-generator\requirements-local.txt
```

Contoh eksekusi mode lokal:

```bat
cd creator-dashboard\apps\ai-youtube-shorts-generator
.venv\Scripts\python.exe main.py "C:\Videos\input.mp4" --mode local --num-clips 3 --output-json result.json
```

### OpenCreator

OpenCreator memerlukan Node.js 22+ dan pnpm 9.15 melalui Corepack. Launcher dashboard membuat katalog template terlebih dahulu, membangun package workspace yang diperlukan, kemudian menjalankan Vite langsung pada `127.0.0.1:19861`. Cara ini sengaja melewati `predev` desktop yang membutuhkan compiler Go untuk KrillinAI.

Untuk model teks melalui endpoint OpenAI-compatible 9Router, buka **Settings > AI services** di OpenCreator dan isi Base URL 9Router, API key, serta salah satu model berikut:

```text
ag/gemini-3.8-flash-high
ag/gemini-3.8-flash-medium
```

Gunakan `ag/gemini-3.8-flash-high` untuk perencanaan atau penilaian yang membutuhkan kualitas lebih tinggi, dan `ag/gemini-3.8-flash-medium` untuk draft cepat serta volume lebih besar. Base URL dan API key tidak disimpan di `creator-dashboard/tools.json` agar secret tidak bocor melalui konfigurasi launcher.

### Short Video Factory

Tool ini memerlukan Node.js minimal 22.17 dan pnpm 10.12.4. Launcher menghapus `ELECTRON_RUN_AS_NODE` sebelum menjalankan aplikasi agar executable Electron benar-benar membuka desktop window. Peringatan Metadata API tidak menghentikan aplikasi karena repository memiliki snapshot terverifikasi dan fallback GitHub.

Pada konfigurasi LLM Short Video Factory pilih protokol **OpenAI Compatible**, masukkan Base URL dan API key 9Router, lalu gunakan `ag/gemini-3.8-flash-high` atau `ag/gemini-3.8-flash-medium` sebagai nama model.

## Troubleshooting

### Status berhenti setelah tombol Jalankan

Buka **Log** pada kartu terkait. Penyebab umum:

- dependensi belum di-install;
- versi Python tidak cocok;
- API key atau konfigurasi wajib belum tersedia;
- port sedang digunakan proses lain;
- FFmpeg tidak tersedia di `PATH`;
- Corepack belum memiliki versi pnpm yang diminta repository.

### Port sudah digunakan

Periksa process pemilik port:

```bat
netstat -ano | findstr ":8501 :8080 :19861 :3210"
```

Hentikan proses hanya jika Anda mengenal PID tersebut:

```bat
taskkill /PID 12345 /T /F
```

### FFmpeg tidak ditemukan

Pastikan perintah berikut berhasil:

```bat
ffmpeg -version
```

Jika tidak, install FFmpeg dan tambahkan direktori `bin` ke PATH pengguna Windows.

### Dashboard tidak otomatis membuka browser

Buka manual:

```text
http://127.0.0.1:3210
```

### Menambah tool baru

Tambahkan entri ke `creator-dashboard/tools.json`. Gunakan command dalam bentuk array, direktori harus tetap berada di workspace, dan service web harus menggunakan loopback `127.0.0.1`. Restart dashboard setelah mengubah konfigurasi.

## Batas integrasi saat ini

Dashboard ini adalah **control center/launcher**, bukan penggabungan source code kelima aplikasi menjadi satu runtime. Setiap tool tetap mempertahankan dependency, konfigurasi, storage, lisensi, dan UI masing-masing. Pendekatan ini sengaja dipilih agar upgrade upstream lebih aman dan konflik dependency Python, Node.js, Electron, MoviePy, serta FFmpeg tidak bercampur dalam satu process.
