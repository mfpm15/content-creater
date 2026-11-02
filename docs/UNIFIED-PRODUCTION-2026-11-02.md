# Produksi terpadu dan audit referensi — 2 November 2026

## Remotion sudah masuk Video Studio

Paket sebelumnya adalah Stickman/OpenCreator: memakai protokol workspace, aset gambar/audio dan daemon sendiri. Tidak ada adapter Scene Plan atau pemasangan Remotion pada setup inti. Karena itu launcher preview bukan bukti Video Studio dapat merender dengan Remotion.

Sekarang **Remotion Editorial** tersedia di `/videos` dengan alur yang sama: brief → Scene Plan → approval → Storyboard → approval → render → review → paket produksi. `remotion_adapter.py` mengubah plan menjadi manifest frame 30 fps; komposisi React asli di `apps/video-studio-remotion` merender diagram bergerak dan caption. Tidak memerlukan daemon OpenCreator. Dependency tetap terisolasi dengan lockfile, sesuai arsitektur multi-aplikasi; pengguna memakai satu menu.

- Runtime terkunci: Remotion, bundler dan renderer **4.0.473**, React **18.3.1**, TypeScript **5.7.3**, Node ≥22. `setup-core.bat` memasangnya dengan `npm ci --ignore-scripts`.
- Empat keluarga: `process`, `data`, `comparison`, `concept`. Keluarga lain dipetakan ke concept dan dijelaskan di UI. Data numerik memakai judul yang disetujui terlebih dahulu, lalu narasi jika judul tidak mengandung angka. Tanda minus/plus/desimal dipertahankan; judul 25% dan narasi 25 persen tidak dijadikan dua statistik. Potongan angka dari token mata uang tertempel tidak diekstrak menjadi nilai salah. Tanpa bar/persentase pertumbuhan sintetis. Diagram proses tiga node adalah metafora, bukan ekstraksi otomatis seluruh langkah naskah.
- Kamera/lighting/transisi memakai allowlist yang sama dengan 2D. Warna, font sistem dan wordmark brand diterapkan. Style mengikuti engine; pilihan gaya yang backend tidak gunakan tidak lagi dapat dipilih.
- Audio `music` lokal atau `tts` opsional. Mode audio tersimpan dan bertahan saat edit/resume/varian rasio. Musik tidak membutuhkan provider atau environment TTS. Tidak menerima audio pribadi.
- Caption memakai cue kata pengguna jika tersedia; tanpa cue, seluruh teks dibagi menjadi potongan pendek dan durasinya **diperkirakan**, bukan forced alignment. Tidak mengklaim sinkron kata terhadap suara.
- Manifest wajib menutup seluruh durasi, tanpa gap/overlap, frame integer dan minimal satu frame per shot. Edit tidak mengubah waktu diam-diam. Dua approval/revision tetap berlaku.
- Renderer menghasilkan MP4 H.264, YUV420 limited-range, BT.709, CRF 18; capture PNG sumber lossless. Frame pertama sudah berisi konten. Sampai enam midpoint diambil langsung dari komposisi dan satu dirender ulang untuk memeriksa determinisme.
- Pengukuran DOM memeriksa overlap judul/ilustrasi/caption dan batas aman umum pada frame stabil yang teramati. Tree kalkulator Remotion yang tersembunyi/berukuran nol serta fase masuk/keluar dikecualikan; bukan klaim semua frame/semantik lolos. Temuan mengubah review menjadi needs_attention.
- Paket hasil menyertakan `remotion-timeline.json`, `render-report.json` dan `audio-mastering.json`. Preview HTML menampilkan frame hasil yang sebenarnya.

## Pelajaran FFmpeg dipakai di kedua pipeline video

`audio_mastering.py` menerapkan loudnorm **dua tahap** untuk campuran musik maupun TTS Video Studio. Nilai analisis harus numerik finite; senyap/unmeasurable dipertahankan dengan status eksplisit, bukan dibuat seolah memenuhi target. Suara yang melebihi slot tetap ditolak, tidak dipotong diam-diam. Musik ducking yang sudah ada dipertahankan.

`video_review.py` mengukur audio hasil encode dan menyimpan codec, pixel format, warna, fps serta pemeriksaan per platform melalui `video_delivery.py`. Profil dibaca dari **JSON yang sama dengan Clipper**, `clipper/platform_specs.json`. Status profil terpisah dari pemeriksaan media umum; video horizontal tidak diklaim cocok untuk semua layanan. Profil tersebut bersumber dari referensi, **belum diverifikasi sebagai ketentuan resmi platform**.

Clipper sudah memiliki delivery check, safe-area, mask subtitle dan ekspor dengan normalisasi dua tahap. Bug tambahan diperbaiki: warning loudness/resolusi/unmeasured sekarang menghasilkan `needs_attention`, meskipun format dasar `ok`. Temuan hasil render terakhir tampil pada pemeriksaan Studio. Proyek lama tidak dirender ulang atau ditulis ulang otomatis. Model utama, caption satu bahasa, summary, watermark dan Top 5 tetap dipertahankan.

## Article: temuan → usulan revisi yang siap direview

`article_tools.improvement_plan` menyusun prioritas per bagian dari ledger sumber/sitasi, angka yang belum didukung kutipan, pola bahasa dan paragraf panjang. GET artikel mengembalikan rencana baca saja tanpa panggilan AI atau perubahan dokumen.

Tombol **Usulkan perbaikan bahasa bagian ini** memilih bagian dan menyusun instruksi dari temuan lokal, kemudian memakai jalur proposal yang sudah ada. Model tidak diberi izin menambah fakta. Counter angka/sitasi/kutipan/akronim/negasi, digest revisi, persetujuan, staging/journal dan rollback tetap berlaku. Naskah baru diterapkan setelah pengguna menyetujui. Temuan sumber hanya menjadi tugas pemeriksaan, tidak membuat bukti atau menandai klaim terverifikasi otomatis. Ini triase/editorial, bukan pelatihan ulang model atau fact-check semantik.

## Peta penerapan semua repo katalog

Delapan pin katalog dibaca ulang secara terarah. Hash/file bacaan: [reference-recheck-20261102.json](benchmarks/reference-recheck-20261102.json). Tabel ini membedakan fungsi produk dari kemampuan upstream yang masih di luar cakupan; tidak menjalankan seluruh isi Markdown skill secara otomatis.

| Referensi | Penerapan yang benar-benar aktif | Batas |
| --- | --- | --- |
| ffmpeg-skill | `delivery.py`, `platform_export.py`, `caption_geometry.py`; kini juga `audio_mastering.py`/`video_delivery.py` dan review Video Studio | Belum seluruh detektor black/freeze/flash/dropout upstream; hold yang disengaja memerlukan konteks |
| ghost-editor | Review retake dengan approval, hook, self-check audio/delivery/layout dan temuan sebelum ekspor | Take terakhir bukan bukti take audio terbaik; tidak mengimpor seluruh style/B-roll |
| claude-shorts | Framing wajah, snap hening opt-in, cursor eksperimental, word-boundary preflight | Bukan forced alignment; cursor/threshold memerlukan benchmark pengguna |
| openmontage | Prinsip storyboard gate, checkpoint dan pemeriksaan hasil dalam implementasi asli | **AGPL: ide saja**; tidak menyalin kode/aset/700+ skill atau mengklaim semua pipeline tersedia |
| animate | Grammar storyboard, seed/waktu absolut, Continuous Motion, clock GSAP/Three.js dan renderer Remotion asli | Bukan seluruh library/style/kit upstream |
| handy | `faster-whisper` memakai `word_timestamps=True` dan `vad_filter=True`, yang sudah ada sebelumnya | Tidak menanam seluruh aplikasi Handy atau menjamin model sudah terunduh |
| agent-reach | Antarmuka REST/CLI/MCP dan pembacaan sumber allowlist milik proyek | Tidak mengaktifkan semua konektor/akun platform Agent Reach |
| youtube-automation-agent | Approval/resume, analytics, evidence ledger dan triase/revisi artikel | Tidak ada auto-publish sosial tanpa review atau credential pengguna |

Referensi tambahan tetap relevan: Whisper/PySceneDetect untuk invariant/benchmark; **OneTake** untuk waktu absolut, carry/hold dan pemeriksaan frame. OneTake **PolyForm Noncommercial**, dipakai sebagai prinsip tanpa menyalin library/template/aset. GSAP/Three.js/HyperFrames tetap memakai adapter yang telah diuji; Remotion kini adapter tambahan yang nyata. Remotion memiliki Free/Company License dengan kondisi entitas/penggunaan; pemasangan SDK bukan penetapan bahwa semua pemakaian bebas syarat.

## Bukti verifikasi

- **134 tes dashboard lulus**, **227 tes Clipper lulus**, compile Python, Ruff F/E9, sintaks JavaScript, typecheck komposisi Remotion dan suite validator timeline Node lulus.
- Uji pipeline offline memakai dua approval, MP4 + AAC nyata, loudnorm dua tahap, review, varian rasio dan paket produksi. Tanpa model/riset/TTS jaringan.
- Empat render nyata: 9:16 **1080×1920**, 16:9 640×360, 1:1 480×480, 4:5 480×600. Masing-masing 2 detik, **60 frame terdekode**, H.264/YUV420/BT.709; audio −14 LUFS, true peak −4.4 dBFS, frame pertama tidak flat, repeat frame identik, tanpa temuan pada 20 observasi layout stabil per kasus. [Bukti dan hash source/frame](benchmarks/remotion-studio-20261102.json).
- Smoke UI fixture: lima engine, plan tidak berubah saat dibuka, kontrol Remotion terkumpul, peringatan artikel tampil, tombol usulan satu klik menghasilkan proposal yang tetap menunggu approval, teks HTML tidak dieksekusi. HTTP dashboard/redaksi dan health/Top 5 Clipper lulus. Tidak memutar media.
- Benchmark tersebut memakai Chromium/software rendering Linux dan naskah sintetis pendek; bukan klaim kualitas cerita, GPU laptop, rendering panjang, transkripsi/video nyata baru, atau provider TTS daring. CI native Windows final [41431931788](https://github.com/mfpm15/content-creater/actions/runs/41431931788) (**7fc4dcb**) dan Clipper [41430689180](https://github.com/mfpm15/content-creater/actions/runs/41430689180) (**530f809**) keduanya **Success**. Gate Windows mewajibkan runtime tersedia sebelum tes, sehingga pipeline Remotion tidak dapat dilewati hanya karena dependency/browser hilang. Kode Clipper identik sejak commit yang diuji tersebut.

Keamanan: props JSON privat/temporer, ukuran dibatasi dan divalidasi dua lapis, teks React di-escape, warna/font/preset di-allowlist, tidak menerima script/asset URL, browser terpasang wajib dipakai dan download browser otomatis ditolak. Worker menerima argumen tetap tanpa shell, memakai environment renderer yang disaring serta cleanup/timeout proses. Tidak mengubah auth/Host/Origin, tidak menambahkan credential atau pengelola antrean baru. Worker Stickman/OpenCreator tidak dibuka sebagai endpoint baru.

## Mencoba di Windows dari GitHub

Tutup aplikasi, lalu jalankan `git pull --ff-only`, `setup-core.bat`, `start-dashboard.bat`. Setup perlu dijalankan lagi karena ada dependency Remotion baru. Buka **Video Studio → Remotion Editorial → Naskah sendiri → Musik/foley lokal** untuk uji tanpa provider. Tinjau Scene Plan dan Storyboard, setujui keduanya, lalu periksa frame, laporan media dan MP4 hasil. TTS opsional memerlukan akses layanan suara yang sudah digunakan proyek.

Implementasi utama `530f809` lulus [Windows 41430689110](https://github.com/mfpm15/content-creater/actions/runs/41430689110) dan [Clipper 41430689180](https://github.com/mfpm15/content-creater/actions/runs/41430689180), keduanya **Success**. Koreksi label metrik `d934aca` dan gate runtime `7fc4dcb` juga lulus CI native Windows final **41431931788**, termasuk encode Remotion nyata dan launcher dari path berspasi. Regresi lokal akhir: 134 tes dashboard dan empat render ulang. Kode Clipper tidak berubah pada koreksi tersebut.
