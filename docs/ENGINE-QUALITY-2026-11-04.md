# Audit dan perbaikan renderer — 4 November 2026

Permintaan: pastikan Opuscar/GSAP, Three.js, Remotion dan renderer lain benar-benar dipakai untuk memperbaiki output. Audit menemukan bahwa Three.js sebelumnya mengulang satu icosahedron/ring/grid untuk semua adegan, Remotion selalu menggambar tiga langkah tanpa label sumber, dan Lottie hanya memilih lingkaran/kotak.

## Perubahan

- **Three.js:** `three_scene.js` membangun geometri native per subjek mekanis dari grammar `opuscar_scene_spec`: rantai, pin, brankas, timbangan, penghalang, jembatan, prisma, registri/modul/matriks, conduit/aperture, jangkar/mast, pelat/segel. Pose dihitung dari waktu absolut; brankas memiliki pivot pintu. Crossfade mempengaruhi objek, menggunakan material terpisah per shot, mempertahankan objek keluar selama objek berikutnya masuk. Frame pertama memiliki objek. Grid, partikel dan icosahedron global dihapus. Judul/subtitle dipisah dari pusat objek dan font menyesuaikan ruang.
- **Remotion:** diagram proses/perbandingan memakai label eksplisit yang ikut disetujui di Scene Plan. Tidak lagi mengarang tiga langkah atau dua lingkaran perbandingan. Tanpa diagram, tampilkan teks editorial dari subjek/judul; angka literal tetap mempertahankan tanda/desimal. Penyesuaian teks dihitung ulang per frame supaya seek tidak bergantung riwayat frame. Referensi root yang sebelumnya hilang melalui komponen SDK diganti dengan elemen DOM langsung, sehingga pemeriksaan layout benar-benar berjalan. Pemeriksaan menerima komposisi tampak yang diskalakan, tetap mengecualikan kalkulator tersembunyi. Fixture 1080p mencatat 40 frame terukur tanpa overlap; regresi pipeline kini mewajibkan `dom_measurement_available=true`. Bila DOM tidak terukur, laporan menjadi `unmeasured` dengan issue eksplisit, bukan lulus berdasarkan jumlah PNG.
- **Lottie:** schema diagram yang sama diekspor menjadi layer teks/vektor standar, ID layer unik, judul menyesuaikan area. Preview mulai dalam keadaan paused. Tidak menambah audio/3D ke format subset ini.
- **Continuous Motion:** judul/caption panjang menyesuaikan area sebelum capture. Dependensi visual tetap hanya scene/viewport/transition yang sudah tercakup dalam cache key; pengujian kesetaraan frame cache tetap dijalankan.
- **Opuscar/GSAP:** grammar mekanis, absolute seek dan gate style frames dari perbaikan sebelumnya dipertahankan serta diuji ulang. Tidak membuka bypass persetujuan.

## Kontrak diagram

Field opsional pada `scenes[]` untuk Remotion/Lottie:

```json
{"diagram":{"kind":"process","labels":["Riset dan sumber","Tinjau storyboard","Render dan periksa"]}}
```

`process`: 2–5 label; `comparison`: tepat 2. Label 1–48 karakter tanpa karakter kontrol. Backend dan validator manifest Node menolak struktur tidak valid; label bukan kode/CSS. Editor menyediakan JSON diagram pada setiap adegan. Label berasal dari naskah yang ditinjau, bukan ekstraksi fakta otomatis. Edit tetap membatalkan approval. Adapter lain menolak diagram eksplisit agar tidak diabaikan diam-diam.

## Bukti validasi

- 156 tes dashboard lulus pada Linux, termasuk SDK GSAP 3.13.0 dan Three.js 0.160.0 nyata, pipeline dua approval, audio mastering, ekspor bundle dan kesetaraan cache Continuous Motion.
- Three.js: tiga subjek berbeda pada 1080×1920, 1920×1080, 1080×1080 dan 320×568; PNG repeat seek identik; bounding box geometri terproyeksi tidak menabrak judul/caption pada tiga subjek di empat ukuran tersebut; objek tetap tampak pada awal/batas scene; tanpa error JavaScript.
- Remotion: `npm ci`, TypeScript, 6 tes Node, `npm audit --omit=dev` (0 vulnerabilities). Smoke HTTP dashboard lulus.
- Encode nyata **1080×1920, H.264/yuv420p, 30 fps**: Three.js dan Opuscar masing-masing 90 frame/3 detik melalui HyperFrames 0.8.195; Remotion dan Continuous masing-masing 60 frame/2 detik melalui adapter masing-masing.
- Sampel PNG hasil dekode diperiksa pada awal, tengah, sekitar batas detik 1, dan akhir. Variasi piksel menunjukkan sampel tidak kosong; ini bukan black-detection seluruh video atau skor estetika. Inspeksi gambar langsung dilakukan tanpa playback.
- Lottie diuji dengan **player resmi lottie-web 5.12.2**, bukan hanya preview internal: semua label tampil, PNG repeat identik, tanpa error browser.
- Fixture terisolasi di `work/` di luar repo; media/SDK unduhan tidak dimasukkan Git. Tidak memakai provider/TTS daring, tidak merender ulang proyek lama.
- Workflow Windows diperluas untuk mengambil SDK Three.js pinned dan menjalankan tes diagram/native geometry. Hasil run baru harus diperiksa tersendiri; bukti Linux bukan bukti GPU laptop Windows.

## Batas yang masih berlaku

Ini perbaikan implementasi dan verifikasi fixture, **bukan jaminan setiap naskah otomatis menjadi film berkualitas tinggi**. Three.js memakai grammar mekanis terbatas dengan gerak bergaya, bukan simulasi fisika, model karakter atau interpreter seluruh kalimat bebas. Subjek tidak dikenal memakai pelat editorial. Kamera/lighting eksplisit `renderControls` tetap menjadi kontrak; tidak seluruh arahan prosa atau continuity Opuscar diterapkan pada 3D.

Lottie tetap subset rectangle/ellipse/text/linear transforms, belum mencakup seluruh spesifikasi Lottie. Continuous tetap tiga konsep trace/focus/assemble. Sound cue prosedural bukan desain foley semantik lengkap; caption tanpa timestamp bukan forced alignment. Tidak ada klaim motion blur, 4K60, lip-sync, GPU Windows, atau penilaian manusia melalui playback. Gate style-frame wajib saat ini khusus Opuscar; renderer lainnya tetap memerlukan review storyboard dan hasil.

Rencana produksi asli 109 detik belum tersedia pada checkout ini. Fixture pendek tidak menggantikannya, dan narasi asli tidak diubah.


## Lanjutan: jumlah objek dan cue Three.js

Audit berikutnya menemukan jumlah rantai/beban masih dipotong tujuh meskipun grammar menyetujui hingga 12, cue kata belum menunda aksi objek 3D, dan transisi slide hanya menggeser teks. `three_scene.js` kini mempertahankan seluruh jumlah 1–12, menghitung fase aksi dari timestamp cue hingga akhir adegan, serta menggeser objek masuk/keluar bersama transisinya. Posisi objek dikembalikan ke origin pada setiap seek agar tidak menumpuk transformasi.

Regresi SDK nyata memeriksa 12 mata rantai, 12 beban beserta counterweight terpisah, pose diam sebelum cue 1,2 detik, perubahan sesudah cue, slide objek dan kesamaan seek ulang. Pemeriksaan layout pada empat ukuran dari audit sebelumnya tetap dijalankan. CI Windows belum terverifikasi: connector tidak mengembalikan status check dan akses CLI Actions ditolak; itu bukan bukti berhasil ataupun gagal.


Validasi lanjutan: 157 tes dashboard lulus (Linux), smoke HTTP lulus, syntax JavaScript/diff bersih. HyperFrames menghasilkan MP4 H.264/yuv420p 1080×1920, 30 fps, 120 frame/4 detik untuk fixture 12 rantai + cue 1,2 detik + slide menuju 12 beban. Still hasil dekode diperiksa langsung tanpa playback. Media uji berada di luar repo; proyek produksi lama tidak disentuh.
