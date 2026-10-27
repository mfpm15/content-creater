# Audit visual Clipper Cuan sebelum redesign

Tanggal inspeksi: 27 Oktober 2026

Artefak runtime diperiksa pada 1440x900, 1280x800, 768x1024, dan 390x844. Screenshot disimpan lokal di `.ui-audit/` dan tidak dilacak Git.

## Ringkasan kegagalan desain

Dashboard bukan gagal karena kekurangan dekorasi. Masalah utama adalah struktur informasi: halaman awal langsung menampilkan form produksi panjang, seluruh keputusan teknis, dan banyak kartu dengan bobot visual serupa. Pengguna tidak mendapat titik mulai yang jelas selain tombol `Run pipeline`, sementara istilah, navigasi, dan urutan proses bercampur antara Bahasa Indonesia dan English.

## Temuan konkret

### Hierarki dan primary action

- Heading `Satu link jadi puluhan klip siap upload` terlalu dominan, tetapi tidak diikuti ringkasan proyek atau konteks keputusan.
- `Run pipeline` muncul sebelum bahasa, profil, kandidat, dan gaya dipilih. Urutan visual tidak mencerminkan urutan kerja sebenarnya.
- Tombol aksi besar bersaing dengan border hijau terang pada kartu sumber. Border menjadi aksen kedua yang tidak bermakna.
- Health indicator berada sebagai pill besar di header dan mengambil perhatian lebih besar daripada konteks proyek.

### Density dan card overload

- Halaman awal memuat sumber, storage, recipe, auto render, kualitas, template, delapan tahap, sembilan profil, durasi, transkripsi, layout, caption, title, watermark, dekorasi, audio, dan CTA dalam satu halaman.
- Semua kelompok menggunakan card dan border hampir sama. Tidak ada pembedaan kuat antara keputusan wajib, opsional, dan informasi teknis.
- Pada desktop 1440x900, viewport pertama hanya mencapai awal recipe. Tugas utama belum dapat diselesaikan tanpa scroll panjang.
- Kartu recipe berisi deskripsi panjang dan lima opsi visual dalam satu baris. Teks sempit menghasilkan banyak baris dan tinggi kartu tidak seimbang.

### Spacing dan alignment

- Konten desktop terlalu lebar pada layar 1440 px. Baris input sumber dan tombol membentang hampir seluruh area, membuat pembacaan melelahkan.
- Padding kartu besar, tetapi jarak internal antarkontrol tidak konsisten. Beberapa heading memiliki ruang besar, lalu kontrol rapat.
- Pada 1280x800, kolom utama menjadi sempit karena sidebar 238 px dan padding horizontal 84 px. Textarea sumber membungkus placeholder secara buruk.
- Toggle storage berada jauh dari label pada desktop, tetapi terjepit di sisi kanan pada tablet dan mobile.

### Warna dan contrast

- Canvas memakai radial gradient biru, sementara kartu memakai border hijau limau dan tombol biru. Tiga aksen bersaing tanpa semantik konsisten.
- CSS masih memuat banyak warna dan efek lama seperti glow, neon, gradient, shadow besar, dan latar gelap studio. Hasil visual tidak konsisten dengan light-first dashboard.
- Beberapa teks sekunder terlalu kecil, terutama metadata 10-12 px dan label uppercase ber-letter-spacing besar.

### Navigasi

- Sidebar berisi delapan tujuan dengan istilah berbeda dari model kerja yang diminta. `Proyek baru`, `Transcript & Caption`, `Template gaya`, `Cek sistem`, `AI Agent & otomatisasi`, dan `Bantuan` bercampur antara area kerja dan utilitas.
- Ikon memakai karakter Unicode dan emoji yang tidak konsisten.
- Tablet/mobile mengubah sidebar menjadi baris horizontal di atas. Pada lebar 390 px, item terpotong dan pengguna harus scroll horizontal tanpa petunjuk.
- Tidak ada navigasi mobile bawah atau drawer yang jelas.

### Responsive dan scroll

- Screenshot 390x844 menunjukkan hanya kartu sumber. Pengguna harus melewati halaman sangat panjang untuk mencapai keputusan berikutnya.
- Heading mobile membungkus menjadi dua baris rapat. Health indicator mengambil baris sendiri di atas konten.
- Tombol `Run pipeline` menjadi full-width, tetapi muncul terlalu dini dan memberi kesan proses dapat dimulai sebelum konfigurasi selesai.
- Kartu storage terlalu tinggi pada mobile karena microcopy panjang dan toggle mengambang di tengah sisi kanan.
- Tablet menampilkan navigasi terpotong (`Transcript & Cap...`) dan tidak memberi akses jelas ke item lain.

### Riwayat/proyek

- Halaman riwayat memakai kartu thumbnail besar dengan informasi kecil di bawahnya. Banyak thumbnail placeholder ungu gelap mendominasi layar tanpa membantu identifikasi.
- Filter dan pencarian mengambang di kanan atas, terpisah dari judul dan grid.
- Status, jumlah klip, hapus, dan tanggal terlalu kecil. Target hapus tidak memenuhi 44 px.
- Judul proyek seperti `Memproses...` berulang, sehingga kartu sulit dibedakan.

### Studio

- Struktur memakai preview, inspector tiga tab campuran, strip kandidat, filter, dan footer render sekaligus. Inspector mencampur recipe, font, caption, format, kualitas, hook, branding, efek, dan metadata.
- Preview berada pada latar teknis gelap berpola dan banyak badge. Tampilan terasa sebagai debug workspace, bukan editor produksi.
- Metadata teknis tampil langsung di inspector dan klip, bukan disclosure `Detail teknis`.
- Primary render terdapat di footer, tetapi banyak aksi lain memiliki bobot visual serupa.

### Accessibility

- Banyak tombol kecil di bawah target sentuh 44 px, termasuk segmented controls, ikon hapus, navigasi preview, chip, dan filter.
- Focus ring memakai warna limau yang tidak cocok dengan aksen biru baru.
- Beberapa label bergantung pada simbol seperti `＋`, `▤`, `◧`, `◉`, `⚡`, dan `⚙`.
- Reduced-motion sudah ada, tetapi animasi, transition, dan pulse tersebar serta perlu disederhanakan.

## Arah perbaikan

- Pisahkan Beranda dari Produksi Baru. Beranda hanya memuat hero pendek, proyek terbaru, antrean ringkas, maksimal tiga preset, serta status service/storage kecil.
- Ubah Produksi Baru menjadi wizard enam tahap. Satu keputusan dominan per layar, state tersimpan, summary desktop, dan disclosure advanced.
- Ganti sidebar dengan tujuh tujuan yang benar-benar memiliki handler: Beranda, Proyek, Produksi Baru, Antrean, Hasil, Studio Lanjutan, Pengaturan.
- Gunakan canvas abu muda, surface putih, border halus, aksen indigo tenang, success teal, radius 12 px, dan spacing 4/8 px.
- Hilangkan gradient dekoratif, glow, shadow besar, dan panel teknis dari alur utama.
- Susun Studio menjadi preview dominan dan inspector Caption, Crop, Dekorasi, Audio, Export. Pindahkan metadata ke disclosure.
- Pertahankan semua endpoint, registry profile, recipe object, subtitle ID/EN, render, cancel, retry, open-folder, serta export sebagai sumber perilaku nyata.
