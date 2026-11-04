# Suara gratis tanpa musik otomatis

Video Studio menggunakan klien **Edge-TTS 7.3.1**, bukan model TTS berbayar. Versi ini terpasang pada runtime suara audit dan kini dipin pada `setup-core.bat`. [Proyek Edge-TTS](https://github.com/rany2/edge-tts) menjelaskan pemakaian layanan suara daring Microsoft; [rilis PyPI](https://pypi.org/project/edge-tts/) menjadi acuan versi klien. Tidak membutuhkan API key berbayar; tetap memerlukan koneksi layanan.

## Perilaku pekerjaan baru

- Default narasi Bahasa Indonesia: `id-ID-ArdiNeural`, rate natural `+0%`.
- Pilihan Inggris: `en-US-GuyNeural`, rate `+0%`.
- Pilihan tanpa suara disediakan agar produksi visual dapat berjalan tanpa TTS.
- Musik dan foley tidak dibuat/dicampur otomatis. Sound cue pada arahan scene tetap dapat menjadi catatan produksi, tetapi audio manifest pekerjaan baru mematikan musik dan cue tersebut.
- Bahasa pilihan masuk prompt narasi baru dan pemilihan suara. Naskah pengguna yang telah diberikan tetap utuh, tidak diterjemahkan diam-diam.
- MP4 membawa narasi saja. JSON Lottie tidak menyematkan audio; tersedia WAV narasi terpisah melalui hasil dan bundle ketika TTS dipilih.
- Suara disintesis per scene, diperiksa durasinya dan diposisikan berdasarkan detik scene. Suara yang melebihi slot tetap ditolak sebelum render visual; tidak dipotong atau dipercepat diam-diam.
- Edit bahasa/mode membatalkan review terkait dan paket prompt sesuai alur yang sama; pengaturan bertahan pada checkpoint dan varian rasio. Klien editor lama yang belum mengirim field baru mempertahankan pengaturan job.

`legacy` plan tanpa `speech` tetap dibaca dengan perilaku lamanya. Pilihan musik eksplisit dari klien API lama dipertahankan untuk kompatibilitas; UI baru hanya menawarkan narasi/tanpa suara. Tidak memodifikasi atau merender ulang hasil lama.

## Implementasi

`speech_settings.py` mengizinkan dua bahasa, mode tts/none, provider edge dan voice yang ditentukan. Provider berbayar, voice/rate bebas dan musik aktif ditolak. Pengaturan ini dipasang sesudah respons planner agar model tidak dapat mengganti penyedia suara.

`speech_worker.py` adalah worker asli dashboard, memakai runtime venv suara yang sudah ada. Worker membaca input JSON terbatas, memvalidasi ID scene, memakai proxy dan CA sesi yang diwariskan dengan verifikasi TLS tetap aktif, menulis berkas sementara dan membersihkannya bila gagal. Core installer mengunci 7.3.1; konfigurasi CA tambahan menggunakan context pustaka versi tersebut. Tidak menulis credential, tidak memutar audio dan tidak menyediakan fallback berbayar.

Narasi disejajarkan dan dimaster melalui jalur FFmpeg yang sama tanpa memanggil generator musik. Mode none menghasilkan track senyap yang ditandai `intentionally_silent`; review tidak mengklaim loudness track ini terukur atau gagal hanya karena pengguna memilih tanpa suara.

## Bukti dan batas

- Katalog suara daring berhasil dikueri melalui proxy/CA: Ardi, Gadis dan Guy tersedia; pilihan default memakai Ardi/Guy.
- Uji sintesis langsung Indonesia dan Inggris melalui layanan saat audit menghasilkan `NoAudioReceived`. Sintesis neural nyata belum terbukti berhasil pada lingkungan ini. Error dilaporkan; tidak diganti musik atau layanan berbayar. Ketersediaan katalog bukan bukti sintesis berhasil.
- Tes audio menggunakan worker yang dimock untuk mengeluarkan WAV nada sintetis, lalu FFmpeg alignment/loudness nyata. Memeriksa voice terpilih, durasi akhir, dan tidak adanya track musik. Ini uji pipeline, bukan penilaian kualitas suara neural manusia.
- Tes lain memeriksa default/language, penolakan provider berbayar, brief bahasa, pelestarian naskah, edit/varian, mode senyap dan penolakan ID path sebelum akses jaringan.
- UI/HTTP dan suite dashboard diuji terpisah. Native Windows dan kualitas dengar belum diverifikasi; tidak memutar media sesuai instruksi pengguna.

Validasi akhir: 177 tes dashboard lulus, smoke UI/HTTP lulus. Uji penerimaan pipeline dua approval menghasilkan MP4 Remotion 320×568/60 fps, audio sengaja senyap sesuai pilihan none, tanpa file musik. Bukti: `docs/benchmarks/speech-20261104.json`. Sintesis neural langsung tetap belum terverifikasi.
