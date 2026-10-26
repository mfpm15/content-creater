# Clipper Cuan: Viral Short-Form Playbook

Tanggal akses sumber: **26 Oktober 2026**. Dokumen ini memisahkan ketentuan/best practice platform dari heuristik internal Clipper Cuan. Tidak ada klaim bahwa suatu klip pasti viral.

## Sumber resmi dan insight yang diterapkan

### YouTube Shorts

1. **Understand three-minute YouTube Shorts**
   URL: https://support.google.com/youtube/answer/15424877
   Penerapan: pipeline tidak mengasumsikan Shorts selalu 10 detik. Preset produk tetap 15–60 detik untuk fokus repurpose, sementara validator memahami batas platform lebih luas. Durasi Auto memilih rentang sesuai struktur ide dan tidak memotong tengah kalimat.
2. **Tips to create YouTube Shorts**
   URL: https://support.google.com/youtube/answer/12948448
   Penerapan: hook awal, konten ringkas yang dapat berdiri sendiri, original audio, serta iterasi tanpa janji performa.
3. **Use automatic captioning**
   URL: https://support.google.com/youtube/answer/6373554
   Penerapan: subtitle hasil ASR diperlakukan sebagai draft yang dapat diedit. Warning muncul saat confidence transkrip rendah.

### TikTok for Business / Creative Center

4. **Creative best practices for performance ads**
   URL: https://ads.tiktok.com/resources/help/article/creative-best-practices
   Penerapan: struktur hook–body–close, komposisi vertikal, teks terbaca, safe area, dan perubahan visual secukupnya. Rekomendasi iklan tidak disamakan dengan jaminan performa organik.
5. **TikTok One Creative Suite / Creative Center**
   URL: https://ads.tiktok.com/creative/creativeCenter
   Penerapan: sumber belajar tren untuk observasi format/topik, bukan untuk menyalin aset atau membuat klaim popularitas tanpa data yang tersimpan.

### Instagram / Reels

6. **Ukuran & rasio aspek reel di Instagram**
   URL: https://www.facebook.com/business/help/1038071743007909
   Penerapan: output utama 9:16 1080×1920, area caption dijauhkan dari tepi, crop punya fallback tengah, dan warning muncul saat confidence crop rendah.

### Caption dan aksesibilitas

7. **Captions/Subtitles**, W3C Web Accessibility Initiative
   URL: https://www.w3.org/WAI/media/av/captions/
   Penerapan: caption mempertahankan ucapan, timing tidak overlap, punctuation/frasa menjadi batas cue, outline/shadow dan kontras dipertahankan, serta SRT disediakan terpisah.

### Mobile Legends / MOONTON

8. **Mobile Legends: Bang Bang Terms of Service**, MOONTON Games
   URL: https://en.moonton.com/terms.html
   Penerapan: workflow menampilkan checklist hak sumber, musik, wajah/suara, dan attribution. Overlay Mobile Legends memakai bentuk generik buatan sendiri. Logo, hero art, map art, font game, atau aset internet tidak diunduh oleh aplikasi.
9. **Mobile Legends: Bang Bang official site**, MOONTON Games
   URL: https://www.mobilelegends.com/
   Penerapan: istilah profile dibatasi pada istilah gameplay umum yang benar-benar muncul di transkrip/metadata atau didukung sinyal yang tersedia. Sistem tidak mengarang kill, objective steal, Savage, hero, build, atau hasil pertandingan.

## Praktik per kategori

### Podcast clips

- Prioritas internal: hot take yang lengkap, pertanyaan-jawaban, konflik-resolusi, cerita mini, kutipan kuat, pergantian speaker, insight mandiri, dan akhir bersih.
- Template: single speaker, split speaker, lalu face crop tengah bila pelacakan wajah tidak yakin.
- Risiko konteks: kutipan pendek dapat mengubah maksud. Kandidat dihukum bila pembuka bergantung pada kalimat sebelumnya atau payoff terpotong.

### Review teknologi

- Prioritas internal: problem-solution, fitur mengejutkan, comparison, verdict, value/price consideration, demo result, pros/cons.
- Harga, spesifikasi, benchmark, dan klaim produk hanya boleh berasal dari transcript atau metadata sumber. Lower-third tidak mengisi data yang tidak ada.
- Kandidat dengan kepadatan informasi tinggi mendapat bobot lebih besar. Rights/context risk mengurangi skor, bukan memblokir workflow.

### Gameplay Mobile Legends

- Prioritas internal: clutch, outplay, team fight, comeback, objective, build/tip, reaction, funny fail, dan commentary insight.
- Visual activity mendapat bobot besar. Bila scene/audio detector tidak menyediakan bukti, label event hanya mengikuti transcript/activity hint dan warning tetap tampil.
- Overlay game-safe generik menjaga caption dan facecam menjauh dari area HUD. Tidak ada aset game eksternal yang ditambahkan.

## Fakta, heuristik, dan hipotesis A/B

- **Fakta platform:** rasio/output, dukungan caption, safe-area requirement praktis karena UI platform, serta aturan hak cipta mengikuti sumber platform resmi di atas.
- **Heuristik produk:** rentang 15–60 detik, skor 13 dimensi, MMR diversity, overlap suppression, sentence-boundary snapping, dan profile weights. Ini bukan aturan platform.
- **Hipotesis A/B:** opening question versus direct claim; caption Clean versus Bold; durasi 15–25 versus 25–40; single-speaker crop versus split-speaker; title benefit-led versus curiosity-led. Uji dengan data publikasi nyata milik user. Aplikasi tidak mengarang view, retention, revenue, atau hasil eksperimen.

## Best practice platform

- Gunakan format vertikal untuk pengalaman layar penuh bila targetnya Shorts, TikTok, atau Reels.
- Pastikan caption akurat dan dapat diperbaiki; caption otomatis tidak dianggap final.
- Jaga konten original serta hak penggunaan audio dan visual.
- Pakai safe area karena kontrol aplikasi platform dapat menutupi tepi layar.
- Nilai tren melalui sumber analitik resmi saat tersedia; jangan menyalin video, audio, atau materi kreator lain.

## Heuristik internal Clipper Cuan

Heuristik berikut adalah keputusan produk, bukan aturan resmi platform:

- **15–25 detik** untuk ujaran padat dan payoff cepat.
- **25–40 detik** untuk konteks sedang.
- **40–60 detik** untuk penjelasan tenang yang perlu menjaga ide utuh.
- Viral Readiness merupakan skor review transparan: hook, standalone clarity, payoff, novelty, emotion/humor, quotability, information density, visual activity, clean ending, profile fit, transcript confidence, crop confidence, dikurangi rights/context risk.
- Overlap suppression default 35% dari bagian terpendek. MMR sederhana menekan kemiripan semantik, lalu memberi bonus scene/speaker diversity. Nilainya dapat diubah di Advanced dan harus diuji.
- Preset caption: Clean, Bold Viral, Minimal, Karaoke. Semua memakai batas frasa/karakter, safe area, kontras, outline/shadow, dan timing non-overlap.
- Hashtag dibatasi pada kelompok niche/topic/format. Tag generik spam dan engagement bait tidak ditambahkan.
- Punch-in, reframing, emoji, dan motion harus subtil. Audio sumber dipertahankan dan loudness dinormalisasi secara aman.

## Checklist readiness sebelum publikasi

1. Hook 0–3 detik dapat dipahami tanpa konteks sebelumnya.
2. Klip berakhir pada kalimat/payoff utuh.
3. Klaim dalam judul dan caption didukung ucapan asli.
4. Caption tidak overlap, tidak keluar safe area, dan jumlah kata nyaman.
5. Wajah/subjek utama tetap di frame; cek manual bila crop confidence rendah.
6. Audio tidak clipping dan tetap memakai sumber asli.
7. Tidak ada aset internet berhak cipta yang ditambahkan.
8. Viral Readiness dibaca sebagai alat review, bukan prediksi pasti.
