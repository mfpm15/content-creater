# Renderer Opuscar terarah — implementasi dan batas review

Implementasi ini melanjutkan audit `creator-dashboard/OPUSCAR_RENDERER_AUDIT_HANDOFF_2026-11-03.md` dan perbaikan awal `6d5b2fd`. Treatment asli ada di `OPUSCAR-DIRECTED-TREATMENT.md`; tidak mengambil kode/shot/aset demo.

## Perubahan yang aktif

- `opuscar_scene_spec.py` membaca subjek produksi (termasuk subjek panjang), aksi, komposisi, kamera, setting/background, foreground dan token continuity. Subjek utama menang atas kata benda sekunder. Midground/metafora digunakan sebagai fallback pengenalan objek. Hasilnya grammar terbatas, bukan HTML/JS dari model.
- `opuscar_primitives.py` menyusun primitive SVG asli: sambungan baja, pelat/press, modul, aperture, sleeve/core, conduit/capsule, lock/pins, anchor, mast, vault/cartridges, prism, registry, balance, barrier, wall/node, bridge dan matrix. Visual mekanis mempunyai tiga lapisan nyata. Aksi dan bentuk tidak ditentukan oleh `visualFamily`.
- `opuscar_actions.js` mengevaluasi anticipation → action → follow-through dari waktu absolut. Scene camera memakai locked/push/pull/track/overhead/oblique; overhead dan oblique adalah transformasi ilustrasi 2D, bukan kamera perspektif 3D. Kontrol render eksplisit tetap menang. Label/judul/subtitle tidak mengikuti kamera. Cue kata yang tersedia tetap mengatur reveal.
- Carrier continuity memakai token eksplisit. Fixture memiliki binding `defense-wedge` pada shot 13–14: ganjal bergerak dari timbangan lalu berubah menjadi bidang penghalang. Dunia → layar menggunakan transformasi SVG yang sama, bukan perkiraan koordinat terpisah.
- Process/comparison/concept yang belum dipahami menghasilkan placeholder editorial yang ditandai unsupported, bukan tiga node, dua bola atau constellation palsu. Gate menolak placeholder tersebut sebelum render penuh. Keluarga lama yang bermakna seperti nature/evidence masih tersedia.
- Semua job Opuscar membuat style frames setelah persetujuan Scene Plan, sebelum persetujuan Storyboard. Review menyimpan digest HTML (termasuk drawing code), frame, contact sheet dan hasil pengukuran di checkpoint. UI menampilkan contact sheet serta seluruh frame. Edit membatalkan review dan kedua approval. API dan worker sama-sama menolak review hilang/gagal/stale; status `sampled` tetap membutuhkan persetujuan manusia.
- Reviewer berjalan dalam subprocess dengan environment renderer yang disaring, satu browser, timeout 120 detik, dan cleanup process tree. Browser hanya mengakses satu halaman lokal serta URL SDK GSAP 3.13.0 yang tetap. Tidak membaca atau menyajikan direktori output secara umum. Kegagalan runtime menjadi `unmeasured`, tidak dianggap lulus.

## Bukti lokal

Fixture `creator-dashboard/fixtures/opuscar-mechanical-audit.json` direkonstruksi dari 19 deskripsi dalam audit. Durasi fixture 95 detik (19 × 5); narasinya diberi label fixture. Scene Plan/narasi produksi 109 detik dari laptop **tidak tersedia** di cloud ini.

- 19 objek/aksi fixture dikenali; 19 nama choreography, enam grammar kamera; tidak ada tiga struktur identik berturut-turut. Ini ukuran struktur program, bukan skor kualitas cerita atau perceptual diversity.
- Pemeriksaan setiap scene pada tiga fase aksi: 57 sampel pada 1080×1920, serta pemeriksaan landscape 1920×1080. Heading/subtitle tidak overflow/overlap; subjek memenuhi ambang sepertiga tinggi frame pada sampel yang diuji. Review memeriksa frame hampir hitam dan ukuran font minimum.
- Contact sheet pass pertama diperiksa. Koreksi mencakup false match `mastery`/`mast`, ukuran prop, line-height judul, arah timbangan, pecahan pin dan transisi signature. Pass kedua memakai drawing code hasil koreksi. Tiga style frames: pin, vault dan balance; contact sheet sembilan key shots; strip aksi interval 0,2 detik untuk 19 shot dan strip batas signature, tanpa playback.
- Pengulangan seek memeriksa DOM identik dan raster terbatas. Chromium menunjukkan variasi kuantisasi tepi meskipun DOM sama; SVG kini dibangun ulang dari template tepercaya pada setiap sampel agar cache frame lama tidak menentukan hasil. Gate mensyaratkan selisih kanal maksimal 2/255 pada maksimal 1% piksel, **bukan klaim hash PNG selalu identik**. Uji kontrol menolak perpindahan satu piksel dan perubahan warna di luar batas. Batas ini dicatat pada report.
- Validasi penutup 4 November: 152 tes dashboard, satu dilewati sesuai lingkungan, tanpa kegagalan. Ruff F/E9, pemeriksaan sintaks JavaScript dan diff juga lulus. Regresi dashboard mencakup adapter lain, approval/revision, redaksi, timeline dan pipeline MP4 fixture lokal. Tes baru menguji interpreter, injection, continuity, placeholder, stale review, perubahan rencana dan gate browser asli.
- Smoke UI menggunakan server HTTP asli dengan state/output fixture terisolasi: 19 subjek dapat diedit, contact sheet dimuat, review gagal menonaktifkan approval, tanpa error JavaScript. Smoke dashboard HTTP juga dijalankan.

## Mencoba di Windows

Jalankan setup core yang sudah ada, lalu dari root checkout:

```powershell
.\creator-dashboard\.venv\Scripts\python.exe creator-dashboard\opuscar_preview.py --plan creator-dashboard\fixtures\opuscar-mechanical-audit.json --output creator-dashboard\output\opuscar-directed-review --style-frames 7,10,13
```

Folder output wajib baru; CLI menolak overwrite. Ia membuat PNG dan report tanpa TTS, pemutaran media, atau encode film penuh. Untuk naskah sendiri, ganti path `--plan` dengan Scene Plan asli. Untuk produksi melalui UI, simpan/periksa Scene Plan, setujui untuk membuat style frames, lalu periksa gambar sebelum menyetujui Storyboard. Interpreter yang menolak aksi perlu arahan yang didukung; jangan melewati gate dengan memalsukan report.

Browser regression lokal dapat memakai `GSAP_TEST_SCRIPT` menunjuk SDK GSAP 3.13.0 lokal. CI Windows mengambil versi persis itu dan menjalankan kedua suite Opuscar; jangan menganggap penambahan workflow sebagai bukti run Windows sudah lulus.

## Batas yang tetap terbuka

Ini interpreter mekanis dengan kosakata terbatas. Tidak semua kalimat bebas pada subject/action/setting/metaphor/typography/lighting diterjemahkan secara semantik. Materi memakai ilustrasi vektor, bukan simulasi material fisik. `window.EV` berisi waktu hit sebagai metadata; tidak berarti semua foley telah disintesis atau audio sudah direview.

Belum ada full render ulang Cyber Kill Chain 109 detik, review suara, validasi audio/delivery film tersebut, atau tes pada laptop Windows pengguna. File lama tetap tidak diubah. Kegagalan subprocess pada laptop dan kebutuhan recovery manual dalam handoff belum dapat direproduksi karena artefaknya tidak tersedia. Gate/checkpoint baru mencegah render tanpa review yang cocok, tetapi bukan klaim menyelesaikan semua kemungkinan kegagalan job lama.
