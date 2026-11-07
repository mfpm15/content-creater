# Peningkatan awal Video Studio — 7 November 2026

## Reproduksi masalah
Video 30 detik, 1080×1920, 30 fps bertema gangguan siber pada penyimpanan darah memiliki enam shot dengan layout dominan seragam dan ilustrasi abstrak berulang. Audio MP4 berisi suara prosedural, bukan dubbing.

## Peningkatan dalam PR ini
- \`apps/video-studio-remotion/src/visual-treatment.mjs\` memilih treatment berdasarkan judul shot yang disetujui, kemudian subjek. Pilihan: kalender/kronologi, kantong darah, fasilitas, peringatan, keamanan, dokumen resmi, perangkat, figur, angka, dan diagram/cerita abstrak.
- \`apps/video-studio-remotion/src/Visuals.tsx\` menggambar artwork prosedural per treatment, dengan animasi deterministik mengikuti frame. Tidak membuat footage realistis atau gambar generatif.
- \`apps/video-studio-remotion/src/Studio.tsx\` memakai modul tersebut dan menambahkan atmosfer latar yang tidak bergantung pada wall-clock.
- \`voice_quality.py\` menolak keluaran Edge-TTS WAV yang rusak, kosong, atau mendekati senyap sebelum dicampur sebagai narasi. Pemeriksaan ini **tidak** menguji ketepatan teks/pelafalan atau kualitas natural suara; peninjauan manusia tetap diperlukan.
- \`test_voice_quality.py\` dan \`src/timeline.test.mjs\` menguji kegagalan suara dan pemilihan visual konkret.

## Cara mencoba setelah merge
1. Cadangkan karya Anda; setelah branch utama diperbarui, jalankan \`git pull --ff-only\`, \`setup-core.bat\`, \`start-dashboard.bat\`.
2. Buka **Video Studio**, pilih **Remotion Editorial**, rasio **9:16**, dan **Edge-TTS Bahasa Indonesia** (bukan mode tanpa suara).
3. Gunakan narasi dengan scene yang menjelaskan objek secara konkret. Review Scene Plan dan Storyboard sebelum menyetujui render.
4. Render satu video pendek. Periksa preview setiap shot, \`voice/*.wav\`, \`audio-mastering.json\`, \`render-report.json\`, dan hasil \`video.mp4\`.
5. Jika provider TTS mengembalikan \`NoAudioReceived\` atau WAV senyap, job harus **gagal dengan pesan eksplisit**. Jangan otomatis menggantinya dengan suara prosedural lalu mengklaim dubbing sukses.

## Batas dan pekerjaan selanjutnya
Perubahan ini **tidak** memasang RAEA, ComfyUI, library footage, skill efek viral, atau provider TTS kedua. Perbaikan visual dibatasi pada grammar ilustrasi SVG editorial. Agar mencapai kualitas cinematic yang lebih tinggi, perlu pipeline asset nyata, shot-by-shot direction, transisi kompleks, sound design, dan evaluasi hasil sesungguhnya. Peninjauan kualitas visual serta keberhasilan Edge-TTS pada laptop Windows belum dilakukan pada saat PR dibuat.

## Uji
- \`python -m unittest discover -s creator-dashboard -p "test_voice_quality.py"\`
- \`python -m unittest discover -s creator-dashboard -p "test_speech_settings.py"\`
- \`cd creator-dashboard/apps/video-studio-remotion && npm ci --ignore-scripts && npm run typecheck && npm test\`
- Uji render nyata dan dengarkan narasi pada Windows sebelum merge.
