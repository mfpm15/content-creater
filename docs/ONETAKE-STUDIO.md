# Video Studio: gerak kontinu — 2 November 2026

Pengembangan ini memakai prinsip kerja yang dipelajari dari [OneTake](https://github.com/feitangyuan/onetake/blob/013a61ac8d98883c73733f59c06e49e9ba444f14/SKILL.md). Adapter, komposisi dan renderer ditulis sendiri. Tidak menyalin library, template, font, film atau aset OneTake; tidak memasang skill tersebut ke runtime aplikasi.

## Cara mencoba di laptop Windows

1. Ambil pembaruan lewat `git pull --ff-only`, lalu restart dashboard. Jalankan `setup-core.bat` bila Playwright/FFmpeg belum dipasang; Chrome atau Edge harus tersedia. Tidak ada dependency baru di luar setup core yang sudah ada.
2. Buka **Video Studio** → **Render Adapter: Continuous Motion**.
3. Baca tiga pilihan **Jejak ide**, **Lensa penjelas**, **Bangun hasil**. Pilih konsep yang sesuai; ketiganya mempunyai ide visual, carrier, look dan batas yang berbeda; Bangun hasil maksimal 12 beat. Brand kit yang dipilih menggantikan palet konsep.
4. Untuk percobaan tanpa provider, klik **Coba contoh lokal 15 detik**. Tombol mengisi contoh yang aman dan memilih mode naskah lokal serta musik/foley prosedural tanpa dubbing. Ini bukan unggah audio pribadi.
5. Klik **Buat Scene Plan**. Periksa timecode, narasi/teks, arahan visual dan beat sheet: objek yang berlanjut, interval gerak dan interval diam.
6. Setujui Scene Plan, kemudian periksa/setujui Storyboard. Mengubah isi storyboard membatalkan approval sebelumnya; perubahan tidak memulai render sendiri.
7. Tunggu MP4 selesai. Baca laporan media/gerak, putar videonya, lalu unduh MP4 atau paket produksi. Kontinuitas dan determinisme diukur pada sampel yang dijelaskan; kualitas cerita tetap memerlukan review manusia.

Mode **Judul → Motion Planner** tetap membutuhkan provider model. **Naskah sendiri** tidak memanggil model atau pencarian. **Narasi TTS + musik** memerlukan runtime dan layanan suara yang sudah dipakai adapter lama; mode musik lokal melewati TTS sepenuhnya. Tidak menambah pengelolaan antrean render atau upload audio pribadi.

## Yang diterapkan

| Prinsip yang dipelajari | Implementasi dalam proyek |
|---|---|
| Pilih ide visual sebelum menyusun film | Tiga konsep dalam UI; backend mewajibkan pilihan eksplisit untuk adapter kontinu. Bukan memilih konsep diam-diam. |
| Sesuatu bertahan antarbeat | Satu node SVG `motion-hero` berubah posisi/ukuran; jalur, lensa atau wadah tetap berada pada dunia yang sama. Bukan mengganti container scene penuh. |
| Ritme mencakup gerak dan diam | Beat sheet diturunkan dari timecode; interval transisi dan hold berbagi sumber data dengan komposisi. Durasi seragam diberi saran review, tidak diubah otomatis. |
| Frame adalah fungsi waktu absolut | `__seek(t)` mengatur semua properti visual. Tidak ada random, integrasi simulasi, CSS animation berjalan sendiri atau state gerak kumulatif. |
| Bukti kontinuitas | Renderer mengukur identitas, kotak, perpindahan pusat dan perubahan ukuran carrier pada dua sisi setiap transisi yang ditulis. Semua batas yang diharapkan dicatat, termasuk bila jumlah batas nol. |
| Seek harus bisa diulang | Screenshot pada satu titik tengah diulang setelah seek ke titik lain; hash piksel dibandingkan. Laporan menyebut titik uji, bukan klaim uji seluruh waktu. |
| Manusia tetap menilai film | Dua approval dipertahankan; laporan geometri tidak menjadi penilaian semantik/estetika atau jaminan kualitas. |
| Draf sebelum biaya tinggi | MP4 30 fps pada rasio yang dipilih, satu browser, streaming satu PNG per frame ke FFmpeg. Tidak menimbun seluruh frame di RAM. |

Di menu ini output saat ini adalah **diagram vektor prosedural**. Field visual menjadi arahan/beat sheet, bukan generator bebas yang mampu menggambar apa pun dari prompt. Konsep menentukan kosakata visual yang didukung. Teks diambil dari rencana; arahan abstrak tidak disulap menjadi rekaman UI produk.

## Keamanan dan kompatibilitas

- Template dibuat backend; pengguna memasok data, bukan HTML/JavaScript. JSON meng-escape delimiter markup, teks ditulis melalui `textContent`, warna/font memakai validasi brand yang sudah ada.
- CSP menolak koneksi/aset eksternal. Renderer hanya dapat meminta satu komposisi lewat server loopback temporer beralamat acak, memeriksa Host tepat, dan tidak menyajikan folder output atau konfigurasi. Unduhan, service worker dan request lain diblokir.
- Environment renderer/encoder memakai penyaringan credential provider yang sama dengan adapter lama. Tidak mengambil akun browser, cookies, profil pengguna, URL produk privat atau font remote.
- Browser sandbox tetap aktif pada penggunaan normal. Opt-in tanpa sandbox hanya dipakai tes cloud terisolasi; tidak menambahkan flag tersebut ke launcher pengguna.
- Ukuran/durasi dibatasi, FFmpeg menerima argumen tetap tanpa shell; encoder memakai dua thread, ada timeout dan pembersihan file sementara. Tidak ada antrean baru.
- Manifest suara tidak mengaku mempunyai voice track pada mode musik. Review final terikat SHA256 MP4, laporan gerak juga mencatat hash komposisi. Paket produksi membawa snapshot plan/review, bukan source skill atau credential.
- Path file Windows/UNC kini menghasilkan nama file saja saat dibuat label sumber Clipper di Linux; path folder pribadi tidak ikut label.

## Batas yang sengaja dilaporkan

Ini **bukan seluruh OneTake**: tidak mengimpor 39 gerakan, template film, replika UI dari screenshot, simulasi fisika, native 3D, forced alignment, lokalisasi time-warp, mastering suara berbasis rekaman, shutter motion blur atau output final 4K60. Render memakai satu sampel per frame. Gerakan cepat dan blur belum dievaluasi setara renderer OneTake.

Probe mengukur carrier yang dideklarasikan, bukan seluruh elemen atau pengertian cerita. Identitas yang sama tidak membuktikan hubungan semantik; teks dan kontinuitas tetap harus dilihat. Layout diperiksa pada midpoint adegan, bukan semua frame. Keberhasilan pada video uji tidak menjamin throughput atau GPU di laptop pengguna.

## Sumber dan rekomendasi yang ditinjau

- **OneTake**, commit `013a61ac8d98883c73733f59c06e49e9ba444f14`: SKILL, README, LICENSE, references composition/rhythm/reference-deconstruction/motion-library/product-demo/3d/sound. Kode/aset berlisensi **PolyForm Noncommercial 1.0.0**; README menyatakan pemakaian komersial memerlukan lisensi tersendiri. Studi prinsip tidak menjadi klaim lisensi untuk menyalin implementasinya.
- **Motion** (`motiondivision/motion`), commit `7415b6cd14dfdb35d91dfc5b9758994444cc228b`: README dan LICENSE.md (MIT). Relevan untuk spring/layout/timeline; tidak dipasang karena adapter baru membutuhkan seek absolut yang sederhana tanpa CDN/bundler. Link agent skill `motiondivision/ai-kit` tercantum sebagai rekomendasi upstream; installer `npx motion-ai` tidak dijalankan atau dianggap sudah terintegrasi.
- **Three.js** (`mrdoob/three.js`), commit `8086b3fda07a70bffad7ee39265c9617994ec482` pada dev: README dan rekomendasi dokumentasi. Relevan untuk ekspansi 3D; adapter Three.js lama dipertahankan. Tidak menjadikan contoh GPU Apple dalam OneTake sebagai bukti kompatibilitas GPU Windows.
- **KreasiPintar**, `https://kreasipintar.com/am/1#hasil`: upaya baca 2 November 2026 ditolak proxy cloud **403**. Tidak menyimpulkan fitur atau kualitas hasil halaman yang belum terbaca. Parameter pelacakan iklan tidak diperlukan untuk studi halaman.

Bukti uji dan status CI terbaru dicatat pada dokumen status sesi ini; jangan mengganti status belum diuji dengan janji kesetaraan produk.

## Bukti otomatis dan render nyata

- Sebelum perubahan, main `d015bb3` divalidasi ulang: 106 tes dashboard lulus; Clipper 201 lulus/1 gagal akibat separator Windows pada label sumber. Masalah tersebut diperbaiki, bukan disembunyikan dengan melewati tes.
- Regresi final mencakup tes dashboard baru untuk konsep/beat sheet, metadata edit dan approval, HTML aman, server komposisi satu file/Host, isolasi mode audio dan pipeline MP4 offline nyata; angka suite/CI final ada di status sesi.
- Contoh UI 15 detik berhasil: 1080×1920, 450 frame/30 fps, satu browser, sekitar **148,1 detik** di cloud Linux saat tes lain juga berjalan. Bukan estimasi kinerja laptop Windows.
- Dua batas diukur carried; repeat piksel pada 7,5 detik identik; geometri/teks tidak bermasalah pada sampel; MP4 lulus media checks (-15,2 LUFS, true peak -1,5 dBFS). Musik memiliki jeda terukur.
- Analisis file encoded: 149 sampel luminansi 10 fps pada lebar160; 85,91% berperubahan rendah pada ambang rata-rata 0,1/255. Ini area average resolusi kecil; dapat melewatkan objek kecil dan tidak menjadi ukuran estetika.
- Browser berhasil mendekode, seek dan **memutar maju** MP4 15 detik; ketiga konsep juga diuji ulang pada preview dengan batas carrier dan repeat piksel.
- Hasil JSON terukur: [continuous-motion-20261102.json](benchmarks/continuous-motion-20261102.json). Media/pekerjaan uji tinggal di `.data/benchmarks/`, tidak masuk Git atau konfigurasi pengguna.
