# Diagnosis visual baseline 900e06f

## Buat Klip

- Komposisi masih berupa form linear lebar tunggal. Area kanan desktop kosong, sehingga tidak ada focal point visual atau gambaran hasil 9:16.
- Stepper tujuh kotak terlalu dominan dan menyerupai wizard administratif. Stepper juga menjanjikan tahap yang tidak terlihat pada state awal.
- Header global menggandakan CTA `Buat Klip` saat pengguna sudah berada di halaman tersebut.
- Source input tidak cukup menonjol. CTA `Lanjut` tidak menjelaskan efek berikutnya dan bersaing dengan CTA sticky `Buat Kandidat` yang tetap terlihat meski source kosong.
- Teks mode hemat terlalu panjang dan lebih dominan daripada keputusan utama.
- Template bar terpisah sebagai kartu besar tanpa konteks. Pada mobile, template dan CTA render muncul jauh dari source serta membuat halaman terkesan terpotong.
- Semua kelompok memakai border, radius, dan surface serupa. Hirarki visual datar dan terasa seperti dashboard form.
- Mobile 390x844 mencapai 1194 px dan 360x800 mencapai 1291 px bahkan pada state kosong. Navigation bawah menutupi sebagian konten dan CTA produksi tidak memiliki konteks kuat.

## Proyek

- Grid kartu membuat informasi operasional terlalu renggang. Delapan proyek mengambil dua baris besar dengan thumbnail kosong identik.
- Placeholder thumbnail berupa blok abu-abu tanpa identitas, status, atau fallback visual yang berguna.
- Search dan tab terpisah dari heading, tetapi belum ada filter status atau sort.
- Hapus selalu terlihat sebagai ikon kecil. Tidak ada quick action buka, lanjutkan, atau duplicate.
- Judul `Riwayat` tidak sesuai dengan navigasi `Proyek` dan mencampur model mental proyek dengan hasil.

## Hasil

- Hasil masih memakai struktur halaman Riwayat. Ready, Processing, dan Failed tidak dipisahkan.
- Kartu video hanya menampilkan skor, durasi, judul, dan proyek. Tidak ada tindakan Studio, folder, atau download yang terlihat.
- Lima preview berhenti di sisi kiri desktop, menghasilkan ruang kosong besar dan keseimbangan buruk.

## Studio picker

- Daftar berupa enam baris putih identik. Tidak ada thumbnail, readiness, status semantik, waktu, atau informasi kandidat.
- Seluruh lebar halaman dipakai untuk satu baris teks, menghasilkan density rendah dan focal point lemah.

## Studio proyek

- Preview 9:16 cukup besar, tetapi chrome editor terfragmentasi: toolbar atas, stage, inspector, candidate rail, dan render bar saling bersaing.
- Inspector masih terasa seperti form teknis. Layer chips dan preset memiliki border seragam serta tipografi kecil.
- Candidate rail memakai banyak kontrol dalam satu baris dan judul kandidat jatuh ke bidang input kecil.
- Preview error mempertahankan spinner dan teks gelap di atas bidang hitam, sehingga recovery state tidak jelas.
- Sticky render bar lebar mengambil ruang tetapi tidak merangkum aspect ratio, bahasa subtitle, style, dan jumlah output.

## Komposisi yang dibuang

1. Stepper tujuh kotak.
2. Layout source satu kolom dengan desktop whitespace kosong.
3. CTA sumber dan render yang tampil bersamaan pada state kosong.
4. Kartu template besar terpisah.
5. Grid proyek berbasis thumbnail placeholder kosong.
6. Studio picker berupa baris generik penuh.
7. Border dan radius seragam pada semua kelompok.

## Arah pengganti

- Workspace produksi dua kolom: keputusan source di kiri, preview 9:16 dan ringkasan workflow hidup di kanan.
- Rail progres ringkas, bukan kotak tahap.
- Source sebagai focal point, project name, recent source, inline validation, autosave state, quality preset, language, profile, dan recipe recommendation dalam satu alur scan.
- Recent projects sebagai strip kompak bawah.
- Proyek memakai list/table hybrid dengan filter, sort, progress, fallback thumbnail lokal, serta quick actions.
- Hasil memakai tab Ready, Processing, Failed dengan tindakan output nyata.
- Studio picker memakai kartu ringkas informatif. Studio proyek mempertahankan backend workflow sambil memprioritaskan preview dan memperjelas inspector serta render summary.
