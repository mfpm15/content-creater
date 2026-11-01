# Plan terpadu: 4 produk fokus × 8 repo referensi

> Rencana awal/historis. Status implementasi terbaru dan keterbatasannya ada di [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md).

Dibuat 31 Oktober 2026 setelah membaca kode keempat produk dan isi dalam repo referensi (bukan hanya README).
Menggantikan bagian "Tidak ada perubahan" di [plan-referensi-2026-10.md](../clippercuan/docs/plan-referensi-2026-10.md), yang terlalu longgar.

Baseline sebelum perubahan berikutnya: ClipperCuan `pytest` 138 lulus; dashboard: `test_article_drafter`, `test_youtube_analytics` (4), `test_video_drafter` (22), `test_dashboard` lulus.

Prasyarat yang belum terpenuhi di mesin ini (diperiksa, bukan diasumsikan):
- `GEMINI_API_KEY` / `GOOGLE_API_KEY` tidak terset di shell. Riset web Google Search (Video Studio) wajib kunci ini, dan jalur yang sama dipakai Article Drafter.
- Belum ada contoh ekspor analitik Instagram Reels / TikTok. Nama kolom tidak boleh ditebak.

Status: ✅ sudah ada · 🔧 ada, perlu ditingkatkan · ➕ belum ada · ⛔ butuh masukan pengguna

---

## 1. ClipperCuan (prioritas 1: sumber uang)

| Ide (repo) | Status | Tindakan |
|---|---|---|
| Cek hasil per platform: rasio, durasi, audio, loudness (ffmpeg-skill, claude-shorts) | ✅ `delivery.py` | Angka diselaraskan dengan `_platforms.py` ffmpeg-skill: Reels 90 dtk, Shorts 180, TikTok 600; resolusi dibanding sisi pendek |
| Zona aman UI per platform untuk caption (ffmpeg-skill `safe`, claude-shorts platform-specs) | ➕ | Tambah ke `delivery.py` + validasi posisi caption terhadap zona aman. TikTok bawah 22 %, kanan 14 %; Reels 20 % / 12 %; Shorts 18 % / 12 % |
| Rapikan batas klip ke jeda hening setelah batas kalimat (claude-shorts `snap_boundaries.py`) | 🔧 `snap_boundary` hanya ke batas kalimat | Tambah `silencedetect`; diuji dengan benchmark `CAPTION_BENCHMARK` agar ranking tidak bergeser |
| Cursor tracking untuk rekaman layar (claude-shorts) | ➕ | Frame differencing di `facetrack.py`; hanya aktif untuk profil screen |
| Hook archetype + booster angka/entitas/pengalaman pribadi (claude-shorts rubrik) | 🔧 `_hook_score` sederhana | Perluas penilaian hook; teks hook overlay 2 baris yang melengkapi, bukan menduplikasi ucapan awal |
| Pilih take terbaik bila pembicara mengulang kalimat (ghost-editor) | ➕ | Deteksi pengulangan dekat → pilih take terakhir/terbersih. Hanya untuk talking head |
| Ekspor per platform lewat preset encoder (claude-shorts, ffmpeg-skill) | 🔧 satu render untuk semua | Opsi ekspor bitrate/loudness per platform; `delivery.check` dipakai sebagai gerbang akhir |
| Uji end-to-end dengan video nyata | ⛔ belum pernah | Satu-satunya cara jujur membuktikan "tidak ada bug". Langkah pertama sebelum fitur baru |

## 2. Video Studio (Opuscar / Three.js / Lottie)

| Ide (repo) | Status | Tindakan |
|---|---|---|
| Alur gerbang persetujuan: brief → rencana adegan → storyboard → render (animate, openmontage) | ✅ | Tidak diubah |
| Riset web terverifikasi sebelum menulis (openmontage, youtube-automation-agent) | ✅ kode ada, ⛔ kunci tidak ada | Pengguna isi `GEMINI_API_KEY`; saya tambah cek kesiapan yang menjelaskan alasan jelas |
| Review terukur setelah render: potongan jatuh di beat, ledakan suara setelah hening, kecepatan narasi, teks terpotong (animate `review.mjs`, ghost-editor self-check) | ➕ | Modul review pasca-render untuk MP4 hasil; memakai `ffprobe`/`ebur128` seperti `delivery.py` |
| Ekspor banyak rasio dari satu karya: 9:16, 1:1, 4:5, 16:9 (animate) | 🔧 satu rasio per render | Render ulang per rasio dari rencana adegan yang sama |
| Penanda beat musik; potong tepat beat (animate `beats.mjs`) | ➕ | Setelah review pasca-render stabil |
| Waktu gambar mengikuti kata narasi (animate `voice.mjs`, faster-whisper) | ➕ | Setelah review pasca-render stabil |
| Analisis video referensi: tempo, hook, struktur ("buat seperti ini") (openmontage, ghost-editor) | ➕ | Pakai `facetrack`/transkrip ClipperCuan; pekerjaan besar, tahap akhir |
| Perkiraan biaya sebelum menghasilkan aset (openmontage) | ⛔ | Tidak relevan selama semua renderer lokal dan gratis |

## 3. Article Drafter

| Ide (repo) | Status | Tindakan |
|---|---|---|
| Riset berita terbaru dengan sumber tervalidasi | ➕ Drafter hanya memakai poin dan sumber dari pengguna | Tahap "riset" baru memakai `google_search_research.py` yang sudah ada (butuh kunci). Hasil: sumber berperingkat (resmi / institusi / media / web), tanggal terbit, ditolak bila tanpa URL atau lebih tua dari batas kesegaran |
| Bahasa "humanizer" | ✅ linter lokal (`humanizer.py`, 31 Okt 2026) tampil di hasil artikel; ➕ putaran tulis ulang | Linter mendeteksi klise, ritme kalimat seragam, awalan berulang, penghubung formal, tanda pisah, pola "bukan sekadar X, melainkan Y". Dikalibrasi pada 2 artikel nyata 9Router (skor 90 dan 78). Hanya melapor, tidak mengubah teks. Belum dibuat: putaran tulis ulang LLM berdasar temuan. `humanizerai.com` butuh kunci dan mengirim teks keluar; tidak dipakai kecuali Anda minta |
| Baca halaman web / transkrip video sebagai sumber (agent-reach) | ➕ | Hanya bila perlu: fetch halaman publik + transkrip YouTube yang sudah ada di `clippercuan/asr.py` |
| Claim ↔ sumber (Evidence desk, youtube-automation-agent) | ✅ sebagian: sitasi `[n]` divalidasi, `[PERLU VERIFIKASI]` | Tambah laporan klaim tak bersumber di hasil akhir |

## 4. Analytics: YouTube, Instagram Reels, TikTok

| Ide (repo) | Status | Tindakan |
|---|---|---|
| Retensi YouTube, lint judul/thumbnail, review hook | ✅ | Tidak diubah |
| Retensi per adegan (youtube-automation-agent) | 🔧 retensi dicocokkan ke SRT | Kelompokkan cliff per adegan/bagian dari skrip |
| Analitik Reels / TikTok | ➕ | ⛔ Perlu contoh ekspor CSV asli dari Instagram Insights dan TikTok Studio. Tanpa itu pemetaan kolom adalah tebakan. Rancangan: pemeta kolom fleksibel, kolom tak dikenal ditampilkan, bukan diabaikan |
| Loop belajar 24 jam / 7 hari dengan persetujuan pengguna (youtube-automation-agent) | ➕ | Setelah ada data Reels/TikTok |

---

## Urutan kerja

1. ClipperCuan: uji end-to-end dengan video nyata, perbaiki bug yang muncul.
2. ClipperCuan: zona aman caption, snap hening, hook archetype, ekspor per platform.
3. Article Drafter: tahap riset + linter humanizer (linter lokal bisa dikerjakan tanpa kunci).
4. Analytics: retensi per adegan; Reels/TikTok setelah contoh ekspor ada.
5. Video Studio: review pasca-render, lalu multi-rasio.

Aturan: satu irisan per langkah, tes ditulis bersama kode, seluruh suite dijalankan sebelum lanjut, angka platform dinyatakan sumbernya.
