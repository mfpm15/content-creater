# Video Studio 30/60 fps

Pekerjaan baru menggunakan **60 fps** pada Opuscar/GSAP, Three.js, Remotion, Continuous Motion dan ekspor JSON Lottie. Brief menyediakan pilihan 30 fps untuk render lebih ringan. Scene Plan/Storyboard juga menyediakan pemilihan fps; perubahan tetap membatalkan persetujuan dan review yang terkait.

Rencana lama tanpa field `fps` tetap 30 fps. Untuk mengubahnya, pilih 60 fps saat review lalu simpan dan setujui ulang sesuai alur. Tidak ada migrasi atau render ulang otomatis terhadap media lama. Varian rasio mempertahankan fps sumber.

Kontrak API: field integer `fps: 30 | 60` pada brief dan plan. Nilai lain ditolak. `frame_rate.py` menjadi sumber validasi bersama; default job baru 60, fallback plan/job lama 30. Model planner tidak menentukan fps: nilai brief diterapkan setelah respons model.

- Opuscar/Three.js: HTML menyimpan `data-fps`, HyperFrames menerima `--fps` yang sama dan menyampel clock absolut pada setiap frame.
- Remotion: manifest, shot/caption, batas maksimum 600 detik dan komposisi React menggunakan fps plan. Panjang transisi dipertahankan dalam detik.
- Continuous Motion: jumlah frame, timestamp seek dan encoder mengikuti fps plan. Cache tetap berdasarkan keadaan visual; setiap frame tetap dikirim ke encoder. Regresi membandingkan seluruh hash frame terdekode cache/tanpa cache pada 60 fps.
- Lottie: `fr`, `op`, timing layer dan keyframe menggunakan fps plan. Ramp 0,2 detik dan scale reveal 0,5 detik tidak menjadi dua kali lebih cepat pada 60 fps.
- Audio tetap berjalan dalam detik pada sample rate audio yang sama. Mux menyalin stream video tanpa menurunkannya ke 30 fps. Review membandingkan fps terukur dengan plan dan mencatat mismatch.

60 fps menambah sampel gerak, dengan waktu render/ukuran file tergantung komposisi. Frame yang memang ditahan diam tetap boleh identik; tidak ada klaim motion blur atau interpolasi footage lama.

Validasi lokal Linux: keempat MP4 1080×1920/60 fps memiliki 120 frame, audio AAC dan durasi 2 detik; ekspor Lottie `fr=60/op=120`. Player resmi Lottie 5.12.2 menghasilkan piksel identik antara 30/60 fps pada empat timestamp yang sama. Smoke UI membuktikan default brief60, review legacy30 dan edit60 tersimpan; smoke HTTP, TypeScript, 7 tes Node dan audit npm (0 vulnerabilities) lulus. Benchmark: `docs/benchmarks/studio-60fps-20261104.json`. Media fixture berada di luar repo; tanpa playback/provider TTS daring. Native Windows belum diuji pada perubahan ini dan harus diperiksa lewat run CI tersendiri.

Regresi akhir: **162 tes dashboard lulus**, termasuk pemeriksaan fps mismatch, default60 pada kelima adapter, serta seluruh frame cache60 dibandingkan tanpa cache. Tidak ada perubahan dependency atau data/media pengguna.
