# Domain Context

## Workflow Produksi Animasi

Workflow Produksi Animasi mengubah brief pengguna menjadi hasil animasi melalui empat tahap eksplisit:

1. **Brief** — topik, narasi, format, durasi, Render Adapter, gaya, dan model.
2. **Scene Plan** — pembagian adegan, narasi, visual, teks layar, waktu, serta sound cue. Pengguna harus menyetujuinya sebelum Storyboard dibuat.
3. **Storyboard** — kartu visual per adegan yang memuat motion direction, easing, komposisi, dan transisi. Versi pertama hanya mendukung persetujuan atau kembali merevisi Scene Plan.
4. **Render** — Render Adapter menghasilkan artefak akhir setelah Storyboard disetujui.

## Motion Plan

Motion Plan adalah kontrak bersama antara perencana dan Render Adapter. Setiap adegan memiliki timing, visual intent, motion direction, easing, transition, narration, on-screen text, dan sound cue. Kontrak ini tidak bergantung pada renderer tertentu.

## Render Adapter

Render Adapter menerjemahkan Motion Plan menjadi artefak animasi:

- **Opuscar/GSAP Adapter** menghasilkan preview HTML dan MP4.
- **Lottie Adapter** menghasilkan preview web dan `lottie.json`.
- **Three.js Adapter** direncanakan untuk tahap berikutnya dan harus memakai seam Render Adapter yang sama.

## Model Routing

Model Routing memilih model perencana melalui endpoint OpenAI-compatible yang berjalan di backend. Gemini dan GPT adalah pilihan utama. Claude tetap tersedia sebagai pilihan tambahan. Kredensial tidak pernah dikirim ke browser.
