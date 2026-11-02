# Perbaikan lintas menu — 2 November 2026

Perubahan ini menerapkan bagian yang terukur dari referensi pada Video Studio, Article Drafter dan ClipperCuan. Keberadaan sebuah repo/skill tidak berarti semua kemampuan upstream sudah tersedia. Katalog sumber dan batas lisensi tetap di [REFERENCES.md](REFERENCES.md), audit adapter di [RENDERER-AUDIT-2026-11-02.md](RENDERER-AUDIT-2026-11-02.md).

## Penerapan dan akar masalah

| Menu | Temuan | Implementasi |
| --- | --- | --- |
| Video Studio | String kamera/lighting/transisi umumnya hanya catatan; keputusan review tidak selalu mengubah gambar | `scene_render.py` memvalidasi `scenes[].renderControls`; normalizer, prompt, editor review dan generator GSAP/Three.js memakai parameter yang sama |
| Article Drafter | Ledger merekam review sumber tetapi belum menunjukkan angka yang tidak ada di kutipan atau nomor sitasi tidak dikenal | `evidence.py` memberi diagnostik literal per paragraf/tabel/list; `static/articles.js` menampilkan peringatan tanpa mengganti tulisan/attestation |
| ClipperCuan | Membatasi jumlah lima output masih memungkinkan rank 6+ masuk setelah penyaringan; fallback bisa memilih kandidat banned | `project.auto_picks` menyaring hanya lima posisi teratas, mengecualikan banned termasuk fallback; tanpa pilihan otomatis kembali ke `candidates_ready` |
| ClipperCuan | Timestamp NaN/infinity bisa dinormalisasi menjadi batas lain; kandidat invalid baru gagal saat media sudah diproses | `preflight.py` menolak timestamp nonfinite, memeriksa rentang sumber sebelum batch/render, menyediakan laporan baca saja di Studio |

Gagasan OneTake yang digunakan: parameter visual konkret, fungsi waktu absolut, carry/hold pada engine Continuous Motion yang sudah ada, dan pemeriksaan frame sebelum mengklaim hasil. Bacaan ulang `composition.md`/`rhythm.md` pada pin `013a61ac8d98883c73733f59c06e49e9ba444f14`; tidak menyalin kode/aset OneTake (PolyForm Noncommercial). Pola pemeriksaan lokal Clipper melanjutkan pelajaran `ffmpeg-skill`, `ghost-editor`, dan `claude-shorts` yang tercatat pada katalog; tidak mengimpor dependency baru. Pemeriksaan artikel adalah implementasi asli untuk menguatkan ledger yang ada.

## Kontrol gambar yang benar-benar tersedia

Pada editor Scene Plan/Storyboard Opuscar dan Three.js, buka **Kontrol gambar yang diterapkan saat render**:

- `camera`: `legacy`, `locked`, `push-in`, `pull-out`, `pan-left`, `pan-right`, `orbit`.
- `strength`: angka 0–1, default 0.5. Boolean, string, nonfinite, field/preset tidak dikenal ditolak.
- `lighting`: `legacy`, `soft`, `dramatic`.
- `transition`: `legacy`, `fade`, `cut`, `slide`.

2D mengubah transformasi ilustrasi serta filter brightness/contrast, tanpa menggeser judul/subtitle melalui kontrol kamera. Orbit 2D adalah rotasi kecil ilustrasi. Three.js mengubah posisi kamera dan intensitas tiga lampu per waktu adegan; kembali ke nilai legacy pada adegan/gap berikutnya tanpa bergantung seek sebelumnya. Transisi 3D berlaku pada HUD, bukan pergantian dunia/geometri WebGL. Strength mengendalikan gerak kamera, bukan intensitas transisi/lampu.

Tidak ada pemetaan bebas kalimat prompt menjadi JavaScript, CSS, script atau URL. Arahan bebas seperti komposisi/tipografi tetap catatan produksi. Kontrol ini ditolak pada Lottie/Continuous Motion; keduanya mempertahankan kontrak visual sendiri. Plan tanpa kontrol baru mempertahankan preset lama. Kedua approval dan pemeriksaan revision tetap berlaku. Mengedit storyboard membatalkan approval seperti sebelumnya; hasil lama tidak dirender ulang otomatis.

Pemeriksaan frame menemukan perbedaan awal `transform:none` vs matriks identitas saat seek melewati tween lalu kembali. Ilustrasi sekarang memiliki transformasi identitas eksplisit dan tween kamera 2D tidak memaksa layer 3D. Ini diuji sebelum/ sesudah tween, seek balik, wall time dan reload.

## Pemeriksaan artikel

Laporan `article.evidence` sekarang berisi `diagnostics` dan tiap claim memiliki `unknown_citations`, `numbers_absent_from_excerpts`, `review_warnings`. Sitasi tunggal serta kelompok `[1, 2; 3]` dikenali. Nomor sitasi tidak dianggap angka klaim. Rujukan belum disitasi dan entri identik setelah normalisasi spasi/huruf turut dilaporkan.

Angka dibandingkan secara literal hanya dengan kutipan **sumber tertaut**. Tidak menyamakan `1.000` dengan `1000`, menerjemahkan angka tertulis, menilai satuan, konteks, negasi atau kebenaran. Kesamaan angka bukan bukti dukungan semantik. Attestation pengguna tidak otomatis dihapus saat ada peringatan; keduanya ditampilkan terpisah. Tidak menghubungkan sumber atau melakukan fetch web diam-diam, tidak mengubah naskah/ekspor.

## Pemeriksaan kandidat Clipper

`GET /api/projects/{pid}/clips/{cid}/preflight` memeriksa waktu finite dan urut, batas durasi sumber (toleransi 0.05 detik), track kata yang efektif, kemungkinan pemotongan kata, dan kepadatan di atas empat kata/detik. Track override klip memakai waktu relatif; transkrip proyek memakai waktu absolut, termasuk revisi caption workspace. Peringatan tidak menghapus kata, tidak memblokir klip dengan waktu valid, dan bukan prediksi viralitas/kualitas audio. Durasi sumber belum diketahui dilaporkan sebagai keterbatasan.

Batch memeriksa seluruh pilihan sebelum mengubah status/mengirim pekerjaan; invalid tidak menghasilkan batch parsial. Render individual melakukan pemeriksaan ulang sebelum mengunduh segmen remote. Tambah/edit klip menolak nonfinite sebelum menyimpan, sambil mempertahankan clamp sumber dan minimum satu detik yang sudah ada. Rank 6+ tetap draft hingga dipilih manual, termasuk bila dipin; kandidat banned tidak menjadi fallback. Tidak menambah pengelola antrean baru atau upload audio pribadi.

## Bukti dan batas validasi

- Uji statis SDK asli **GSAP 3.13.0 / Three.js 0.160.0**: 24 kasus (12 per adapter), kontrol kamera/lampu/transisi mengubah piksel; sampel identik pada seek balik, reload, dan setelah menunggu dua frame browser. Kamera/lampu Three.js kembali ke legacy pada adegan berikutnya. Semua tanpa error JavaScript. Bukti teks: [studio-controls-audit-20261102.json](benchmarks/studio-controls-audit-20261102.json), mencakup hash source/frame; SDK dan screenshot temporer tidak disertakan di Git.
- Frame tersebut memakai Chromium software WebGL Linux 480×854, bukan benchmark GPU laptop Windows, pemeriksaan seluruh frame, atau penilaian estetika manusia. Tidak memutar media.
- Suite baru `test_studio_controls.py` memeriksa validasi, roundtrip, penolakan adapter tak didukung, waktu absolut lampu/kamera dan diagnostik artikel. `tests/test_preflight.py` menguji input invalid, override, API, batch atomik serta pipeline tersimpan Top 5 → selesai → pilihan manual rank 6. Operasi media/scoring pada tes state dimock; suite regresi lama tetap mencakup encode FFmpeg sintetis nyata.
- Regresi lokal akhir: **126 tes dashboard lulus**, **223 tes Clipper lulus**, compile Python, Ruff F/E9, pemeriksaan sintaks tiga modul JavaScript, HTTP dashboard/redaksi dan `/api/health` Clipper lulus. Smoke Top 5 juga memeriksa skor tersaring serta semua Top 5 banned. Data/output tes sementara; tidak memakai artefak pengguna.
- Smoke UI Chromium dengan API fixture: empat engine membuka review tanpa mengubah plan; kontrol GSAP/Three.js terkumpul sesuai pilihan dan tidak muncul pada Lottie/Continuous; peringatan artikel tampil dan teks HTML tidak dieksekusi. Tanpa error JavaScript/playback. Ini tes interaksi fixture, bukan pengujian provider produksi.
- Commit implementasi `0832ee6`: [Windows native 41422103700](https://github.com/mfpm15/content-creater/actions/runs/41422103700) **Success**, [Clipper CI 41422103657](https://github.com/mfpm15/content-creater/actions/runs/41422103657) **Success**. Workflow Windows menyertakan `test_studio_controls.py`, installer core dan launcher path berspasi; Clipper menemukan tes baru otomatis. Bukti frame SDK di atas tetap berasal dari Linux, bukan GPU Windows pengguna.

Remotion masih integrasi Stickman/OpenCreator terpisah, bukan engine Video Studio; runtime dan hardening worker terpisah belum divalidasi pada perubahan ini. Tidak mengklaim semua 59 style Lemo, 4K60, shutter motion blur, semua fitur layanan komersial atau semua repo/skill sudah diimplementasikan. CSV nyata serta benchmark media pengguna tetap menunggu data yang telah ditunda pengguna.
