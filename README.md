# Content Creator Control Center

## Instalasi Windows langsung dari GitHub

Tidak perlu ZIP atau ekstraksi. Setelah Git, uv, Node.js 22+, FFmpeg/FFprobe dan Chrome/Edge tersedia, jalankan dari Command Prompt:

```bat
git clone https://github.com/mfpm15/content-creater.git
cd content-creater
setup-core.bat
start-dashboard.bat
```

Untuk memperbarui, tutup aplikasi terlebih dahulu, lalu jalankan `git pull --ff-only`, `setup-core.bat`, dan `start-dashboard.bat`. Jika Git melaporkan konflik/perubahan lokal, pertahankan perubahan tersebut; jangan memakai `git reset --hard` atau menghapus `.data`, `output`, maupun credential lokal. ZIP di bagian lain hanya alternatif distribusi.

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
| AI YouTube Shorts Generator | Potong video panjang menjadi Shorts dengan highlight dari LLM | CLI | dijalankan manual |

Dashboard sendiri berjalan di http://127.0.0.1:3210. Dari sana tiap tool bisa di-start, di-stop, dicek status kesiapannya, dan dilihat lognya.

**Article Drafter** (menu di sidebar, http://127.0.0.1:3210/articles.html): isi poin draft, hasilkan artikel `.md` dan `.docx` lewat 9Router, plus prompt gambar siap tempel ke Nano Banana atau ChatGPT. Gambar hasilnya diunggah balik dan dokumen dibangun ulang dengan gambar tertanam. Tanpa dependensi tambahan. Hasil tersimpan di `creator-dashboard/output/articles/` (tidak masuk git).

- **Panjang:** 200 sampai 30.000 kata. Artikel panjang ditulis bertahap (kerangka, daftar pustaka, tiap bagian 3 paralel, prompt gambar) dengan bilah progres. Bila gagal di tengah, bagian yang sudah jadi tersimpan dan tombol Lanjutkan hanya menulis sisanya. Uji nyata: 15.108 kata dalam sekitar 8 menit.
- **Struktur baku** menurut jenis artikel: analisis/white paper, IMRaD, laporan, populer, tutorial. Artikel bernomor memakai abstrak, kata kunci, daftar isi (di atas ±3.000 kata), penomoran 1., 1.1, kesimpulan, dan daftar pustaka. Nomor halaman ada di Word.
- **Sumber rujukan:** isi kolom Sumber, lalu sistem membuat Daftar Pustaka gaya IEEE dan sitasi `[n]` di teks. Sitasi ke nomor yang tidak ada diganti `[PERLU VERIFIKASI]`. Opsi "Sarankan rujukan tambahan" menaruh saran AI di bagian terpisah bertanda belum diverifikasi.
- **Gaya visual:** pilih satu dari 13 gaya, atau Acak (tiap gambar beda gaya).

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
| OpenCreator, Short Video Factory | default LLM ada di source (`creator-services.ts`, `src/lib/llm/config.ts`), ubah di UI tiap tool |

Jangan commit API key.

## Catatan

- Generasi gambar/video (Nano Banana, Veo) belum terpasang. Gateway 9Router belum punya provider gambar, dan MoneyPrinterTurbo belum punya adapter Google native.
- OpenCreator menjalankan build paket terlebih dahulu sebelum Vite, jadi start pertama lebih lama.
- Dashboard hanya menjalankan perintah yang tertulis di `tools.json`, tidak menerima perintah dari browser. Biarkan terikat ke `127.0.0.1`.
- Font macOS besar (`STHeiti*.ttc`) tidak ikut di repo.

## Lisensi

Kode dashboard di `creator-dashboard/` (kecuali `apps/`) milik pemilik repo ini. Setiap tool di `creator-dashboard/apps/` memakai lisensi aslinya, lihat file `LICENSE` dan README di folder masing-masing. Source tool sudah dimodifikasi lokal (default LLM, launcher), jadi tetap hormati lisensi dan atribusi upstream.


## Verifikasi laptop setelah setup

Dari Command Prompt di folder proyek, jalankan `check-local.bat` setelah `setup-core.bat`.
Pemeriksaan ini menguji import dependency dashboard/Clipper, Node 22+, FFmpeg/FFprobe,
libass, encoder H.264/AAC, loudnorm, browser dan runtime Remotion tanpa memanggil provider.
Status credential hanya menunjukkan konfigurasi, bukan keberhasilan koneksi.

Riset Article dan Video Studio memakai SDK Google di venv dashboard, yang dipasang setup inti.
Tidak perlu memasang Podcastfy untuk riset. Mode `RESEARCH_PROVIDER=google` memerlukan `GOOGLE_API_KEY` atau `GEMINI_API_KEY`. Mode `9router` memakai endpoint/key LLM aplikasi dan katalog Search gateway. Mode `auto` memilih Google bila key Google tersedia, selain itu 9Router.
Permintaan riset web tanpa konfigurasi ditolak; pilih mode lain secara eksplisit bila ingin bekerja offline.
Setelah pemeriksaan lulus, coba Video Studio dengan naskah sendiri + musik lokal, lalu periksa
MP4/PNG review; coba Article dengan gateway LLM aktif; coba Clipper memakai video pendek lokal.
Whisper dapat memerlukan unduhan model pertama kali. Pemeriksaan dependency tidak menggantikan
pengujian suara/provider, GPU dan hasil konten di perangkat pengguna.


Untuk 9Router lokal: jalankan `check-search.bat` untuk melihat katalog Search yang benar-benar tersedia.
Jika ada beberapa pilihan, set `RESEARCH_SEARCH_MODEL` ke id dari katalog lalu restart dashboard.
`check-search.bat --query "dokumentasi FFmpeg loudnorm"` menguji pencarian nyata.
Katalog kosong berarti provider Search belum tersedia/diizinkan di gateway, walaupun model chat bisa dipakai.
Gunakan `RESEARCH_PROVIDER=9router` untuk memilih jalur gateway secara eksplisit.
Artikel memakai `ARTICLE_LLM_*`, video memakai `VIDEO_LLM_*`, keduanya fallback ke `LLM_*`/`OPENAI_*`.
Jangan tempel API key di perintah atau laporan yang dibagikan.
