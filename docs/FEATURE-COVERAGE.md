# Cakupan pengembangan dan batas validasi

Diperbarui 1 November 2026. Dokumen ini mencatat kemampuan proyek, bukan klaim kesetaraan dengan produk lain.

## Referensi produk dari pengguna

| URL | Status pemeriksaan |
|---|---|
| https://socialvisuals.pro/ | Halaman belum dapat dibaca; proxy cloud mengembalikan 403 |
| https://reap.video/clipping | Sama |
| https://www.opus.pro/ | Sama |
| https://www.heygen.com/id-id/tool/ai-video-clip-generator | Sama |
| https://creatify.ai/id/tools/ai-video-clip-generator | Sama |
| https://www.vmaker.com/tools/ai-clip-maker | Sama |

Draft allowlist enam host sudah disimpan pada konfigurasi environment; belum diterapkan ke instance berjalan. Jangan mengatribusikan fitur spesifik ke produk tersebut tanpa membaca sumbernya. Tidak ada kode, aset, merek, atau model milik produk tersebut yang disalin. Rincian delapan repo pengetahuan ada di [REFERENCES.md](REFERENCES.md).

## Kemampuan yang tersedia

| Area | Implementasi | Batasnya |
|---|---|---|
| Video panjang → klip | Kandidat, pemeringkatan lokal/LLM opsional, editor, caption, framing, antrean | Skor editorial bukan prediksi viralitas |
| Caption dan istilah | Track editorial, glossary, revision guard, ASS/SRT dan rerender | Transkrip sumber tetap bisa salah; jangan mengganti nama/angka otomatis |
| Batas klip | Snap hening opt-in pada audio lokal yang sudah tersedia, cache hash, invariant kata/durasi | Mode hemat disk tidak mengunduh audio penuh untuk fitur ini |
| Take berulang | Review dua teks dan waktunya; penghapusan hanya pengulangan persis + konfirmasi talking-head, stale revision ditolak | Take terakhir bukan bukti suara terbaik; fuzzy hanya saran manual |
| Framing pembicara | Pergantian dominasi mulut stabil dalam satu shot dengan gate energi audio | Heuristik, bukan identitas/diarization; fallback dua panel; perlu benchmark nyata |
| Rekaman layar | Profil manual `screen_recording`, cursor heuristic, smoothing dan blur fallback | Eksperimental, portrait saja; diuji sintetis |
| Delivery per platform | Preset bersama, overlay, antrean H.264/AAC/loudness dua tahap, hash dan unduhan tervalidasi | Profil referensi, bukan ketentuan resmi terbaru; jalur unduh mentah tetap ada |
| Zona aman teks | Mask libass semua frame, termasuk caption, title, CTA dan watermark teks pada ekspor | Teks bawaan video, watermark gambar/dekorasi tidak diukur; mask tidak aman memblokir ekspor |
| Analisis referensi lokal | Sampel 1–120 detik, scene cuts, median shot, tempo ucapan, pembuka dan jeda transkrip | Tidak menilai struktur semantik, fakta, atau estetika; tidak menyalin gaya otomatis |
| Video Studio | Gerbang Scene Plan/Storyboard, resume, variasi 9:16/1:1/4:5/16:9 dari satu rencana | Tiap rasio direview ulang; MP4 memerlukan runtime HyperFrames/Opuscar/TTS yang siap |
| Lottie | Data ekspor sama dengan sumber preview mandiri, teks aman, bentuk dan transform dasar | Subset vektor sederhana, tanpa audio/3D/aset eksternal; bukan seluruh Motion Plan |
| Review video | ffprobe, loudness/true peak/silence, estimasi kecepatan narasi, delta cut ke grid envelope musik prosedural | Bukan deteksi beat musik eksternal atau timestamp per kata; timing disetujui tidak otomatis diubah |
| Review visual | Screenshot midpoint maksimal 20 adegan dan cek overflow elemen teks | Opsional Playwright/browser; bukan review semua frame/transisi/estetika; `unmeasured` bila tidak siap |
| Artikel | Riset opsional, ledger sumber/kutipan/tanggal, kaitan paragraf–sumber, freshness, revisi bagian dengan persetujuan dan backup | Status sumber adalah attestation pengguna, bukan fact-check otomatis; perubahan nama/makna tetap wajib direview |
| Diagram artikel | Flow berurutan/mind map satu tingkat → SVG+PNG lokal → DOCX | Pillow opsional; bukan renderer Mermaid umum |
| Analytics | Pemetaan kolom CSV eksplisit, kolom tak terpakai dilaporkan, retensi per scene, observasi 24h/7d + approval eksperimen | CSV asli Reels/TikTok ditunda pengguna; schema native belum diverifikasi; tidak auto-publish |

## Konfigurasi dan keamanan

- Dashboard tetap loopback, semua mutasi memeriksa Host/Origin. Clipper mempertahankan auth token, exact origin, validasi path dan antrean.
- `creator-dashboard/requirements-review.txt` hanya dependency opsional diagram/review. Browser Chromium harus tersedia terpisah. Sandbox browser aktif secara default; `VIDEO_REVIEW_ALLOW_NO_SANDBOX=1` hanya untuk lingkungan uji terisolasi yang memang tidak mendukung sandbox.
- Review visual memakai server loopback sementara, request browser dibatasi ke folder render dan CDN runtime yang digunakan template. Tidak memakai profil browser pengguna atau credential backend.
- `RESEARCH_SOURCE_HOSTS` mengizinkan host HTTPS publik secara eksplisit (pisah koma). Default kosong, tidak fetch. Tidak meneruskan token backend, tidak mengikuti redirect, menolak IP privat, port nonstandar, URL credential/query credential dan badan >1 MB. Allowlist ini untuk situs yang dipercaya, bukan crawler umum yang menjamin perlindungan terhadap DNS rebinding di seluruh proxy.
- API key hanya di konfigurasi backend/secret environment. Jangan mengirim nilainya lewat chat, dokumen, CSV, URL sumber, atau commit.
- Usulan revisi, backup, ledger bukti dan observasi disimpan atomik mode privat 0600. Data lokal/output tidak masuk Git.
- Varian ekspor lama yang hanya mengukur spoken caption perlu diekspor ulang untuk memenuhi cakupan seluruh teks ASS; unduhan tervalidasi menolak metadata pemeriksaan lama.

## Pekerjaan yang masih memerlukan tahap berikutnya

1. Benchmark video nyata untuk cursor, speaker-turn, crossfade dan snap hening; CSV ekspor asli setelah pengguna siap.
2. Timestamp narasi per kata dan gerak visual yang mengikutinya; belum ada model alignment siap yang tervalidasi.
3. Deteksi beat musik eksternal, transient setelah hening, serta review seluruh frame/rendered pixel termasuk elemen visual nonteks.
4. Analisis semantik hook/payoff referensi dan style proposal dengan review; tidak menganggap statistik cuts sebagai pemahaman cerita.
5. Verifikasi fitur keenam situs setelah akses tersedia, kemudian petakan gap faktual. Avatar, dubbing/terjemahan, generative B-roll, integrasi publishing/scheduler bukan fitur yang sudah selesai dalam perubahan ini.
6. Uji provider nyata dan MP4 penuh dengan runtime render/TTS siap; pengujian lokal tidak membuktikan akun/provider eksternal berfungsi.
