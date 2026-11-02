# Audit integrasi renderer — 2 November 2026

Audit dilakukan pada main `dfb65fc` dan perubahan clock dalam sesi ini. Kode/manifest/panduan relevan dibaca terarah. Validasi berupa tes, sampling frame HTML/WebGL dan analisis file; **tidak memutar media**.

## Yang benar-benar terhubung

| Komponen | Versi/rujukan yang ditemukan | Pemakaian nyata | Batas |
|---|---|---|---|
| Three.js | Video Studio CDN **0.160.0**; manifest library Lemo meminta ^0.170.0 | `video_drafter.generate_threejs_composition`: WebGLRenderer, geometris icosahedron, ring, partikel, light dan kamera terjadwal | Versi CDN bukan versi manifest Lemo. Tidak memakai seluruh style/GLB/rig/shader Lemo, tidak membentuk model bebas dari prompt. |
| GSAP | **3.13.0** | Timeline animasi HTML 2D dan clock 3D; registrasi `__timelines.video` | Bukan editor drag-and-drop umum. Demo HyperFrames yang tadinya memakai `@3` kini dipin agar tidak berubah diam-diam. |
| Lemo-Opuscar | Library `0.1.0`, Node ≥20; package MIT | Worker TTS `core/tts/tts_zh.py`, lingkungan suara, metode produksi/kontrak waktu; gambar dibuat generator lokal milik dashboard | Katalog 59 STYLE.md **tidak** otomatis menjadi 59 preset Video Studio. Pipeline gambar dashboard memakai HyperFrames, bukan memanggil `core/render/video.mjs`. |
| HyperFrames | Terpasang **0.8.195**, Apache-2.0 | CLI render adapter Opuscar dan Three.js, satu worker; kontrak timeline GSAP | Memerlukan runtime Node/browser/CDN yang siap; bukan renderer Continuous Motion atau Lottie. |
| Remotion | Paket OpenCreator **4.0.473** | `StickmanLandscape/Portrait`, validator timeline, worker `selectComposition` + `renderMedia`, executor OpenCreator dan runtime bundle | Belum menjadi pilihan engine pada `/api/videos`. Dependency/runtime Remotion tidak terpasang di checkout cloud ini; eksekusi Remotion tidak diklaim teruji. |
| Lottie | JSON `v=5.12.2`, player standar pernah diuji terpisah | Ekspor subset ellipse/rect/text/transform; JSON yang sama dipakai preview | Tanpa audio/3D/aset eksternal dan bukan seluruh Motion Plan. |
| Continuous Motion | Adapter original proyek | SVG satu dunia, konsep, hold, carrier, PNG → FFmpeg, cache state, dua approval | Ide OneTake dipelajari; tidak mengimpor kode/aset PolyForm Noncommercial. Bukan seluruh pustaka/pipeline OneTake. |

### Berkas yang dipelajari

- Dashboard: `video_drafter.py`, `visual_review.py`, `tools.json`, template demo HyperFrames, manifest dan tes terkait.
- Lemo: `AGENTS.md`, `TECHNIQUE.md`, `core/render/{page,video}.mjs`, manifest. Kontrak upstream adalah `DUR`, `render(t)`, `READY`; determinisme dan timeline bersama menjadi acuan.
- HyperFrames terpasang: metadata paket dan `createGSAPFrameAdapter`; frame disampling dengan `timeline.seek(seconds, false)`. Peninjauan file dependency hanya untuk memeriksa kontrak; tidak mengedit dependency.
- OpenCreator: AGENTS lokal; `packages/stickman-remotion/{src/Root.tsx,src/StickmanLandscape.tsx,src/timeline.ts,src/timeline.test.ts,remotion.config.ts,package.json}`; daemon `creator/stickman/{remotion-worker,remotion-executor}.ts`.
- Upstream publik: GSAP README dan source tag **3.13.0** (`seek` memang membisukan callbacks secara default), metadata npm versi yang sama; Three.js LICENSE tag r160; README dan LICENSE Remotion. Bacaan main upstream adalah informasi saat audit, bukan pin runtime baru.

## Masalah yang diperbaiki

1. **Dua clock berbeda.** GSAP disampling berdasarkan waktu film, tetapi animasi CSS dekoratif berjalan menurut waktu browser. Hasil frame dapat bergantung pada kapan screenshot diambil. `animation_clock.py` sekarang menghentikan dan menyetel waktu Web Animations API secara eksplisit; offset scene dibaca dari `data-start`, termasuk pseudo-element dan animasi yang dibuat ulang sesudah display berubah.
2. **Draw 3D bergantung callback.** Sebelumnya WebGL menggambar hanya dari tween `onUpdate`. GSAP `seek(t)` biasa memakai suppress-events; review kita juga tidak mengirim `false`. HyperFrames sendiri sudah memakai `false`, jadi temuan ini **bukan bukti semua MP4 HyperFrames sebelumnya beku**. Sekarang `render`/`totalTime` GSAP memanggil sinkronisasi frame eksplisit sambil mempertahankan objek/chaining GSAP asli; suppressed seek dan sampling oleh parent timeline ikut tercakup.
3. **Scene bintang acak saat reload.** `Math.random()` untuk posisi awal diganti seed tetap dari topik. Geometri tidak dibangun ulang saat seek. Buffer WebGL dipertahankan untuk screenshot statis; tradeoff-nya penggunaan buffer GPU lebih tinggi daripada default.
4. **Kontrak core Opuscar belum diekspos.** Kedua template kini juga menyediakan `DUR`, `render(t)`, `READY`, `__ready` dan `__seek` yang mengembalikan boolean. Durasi deklaratif mengikuti plan, bukan ekor tween dekoratif. Produksi tetap memakai jalur HyperFrames yang sudah ada; tool core Lemo belum dijalankan dalam audit ini.
5. **Katalog Remotion berlebihan.** Deskripsi/kemampuan launcher kini menjelaskan komposisi OpenCreator yang terpisah, tanpa mengklaim editor drag-and-drop atau agent skill sudah aktif.

## Gap arsitektur yang masih nyata

Pembaruan sesudah audit ini: kontrol kamera/lighting/transisi yang eksplisit telah diterapkan pada GSAP/Three.js, dengan uji 24 kasus frame statis. Baca [INTEGRATION-REVIEW-2026-11-02.md](INTEGRATION-REVIEW-2026-11-02.md) untuk schema, pemetaan adapter dan batasnya. Field arahan bebas di bawah tetap tidak otomatis menjadi kode/render parameter.

- `onScreenText`, narration, waktu, subject dan visual family berpengaruh pada hasil sesuai adapter. Sebaliknya, banyak string `camera`, `lighting`, `composition`, `transition`, `typography` dan creative direction dipertahankan untuk review tetapi **belum diterjemahkan menjadi semua parameter render**. Menulis arahan sinematik yang detail tidak otomatis membuat renderer melaksanakannya. GSAP memakai banyak easing/transisi tetap; kamera/material Three.js juga preset.
- Komposisi Remotion membutuhkan timeline dengan `shots`, `captions`, path image/audio, rasio, fps dan totalFrames yang valid. Default Root berisi `shots=[]`/`captions=[]` dan 30 frame; `assertTimeline` menolak total coverage tersebut. Launcher preview kosong bukan bukti render siap. Worker OpenCreator memang memasukkan props/aset valid dari prosesnya sendiri, sehingga alur tersebut berbeda dari launcher tanpa props.
- Guard path worker Remotion yang dibaca memakai containment secara leksikal. Resolusi symlink/junction, batas request jaringan browser dan hardening asset server perlu audit/tes paket khusus sebelum alur tersebut dipakai untuk input baru dari Video Studio. Ini catatan baca sumber, bukan klaim eksploit berhasil. Tidak mengubah daemon/runtime OpenCreator atau menyatakan lisensi/remotion runtime selesai dipasang.
- Upgrade Three.js ke versi manifest memerlukan perubahan format import/bundle dan regression test; tidak cukup mengganti angka versi URL classic build. Versi 0.160.0 dipertahankan secara sadar dalam perubahan ini.

### Urutan pengembangan yang disarankan

1. Definisikan parameter motion/camera/lighting/transisi yang benar-benar didukung per adapter, beserta allowlist/range dan indikator field yang hanya menjadi catatan. Pemilik awal: normalizer dan generator di `video_drafter.py`, UI review `static/videos.js`.
2. Terjemahkan parameter tersebut satu per satu; setiap perubahan diuji berdasarkan gambar pada waktu tertentu, repeat seek dan kecocokan durasi. Jangan langsung mengeksekusi string prompt sebagai JavaScript atau import URL.
3. Bila Remotion akan masuk Video Studio, buat adapter eksplisit Scene Plan → timeline manifest dengan frame integer, coverage, hash media, file staging privat dan pemetaan URL media lokal. Gunakan worker terisolasi; pertahankan dua approval dan redaksi credential. Uji package/daemon sesuai AGENTS OpenCreator sebelum membuka engine tersebut di UI.
4. Setelah itu evaluasi bundling aset GSAP/Three.js agar tidak tergantung CDN, lalu migrasi versi secara terkunci. Jangan mengedit node_modules atau menganggap semua skill/style sudah menjadi fitur hanya karena repositorinya ada.

## Validasi dan lisensi

- **119 tes dashboard lulus**, termasuk tes clock nyata CSS/pseudo-element, seek suppressed, sampling parent, durasi, getter/chaining dan katalog. Ruff F/E9, smoke dashboard HTTP/katalog/redaksi serta diff check lulus. Suite Clipper tidak diulang karena tidak diubah.
- SDK **GSAP 3.13.0** dan **Three.js 0.160.0** yang benar-benar dipakai dimuat dari salinan temporer untuk uji frame statis. Tidak dimasukkan ke Git. Kedua adapter menghasilkan piksel identik setelah seek bolak-balik, menunggu dua frame browser, dan reload; Three.js juga diuji buffer tidak kosong dan WebGL berubah ketika raw seek membisukan event.
- Hasil: [render-adapter-audit-20261102.json](benchmarks/render-adapter-audit-20261102.json). Ini uji software WebGL cloud Linux pada 480×854, bukan benchmark GPU Windows, render panjang, provider TTS atau eksekusi Remotion.
- Three.js r160 berlisensi MIT; metadata GSAP 3.13.0 merujuk Standard “no charge” license, bukan MIT; HyperFrames terpasang Apache-2.0. Remotion mempunyai Free/Company License dengan syarat entitas/penggunaan. Jangan menurunkan lisensi seluruh dependency dari lisensi repo pembungkus atau menyatakan semua bebas syarat.

CI kode `e17d95a`: [Windows native run 41416880214](https://github.com/mfpm15/content-creater/actions/runs/41416880214) **Success**, mencakup setup core, tes clock/CSS browser, tes dashboard terpilih, HTTP dan launcher path berspasi. Bukti SDK GSAP/Three.js penuh pada audit ini tetap berasal dari frame statis software WebGL cloud Linux, bukan GPU laptop pengguna. Perbaikan generator berlaku pada komposisi baru; artefak pengguna lama tidak ditulis ulang.
