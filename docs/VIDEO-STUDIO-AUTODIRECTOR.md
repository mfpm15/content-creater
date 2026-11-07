# Video Studio AutoDirector — workflow dan keterbatasan

## Cara pakai (alur cepat)
1. Buka **Video Studio**. Isi **Judul video** dan, bila perlu, **Deskripsi/konteks**. Deskripsi adalah arahan produksi, bukan naskah yang dibacakan.
2. Pilih durasi, format, dan desain caption. Gunakan pilihan tema **Otomatis** atau pilih langsung gaya populer; 12 tema lengkap ada pada panel yang dapat dibuka.
3. **Cari gambar otomatis** memakai pencarian metadata Wikimedia Commons (CC0/domain publik). Ini pilihan yang dapat dimatikan; import manual masih tersedia.
4. **Otomatis lanjut sampai MP4** menghasilkan draf video tanpa menyetujui dua tahap secara manual; opsi ini dapat dimatikan agar Scene Plan dan Storyboard tetap dapat diedit sebelum rendering.
5. **Riset web** opsional: hanya bisa aktif jika Google Search grounding dikonfigurasi. Planner 9Router terpisah tetap wajib bila ingin membuat narasi dari judul tanpa naskah. Jika provider tidak ada, UI menunjukkan status/gagal alih-alih memalsukan hasil.
6. Render memerlukan Node, Remotion, browser lokal dan FFmpeg; dubbing Edge-TTS juga memerlukan jaringan yang berfungsi. Klik **Tes dubbing** jika ingin mendengar contoh lebih dulu.
7. Periksa MP4, narasi, teks, fakta, relevansi gambar dan lisensi sebelum mengunggah. Sistem tidak mengunggah video secara otomatis.

## Tiga mode
- **Quick otomatis** (default): sistem memilih template berdasarkan kata kunci judul, menulis narasi bila planner tersedia, menyusun scene, mencoba mengisi maksimal 3 shot dengan gambar CC0/domain publik, kemudian membuat MP4. Kamera/gambar/tipografi/caption diproses dengan Remotion. Ini draf, bukan jaminan kualitas.
- **Review manual**: nonaktifkan opsi render otomatis. Dua gerbang review Scene Plan dan Storyboard tetap dipakai.
- **Advanced**: naskah bertimecode, edit scene, engine alternatif, brand kit, model, FPS, mode suara dan impor manual. Fitur engine lama tetap dipertahankan.

## Desain caption
- Clean Editorial: keterbacaan tinggi, efek minimal.
- Kinetic Pop: kemunculan frasa dengan animasi pendek.
- Moving Pill: kapsul warna dengan transisi ringan.
- Cinematic Outline: frame teks dengan garis aksen.
- Word Highlight: **hanya** menyala per kata bila tersedia *wordCues* dari pengguna/penyelarasan audio yang sebenarnya. Tanpa cue, renderer menampilkan frasa seperti biasa. Hasil text-chunk tanpa cue masih **estimasi**, bukan forced alignment.

## Pencarian media otomatis
- Provider: Wikimedia Commons Action API generator search + imageinfo.extmetadata, hanya thumbnail dengan host \`upload.wikimedia.org\` dan \`https://\`.
- Batas: maksimal 3 shot per video, enam hasil pencarian per shot, gambar PNG/JPEG/WebP maksimal 8 MB, tanpa redirect, tanpa download host arbitrer.
- Seleksi: hanya label metadata **CC0/public domain**, nama berhubungan dengan query shot, URL sumber Commons disimpan dengan lisensi, nama kreator, hash file, dan \`rightsBasis=external_metadata_unverified\`.
- Jika tidak ditemukan: renderer menggunakan ilustrasi procedural dan melaporkan alasan. Tidak ada scraping Google Images, klaim gambar sebagai bukti peristiwa, atau unduhan sumber tanpa metadata.
- Ini bukan penjaminan lisensi hukum. Public domain bergantung pada wilayah dan berkas dapat memuat merek, wajah, atau materi yang memiliki batas terpisah; periksa sebelum monetisasi.

## Prinsip anti-slideshow (terinspirasi Bang Motion, MIT)
- Setiap scene punya *visual purpose*, objek konkret yang dipakai untuk menjelaskan fakta, dan gerakan kamera yang mendukung cerita.
- Variasi media dilakukan karena perkembangan narasi, **bukan** menjalankan banyak transisi secara acak.
- Hindari judul + foto + fade yang sama terus-menerus, berulang memakai aset yang sama, dan gerak Ken Burns sebagai satu-satunya unsur baru.
- Gunakan gerakan deterministik mengikuti frame agar preview, repeat seek dan render MP4 konsisten.
- Template bukan pengganti naskah, kesesuaian aset, mixing suara atau review visual.

Panduan Bang Motion: https://github.com/bangtutorial/bang-motion (lisensi MIT; tidak ada kode/assets upstream yang dicopy dalam implementasi ini).

Caption timing: https://www.remotion.dev/docs/captions/create-tiktok-style-captions

Wikimedia API dan kebijakan:
- https://www.mediawiki.org/wiki/API:Imageinfo
- https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy

## Belum tersedia
- Model text-to-video yang membuat rekaman video realistis.
- Pencarian footage bergerak komersial otomatis, mixing musik berlisensi dari media provider, auto-publishing.
- Forced alignment kata yang otomatis memproses WAV penuh (butuh worker khusus seperti WhisperX dan GPU/CPU).
- Validasi kebenaran faktual otomatis, pemeriksaan copyright hukum dan evaluasi estetika oleh manusia.

## Pengujian
Windows CI menjalankan unit test otomatis media, lisensi, path, sanitasi, pipeline persetujuan, video caption, tipe Remotion, javascript browser, dan rendering MP4 nyata dari dua gaya. Verifikasi dengan audio/sumber internet aktual serta penilaian visual di laptop tetap diperlukan.
