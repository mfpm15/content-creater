# Video Studio Faceless — implementasi awal (7 November 2026)

## Status: template grafis + motion + narasi; bukan generator video realistik tanpa batas

- Pengguna dapat memilih satu dari **12 preset visual** melalui **Video Studio**. Template memilih Remotion, palet warna, layout (headline/split/poster/center) dan profil motion (technical/cinematic/kinetic/calm/urgent/minimal).
- Desain masing-masing template dipasangkan ke manifest render yang divalidasi. Preset lama tanpa template menggunakan layout editorial agar project lama tetap terbuka.
- Brief/topik dapat diubah menjadi naskah & scene plan oleh planner 9Router **bila provider lokal aktif**, lalu diperiksa pengguna pada scene plan dan storyboard. Mode naskah sendiri tidak menghubungi AI.
- Edge-TTS Bahasa Indonesia merupakan opsi dubbing default, **memerlukan akses provider jaringan yang berfungsi**. WAV kosong/rusak/terlalu senyap ditolak oleh pemeriksaan audio, bukan diganti dengan musik sambil disebut narasi.
- Tidak ada footage model AI/stock video otomatis pada perubahan ini. Ilustrasi Remotion masih berasal dari visual procedural yang terbatas. Judul yang tidak mempunyai simbol sesuai tetap membutuhkan media nyata atau ilustrasi khusus untuk kualitas premium.

## Cara memakai

1. Buka **Video Studio** di Creator Control Center. Pilih salah satu kartu template (atau filter **Genre**).
2. Masukkan topik/judul. Pilih mode **Planner** hanya jika provider 9Router yang Anda konfigurasi tersedia; untuk jalur offline gunakan **Naskah sendiri** dengan narasi.
3. Pilih aspek **9:16**, durasi **30–60 detik**, dan **Edge-TTS Bahasa Indonesia**. Template otomatis menggunakan adapter Remotion; jangan ubah ke adapter lain kecuali melepas template.
4. Review naskah, scene plan, cek preflight **Konten Faceless** serta adegan sebelum menyetujui storyboard. Peringatan tidak memblokir render secara otomatis.
5. Setelah render, dengarkan dubbing, lihat preview seluruh shot dan periksa musik/SFX, lalu ekspor. **Jangan otomatis publikasi** tanpa pemeriksaan fakta, hak pakai aset, dan kebijakan konten sintetik platform.

## Kualitas konten dan monetisasi

YouTube menegaskan konten mass-produced/repetitif tanpa komentar, narasi, atau nilai original dapat tidak memenuhi syarat monetisasi. Template tidak boleh menjadi satu-satunya unsur unik video. Konten faceless yang baik perlu cerita orisinal, poin informatif, perspektif/konteks unik, sumber, dan komposisi visual yang sesuai dengan narasi.

- Kebijakan YouTube: https://support.google.com/youtube/answer/1311392?hl=id
- Pengungkapan konten sintetik realistis: https://support.google.com/youtube/answer/14328491?hl=id
- Aset bebas unduh tidak selalu boleh digunakan sebagai endorsement atau dipublikasikan ulang sebagai aset mentah; periksa lisensi tiap footage/audio.

**Tidak ada jaminan pendapatan.** Monetisasi bergantung pada kelayakan akun, orisinalitas, performa penonton, serta kebijakan platform.

## Repository yang diperiksa untuk roadmap berikutnya

| Repository | Status | Lisensi toolkit | Keputusan |
|---|---|---|---|
| https://github.com/remotion-dev/skills | Referensi praktik terbaik React/Remotion | Periksa per file saat mengambil komponen | Pelajari best practices, jangan install duplikat renderer |
| https://github.com/Vincentwei1021/video-shotcraft | Koleksi shot dan motion sinematik | Apache 2.0 pada root LICENSE | Kandidat penambahan efek bertahap setelah review provenance aset |
| https://github.com/Vibha-Ramprakash/claude-video-effects | Efek Python/OpenCV/FFmpeg | MIT pada root LICENSE | Adapter eksternal potensial, belum dipasang |
| https://github.com/iart-ai/motion-skills | Resep motion AI | MIT pada root LICENSE | Referensi teknik dan timing |
| https://github.com/moshspro-dev/video-effect-reel | Resep efek video | MIT pada root LICENSE | Katalog ide, bukan renderer |
| https://github.com/Vincentwei1021/video-talkcraft | Voiceover-synced video skill | PolyForm Noncommercial | **Tidak disalin** ke proyek komersial tanpa izin penulis |
| https://github.com/shinyobjectz/raea | GPU/Bevy motion graphics engine | FSL 1.1 -> Apache 2.0 pada change date | Integrasi terpisah setelah evaluasi batas lisensi dan kestabilan canary |

**Tidak** mengunduh/menggandakan kode, footage, musik atau model AI dari repository di atas pada PR ini.

## Acceptance testing

- `python -m unittest discover -s creator-dashboard -p "test_video_templates.py"`
- `python -m unittest discover -s creator-dashboard -p "test_faceless_quality.py"`
- `python -m unittest discover -s creator-dashboard -p "test_speech_settings.py"`
- `cd creator-dashboard/apps/video-studio-remotion && npm run typecheck && npm test`
- `test_opuscar_layout.py` di Windows CI (uji judul panjang dan 5 ukuran canvas)
- Uji lapangan: render dua template berbeda dari naskah yang sama, dengarkan dubbing Bahasa Indonesia, periksa timing/subtitle, dan buka hasil MP4 di HP.

## Tahapan berikutnya (belum diimplementasikan)

1. Media bin internal: import asset pengguna + metadata sumber dan lisensi; sandbox file dan validasi MIME/durasi/ukuran.
2. Provider stock footage dengan API key milik pengguna, cache, rate limit, dan catatan lisensi per klip. Tidak mengunggah rekaman atau naskah ke pihak ketiga tanpa izin.
3. Compositing mixed-media nyata pada renderer untuk footage, ilustrasi, text effects, dan voice-over yang diikuti timestamp audio.
4. Review multi-frame menggunakan metrik teknis dan penilaian kreatif manusia; optimasi berdasarkan video yang disetujui.
5. Perluasan efek dari library MIT/Apache setelah memeriksa lisensi aset turunannya; RAEA opsional ketika kompatibilitas binary Windows stabil.
