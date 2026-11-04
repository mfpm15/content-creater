# Planner yang mengikuti kemampuan renderer

Perbaikan ini menutup perbedaan antara arahan produksi bebas dan kemampuan engine yang benar-benar tersedia. Sebelumnya planner dapat meminta objek/aksi yang tidak didukung; beberapa engine memakai fallback editorial dan Three.js belum menolak kombinasi objek/aksi yang tidak kompatibel sebelum audio. Opuscar baru menemukan sebagian masalah saat style-frame review.

`renderer_contract.py` sekarang menyediakan instruksi khusus untuk scene planner dan diagnostik yang dipakai saat review/pra-render. Instruksi tidak mengubah narasi pengguna atau memaksa topik menjadi objek mekanis yang tidak relevan.

| Engine | Kontrak yang dijelaskan kepada planner | Diagnostik |
| --- | --- | --- |
| Opuscar/GSAP | Grammar objek/aksi mekanis dan keluarga ilustrasi prosedural yang tersedia; angka literal | Error untuk visual tanpa implementasi/aksi tidak cocok; peringatan untuk scene data tanpa angka |
| Three.js | Geometri mekanis yang tersedia, kontrol kamera/lighting/transisi eksplisit; pelat editorial sebagai fallback | Error untuk aksi tidak cocok; fallback editorial dilaporkan, kecuali kinetic-type yang sengaja dipilih |
| Remotion | Diagram proses/perbandingan dengan label eksplisit; angka literal atau teks editorial | Peringatan bila label diagram atau angka yang dapat ditampilkan tidak tersedia |
| Lottie | Subset rectangle/ellipse/text/transform; diagram berlabel | Peringatan ketika proses/perbandingan tidak memiliki label diagram |
| Continuous | Konsep trace/focus/assemble, carrier dan hold | Error untuk konsep belum dipilih atau assemble melebihi 12 beat |

## Alur review dan render

- Scene Plan menyimpan `rendererReview` berisi mode render per shot, error dan peringatan. Editor menampilkan temuan sebelum pengguna menyetujui; setelah koreksi, tombol Simpan memperbarui pemeriksaan.
- Job pipeline2 dan varian baru menolak approval serta worker jika masih ada error kemampuan renderer, sebelum membuat audio/render. Kedua jalur memakai pemeriksaan yang sama. Peringatan tetap dapat ditinjau dan disetujui untuk penggunaan editorial yang disengaja.
- Paket prompt memuat diagnostik yang terikat digest revisi. Pesan keterbatasan per shot berasal dari temuan sebenarnya; ilustrasi Opuscar yang memang didukung tidak lagi salah disebut pelat editorial.
- Pemilihan fallback Opuscar dan ekstraksi metrik literal dipakai bersama generator/diagnostik/adapter Remotion. Tanda, desimal dan prioritas angka judul dipertahankan; angka tidak dikarang untuk mengisi visual kosong.
- Parser menerima token aksi resmi secara eksplisit. Ini memperbaiki `expand`, yang sebelumnya terdaftar tetapi memerlukan prosa tambahan agar terbaca; pasangan yang tidak kompatibel tetap ditolak.
- Instruksi audio mengikuti konfigurasi plan yang sedang dieksekusi. Izin pengguna untuk musik/SFX tetap berlaku, tetapi planner tidak boleh menjanjikan elemen yang tidak diaktifkan/diimplementasikan.

## Pengujian dan batas

Tes kontrak memeriksa semua pasangan objek/aksi yang diiklankan, kesesuaian diagnostik dengan markup Opuscar pada berbagai family/type, fallback Three.js, label diagram, konsep Continuous, data kosong, pemulihan setelah edit, serta penolakan API/worker sebelum audio. Regresi lain mencakup frame browser SDK nyata dan pipeline MP4 yang sudah tersedia.

Status supported hanya menyatakan cakupan implementasi yang dikenali. Ini bukan penilaian semantik, kebenaran fakta, estetika, fisika realistis atau keseluruhan kualitas film. Review storyboard/hasil masih diperlukan; tidak ada skor kualitas buatan. Status sintesis Edge daring sebelumnya belum berubah. Tidak memutar media atau merender ulang proyek lama.

Validasi akhir lokal: 186 tes dashboard lulus, compile/syntax/diff bersih, smoke HTTP dan UI lulus. UI menampilkan diagnostik, menolak approval saat ada error dan tetap mengizinkan simpan perbaikan. Regresi browser memakai SDK GSAP/Three.js nyata; pipeline Remotion/Continuous nyata tetap lulus. Workflow Windows diperluas, hasil run perubahan ini belum diverifikasi.
