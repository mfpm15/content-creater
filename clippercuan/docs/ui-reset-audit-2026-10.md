# Audit reset frontend Clipper Cuan

Tanggal inspeksi: 27 Oktober 2026
Commit baseline: `4cf023af8941e882d4220d625c7a7344314a33dd`
Runtime: `http://127.0.0.1:8765`

Screenshot runtime disimpan lokal dalam `.ui-audit/baseline/`. Direktori tersebut tidak boleh dilacak Git.

## Cakupan audit

Baseline diambil pada empat viewport:

- 1440 × 900
- 1280 × 800
- 768 × 1024
- 390 × 844

Tujuh area diperiksa pada setiap viewport:

- Beranda
- Produksi Baru
- Proyek
- Antrean
- Hasil
- Studio
- Pengaturan

Total baseline: 28 screenshot full-page.

## Penyebab struktural dua redesign sebelumnya tetap buruk

### 1. Model informasi masih memakai admin dashboard

Sidebar mempertahankan tujuh tujuan permanen: Beranda, Proyek, Produksi Baru, Antrean, Hasil, Studio Lanjutan, dan Pengaturan. Antrean serta Hasil sebenarnya merupakan dua state dari pekerjaan produksi yang sama. Pemisahan ini menambah keputusan navigasi tanpa menambah kemampuan.

Beranda masih memakai hero, statistik hasil, antrean, preset, dan status sistem. Halaman tersebut menjelaskan produk, tetapi tidak langsung menyelesaikan tugas utama pengguna: memasukkan sumber dan membuat klip.

### 2. Produksi Baru tetap berupa wizard kaku

Produksi Baru membagi keputusan ringan menjadi enam layar: Sumber, Bahasa, Profil, Kandidat, Caption, dan Review. Pengguna harus menekan `Lanjut` berulang walaupun pilihan bahasa dan profil hanya membutuhkan satu interaksi.

Terdapat dua CTA `Lanjut` pada tahap sumber: satu di samping input URL dan satu lagi pada footer wizard. CTA ganda membuat hierarki aksi tidak tegas.

Stepper enam kolom mengambil lebar besar pada desktop. Pada mobile hanya empat tahap pertama terlihat. Caption dan Review keluar viewport horizontal tanpa petunjuk jelas.

Ringkasan desktop memakai kolom samping yang mengurangi lebar input utama. Pada mobile ringkasan dipindahkan menjadi kartu tinggi setelah tombol navigasi, menambah scroll tanpa membantu keputusan saat ini.

### 3. Progressive disclosure hanya menyembunyikan panel lama

Markup tetap memuat recipe, auto-render, template, sembilan profil, durasi, transcriber, layout, caption, title, watermark, dekorasi, musik, dan render action dalam satu template besar. Wizard hanya menambah `wizard-hidden` pada kelompok lama. Struktur informasi lama tidak benar-benar dibuang.

Akibatnya JavaScript mengelola dua model sekaligus: form panjang dan wizard enam tahap. State, summary, hidden groups, advanced mode, dan tombol sumber saling bergantung. Kompleksitas ini membuat perubahan visual berikutnya mudah kembali menjadi tambalan.

### 4. Style lama ditumpuk, bukan diganti

`style.css` memiliki sistem visual awal, aturan Studio gelap, lalu blok `CALM WORKSPACE REDESIGN` yang mengoverride aturan sebelumnya. Token radius berubah dari 18 px menjadi 12 px, warna aksen berubah, sidebar berubah, tetapi aturan lama tetap aktif pada selector yang tidak dioverride.

Dampaknya:

- Studio masih memakai stage gelap berpola titik dan inspector gradient gelap.
- Beberapa komponen memakai radius, shadow, density, serta warna berbeda.
- Responsive behavior tersebar pada beberapa media query yang saling menimpa.
- Perbaikan berikutnya sulit diprediksi karena cascade membawa keputusan desain lama.

### 5. Mobile masih memakai drawer desktop

Pada mobile sidebar desktop diubah menjadi drawer selebar maksimal 300 px. Top bar tetap memuat tombol menu, status AI, dan CTA Buat Klip. Struktur ini memakai dua lapis navigasi untuk empat area inti yang seharusnya cukup memakai bottom navigation.

Produksi mobile menunjukkan:

- heading besar sebelum tugas aktif;
- stepper horizontal terpotong;
- source card, CTA, storage explanation, wizard navigation, lalu summary tersusun vertikal;
- banyak ruang terpakai sebelum language/profile muncul;
- pengguna harus scroll panjang untuk pilihan sederhana.

### 6. Studio belum menjadi creative workspace

Route Studio hanya menampilkan daftar proyek datar berisi judul, jumlah klip, status mentah, dan tautan `Buka studio`. Tidak ada thumbnail, resume context, atau preview.

Saat proyek dibuka, Studio menampilkan preview, inspector tiga tab campuran, strip kandidat penuh filter, metadata, dan footer render sekaligus. Inspector mencampur recipe, font, caption, format, kualitas, hook, branding, efek, dan metadata. Preview bersaing dengan panel 380 px serta toolbars padat.

Nama tab `Instant style`, `Clip setting`, dan `Branding & efek` tidak mengikuti mental model editing yang diminta: Caption, Frame, Dekorasi, dan Audio.

### 7. Kandidat terlalu kecil dan terlalu teknis

Candidate strip memakai thumbnail horizontal kecil. Hook, transcript excerpt, alasan pemilihan, profile fit, dan score breakdown hanya tersedia setelah kandidat dibuka melalui inspector. Pengguna tidak dapat membandingkan dua atau tiga kandidat secara langsung.

### 8. Hierarki dan whitespace tidak seimbang

Desktop memakai content max-width besar, sidebar 224 px, padding main 32 px, dan summary 260 px. Area tugas sumber terlihat kecil dibanding ruang kosong layar.

Studio picker memakai baris penuh selebar konten dengan informasi sangat sedikit. Banyak whitespace horizontal tidak membentuk hierarki atau membantu scanning.

Pada mobile, whitespace berubah menjadi scroll vertikal karena setiap bagian lama dijadikan kartu penuh.

### 9. Typography dan target sentuh belum konsisten

Teks metadata dan eyebrow masih berada sekitar 9–12 px. Beberapa tombol `.sm` minimum 40 px, di bawah target sentuh 44 px. Segmented controls dan filter Studio juga memakai ukuran kecil.

Simbol Unicode dan emoji masih dipakai pada download, hot status, manual clip, crop, caption editor, dan status auto. Ikon belum menjadi sistem SVG inline yang konsisten.

### 10. Loading screenshot membuktikan readiness tidak eksplisit

Screenshot CLI awal untuk Beranda menangkap state `Menyiapkan workspace...` walaupun navigasi sudah tampil. Tidak ada selector readiness atau state skeleton per bagian. Validasi visual dapat salah menilai layout bila hanya menunggu page load.

## Kontrak perilaku yang harus dipertahankan

### Bootstrap dan registry

- `GET /api/info`
- `GET /api/health`
- `GET /api/settings`
- `GET /api/profiles`
- `POST /api/profiles/preview`
- `GET /api/recipes`
- `GET /api/templates`
- `GET /api/system`

### Source dan project creation

- URL tunggal atau banyak URL
- upload file melalui `POST /api/upload`
- payload `POST /api/projects` berbentuk `{ source, settings }`
- language Auto, ID, EN, dan nilai legacy lain tetap diterima
- content profile registry dan fallback Auto tetap dipertahankan
- `duration_preset`, recipe, storage mode, subtitle, caption, crop, quality, dan manifest lama tetap kompatibel

### Candidate workflow

- `GET /api/projects/{pid}`
- `POST /api/projects/{pid}/candidates/select`
- `POST /api/projects/{pid}/candidates/top/{count}`
- `POST /api/projects/{pid}/candidates/{cid}/action`
- `POST /api/projects/{pid}/rerank`
- `GET /api/projects/{pid}/candidates/manifest`

### Render dan lifecycle

- `POST /api/projects/{pid}/batch-render`
- `POST /api/projects/{pid}/settings`
- `POST /api/projects/{pid}/rerender`
- `PATCH /api/projects/{pid}/clips/{cid}`
- `POST /api/projects/{pid}/clips`
- `DELETE /api/projects/{pid}/clips/{cid}`
- cancel, retry, resume, open folder, ZIP, manifest, dan export

### Caption workspace

- subtitle ID/EN dan source metadata
- words endpoint
- caption workspace GET, PUT, action
- caption templates
- glossary, revision, cue timing, preview, serta safe-area behavior

### Settings

- LLM/9Router
- cloud ASR
- download cookies browser
- automation webhook, inbox, dan export directory
- local fallback tanpa AI eksternal

## Arah reset

Frontend baru harus memakai empat area inti:

1. Buat Klip
2. Proyek
3. Hasil
4. Studio

Pengaturan menjadi secondary action. Antrean bergabung dengan Hasil.

Default route langsung membuka workspace source. Language dan empat profile utama baru muncul setelah source valid. Kandidat, style, preview, dan render action muncul progresif dalam workspace yang sama.

Desktop memakai rail ringkas serta workspace dominan. Mobile memakai bottom navigation empat item tanpa drawer bertingkat.

Studio memakai preview 9:16 dominan, optional scene rail, inspector 320–380 px dengan Caption, Frame, Dekorasi, dan Audio, serta transport ringkas. Metadata teknis dipindahkan ke modal Detail.
