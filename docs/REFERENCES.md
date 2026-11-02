# Repo Referensi

Delapan repo dipelajari pada 31 Oktober 2026 untuk ClipperCuan dan dashboard. Salinan lokal ada di `references/` (root repo), **tidak ikut Git** (292 MB, tiap repo membawa `.git` sendiri; lihat `.gitignore`). Dokumen ini yang ikut Git: daftar, versi, lisensi, apa yang dipelajari, apa yang dipakai.

Aturan pakai:
- Referensi **dibaca**, bukan dependency. Tidak ada kode yang disalin; hanya ide, angka, dan alur kerja. Jangan impor dari `references/`.
- `openmontage` berlisensi **AGPL-3.0**. Jangan salin kode atau aset dari repo itu ke proyek ini. Ide dan alur kerja saja.
- Tujuh repo lain berlisensi MIT. Bila nanti ada kode yang benar-benar disalin, cantumkan atribusi dan lisensinya di berkas yang menerimanya.
- Angka yang diambil dari referensi harus tetap diuji pada video nyata (lihat kolom "Dipakai").

## Katalog

| Folder | Sumber | Commit | Lisensi | Terakhir diubah upstream |
|---|---|---|---|---|
| `references/ffmpeg-skill` | https://github.com/kajisho5/ffmpeg-skill | `a2c8433` | MIT | 2026-10-31 |
| `references/ghost-editor` | https://github.com/kurbaitaev/ghost-editor | `ce17272` | MIT | 2026-10-30 |
| `references/claude-shorts` | https://github.com/agricidaniel/claude-shorts | `a369fad` | MIT | 2026-04-10 |
| `references/openmontage` | https://github.com/calesthio/openmontage | `195eab2` | **AGPL-3.0** | 2026-10-28 |
| `references/animate` | https://github.com/cth9191/animate | `7e5eb56` | MIT | 2026-10-05 |
| `references/handy` | https://github.com/cjpais/handy | `7bfb2e2` | MIT | 2026-10-27 |
| `references/agent-reach` | https://github.com/Panniantong/agent-reach | `14c2134` | MIT | 2026-10-25 |
| `references/youtube-automation-agent` | https://github.com/darkzOGx/youtube-automation-agent | `e973d51` | MIT | 2026-10-26 |

## Pelajaran per repo

Kedalaman bacaan berbeda. "Kode" = file skrip dibaca langsung. "README" = hanya README dan struktur folder.

### ffmpeg-skill (kode)
- Tabel platform di `scripts/_platforms.py`: durasi maksimum, rasio, loudness. Angka yang dipakai: Reels 90 dtk, Shorts 180 dtk, TikTok 600 dtk; resolusi dibandingkan pada **sisi pendek**; loudness target -14 LUFS, toleransi 2; fps maksimum 60 (bukan minimum 24).
- `scripts/check.py`: pola "ukur hasil, laporkan `ok` / `warn` / `error` plus saran perbaikan".
- `templates/{tiktok,reels,shorts}.json`: ukuran zona aman dan default caption per platform (belum dipakai).
- **Dipakai:** `clippercuan/app/clipper/delivery.py`, REST `.../delivery`, MCP `check_delivery`.
- **Dipakai berikutnya:** zona aman pada `platform_specs.json`, overlay Studio, pengukuran mask caption lewat libass, serta antrean ekspor/unduhan varian yang diperiksa. Profil tetap berlabel referensi; title/watermark/teks sumber di luar cakupan mask caption.

### claude-shorts (kode)
- `scripts/compute_reframe.py`: pelacakan wajah dan pelacakan kursor untuk rekaman layar, perataan posisi.
- `scripts/snap_boundaries.py`: batas klip ditarik ke batas kata, lalu ke jeda hening terdekat.
- **Dipakai:** gagasan crop mengikuti wajah (sudah ada lebih dulu di `facetrack.py`).
- **Tambahan:** snap hening opt-in dengan invariant kata/durasi dan cache; cursor tracker manual eksperimental dengan fallback. Diuji sintetis; benchmark nyata belum tersedia.

### openmontage (README)
- Gerbang persetujuan visual, analisis video referensi, papan produksi.
- **Dipakai:** tidak ada perubahan; `/api/production` dan pilih kandidat sudah ada di ClipperCuan.
- Lisensi AGPL-3.0: hanya ide.

### ghost-editor (kode/dokumentasi workflow)
- Self-check akhir (jeda, level suara, ukuran caption), pilih take terbaik, gaya dari reel referensi.
- **Dipakai:** self-check delivery/audio/visual opsional, review pengulangan lokal dengan persetujuan. Take terakhir hanya saran, bukan bukti kualitas audio terbaik; gaya dari reel masih memerlukan review semantik.

### youtube-automation-agent (dokumentasi fitur)
- Gerbang persetujuan, resume per tahap, Shorts dari video, analitik.
- **Dipakai:** tidak ada perubahan; resume (`recover_interrupted`, `retry`) sudah ada, analitik ada di `creator-dashboard/youtube_analytics.py`.

### animate (grammar/FORMATS.md)
- Animasi prosedural dengan storyboard.
- **Dipakai:** tidak ada perubahan; sudah tercakup Opuscar/HyperFrames di Video Studio.

### handy (README)
- STT offline dengan VAD Silero.
- **Dipakai:** tidak ada perubahan; `faster-whisper` dengan `vad_filter=True` sudah ada di ClipperCuan.

### agent-reach (README)
- Membaca platform lewat satu CLI untuk agen.
- **Dipakai:** tidak ada perubahan; ClipperCuan sudah punya MCP/CLI/REST.

## Memasang ulang `references/`

`references/` hilang bila repo di-clone baru. Pasang ulang pada commit yang sama:

```
mkdir references
cd references
git clone https://github.com/kajisho5/ffmpeg-skill.git            && git -C ffmpeg-skill checkout a2c8433
git clone https://github.com/kurbaitaev/ghost-editor.git          && git -C ghost-editor checkout ce17272
git clone https://github.com/agricidaniel/claude-shorts.git       && git -C claude-shorts checkout a369fad
git clone https://github.com/calesthio/openmontage.git            && git -C openmontage checkout 195eab2
git clone https://github.com/cth9191/animate.git                  && git -C animate checkout 7e5eb56
git clone https://github.com/cjpais/handy.git                     && git -C handy checkout 7bfb2e2
git clone https://github.com/Panniantong/agent-reach.git          && git -C agent-reach checkout 14c2134
git clone https://github.com/darkzOGx/youtube-automation-agent.git && git -C youtube-automation-agent checkout e973d51
```

Salinan awal dibuat dangkal (`--depth 1`); perintah `checkout` di atas hanya berhasil bila commit itu masih berada di riwayat yang terunduh. Bila gagal, jalankan `git -C <folder> fetch --unshallow` lalu ulangi.

## Ide yang belum dikerjakan dari referensi

Daftar kerja ada di [STATUS-2026-11-01.md](STATUS-2026-11-01.md) dan [../clippercuan/docs/plan-referensi-2026-10.md](../clippercuan/docs/plan-referensi-2026-10.md). Status terbaru dan batas benchmark: [FEATURE-COVERAGE.md](FEATURE-COVERAGE.md). Snap hening, zona aman/ekspor, cursor eksperimental dan review take sudah diintegrasikan; alignment kata, beat eksternal, dan review semantik referensi masih terbuka.

## Studi lanjutan — 1 November 2026

Dua repo tambahan dibaca terarah dalam checkout sementara `/tmp`, bukan dependency produk:

| Sumber | Commit kode | Lisensi kode | File yang dipelajari dan penerapan |
|---|---|---|---|
| [openai/whisper](https://github.com/openai/whisper) | `86098128c0b4f24f0e2aa2994de830614b474227` | MIT | `tests/test_transcribe.py`: word timestamps harus naik dan menjaga isi transkrip; tes kata “Americans” terhadap waktu 1,8 detik. Diterapkan sebagai validasi cue input eksplisit, bukan menjalankan/copy model Whisper. `tests/jfk.flac` hanya untuk ukur audio lokal. |
| [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | `55f20ff3448ed336df032ac6270cf47d215dc2c4` | BSD-3-Clause | `scenedetect/detectors/content_detector.py`: skor perubahan HSV/luma dan kalibrasi; `tests/test_detectors.py`: titik potong berbasis frame sebagai acuan regresi. Ditambahkan benchmark satu-ke-satu dengan precision/recall dan pembagian bukti tempo per sepertiga waktu. Tidak mengimpor detector upstream. |

Fixture video PySceneDetect berasal dari commit branch resources `e68d06a78e5241d82300d4924a53629feecbcb6b`, berbeda dari commit kode. Hak media tidak diasumsikan mengikuti lisensi kode; tidak dimasukkan ke Git. Sumber, hash, hasil, batas dan cara ulang Windows ada di [benchmarks/README.md](benchmarks/README.md). Keenam situs produk pengguna kini berhasil dibaca HTTP 200; perbandingan tersebut adalah studi halaman publik, bukan pengujian akun/layanan mereka.

## OneTake dan rekomendasi motion — 2 November 2026

Studi terarah [OneTake](https://github.com/feitangyuan/onetake), commit `013a61ac8d98883c73733f59c06e49e9ba444f14`, meliputi SKILL, README/lisensi dan dokumen rhythm, composition, reference-deconstruction, motion-library, product-demo, 3D serta sound. **PolyForm Noncommercial 1.0.0**, bukan MIT; tidak menyalin kode, font, template, film atau aset ke produk. Implementasi sendiri: `continuous_motion.py`, konsep eksplisit, beat sheet, carrier berlanjut, seek absolut dan pengukuran browser sebelum ekspor MP4. Tidak mengklaim seluruh pipeline OneTake.

README/lisensi Motion JS (MIT), dokumentasi pengantar Three.js dan rekomendasi agent tooling juga ditinjau tanpa memasang installer pihak ketiga. Pin sumber, cara memakai Video Studio, bagian yang diadopsi dan batasnya ada di [ONETAKE-STUDIO.md](ONETAKE-STUDIO.md). Halaman KreasiPintar tambahan pengguna belum terbaca karena 403; belum dipetakan fiturnya.

Audit ulang Three.js, GSAP, Opuscar, HyperFrames, Remotion, Lottie dan Continuous Motion: [peta integrasi/temuan/validasi](RENDERER-AUDIT-2026-11-02.md). Keberadaan repo atau dependency bukan bukti bahwa seluruh skill, style dan editor sudah terhubung.
