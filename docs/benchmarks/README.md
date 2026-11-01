# Benchmark publik dan studi produk — 1 November 2026

Dua hal diukur terpisah: kemampuan pipeline pada fixture publik, dan fitur yang disebut pada halaman produk. Tidak ada akun berbayar atau perbandingan kecepatan/kualitas hasil keenam layanan yang diuji.

## Hasil pipeline nyata

| Fixture | Acuan sumber | Pengukuran |
|---|---|---|
| `whisper-jfk.flac`, 11 detik | [openai/whisper, tests/jfk.flac](https://github.com/openai/whisper/blob/86098128c0b4f24f0e2aa2994de830614b474227/tests/jfk.flac) | Audio -12,5 LUFS, true peak -2,1 dBFS; tidak terdeteksi jeda ≥0,5 detik di bawah -40 dB. ASR/alignment **tidak dijalankan**. |
| `scenedetect-goldeneye.mp4`, durasi file 82,593 detik | [PySceneDetect resources](https://github.com/Breakthrough/PySceneDetect/blob/e68d06a78e5241d82300d4924a53629feecbcb6b/tests/resources/goldeneye.mp4) | Sampel frame 1199–1450 pada 24000/1001 fps (50,008–60,477 detik). Ditemukan 4 dari 5 cut acuan: precision 1,0; recall 0,8; toleransi ±0,12 detik. Audio diukur pada **seluruh file**, bukan hanya sampel. |

Acuan cut berasal dari [tes ContentDetector upstream](https://github.com/Breakthrough/PySceneDetect/blob/55f20ff3448ed336df032ac6270cf47d215dc2c4/tests/test_detectors.py): frame 1226, 1260, 1281, 1334, 1365. Ini ekspektasi tes detector tersebut, bukan anotasi universal seluruh transisi. Detektor FFmpeg kita melewatkan frame **1260**. Ambang default tetap; menyetel berdasarkan satu film berisiko menambah false positive pada video lain.

Kode pengembangan yang diuji: [`117044e`](https://github.com/mfpm15/content-creater/commit/117044e). Laporan JSON menyertakan SHA256, ukuran, versi Python/FFmpeg, waktu ukur UTC, wall time, hasil ukur dan batasnya: [speech](whisper-jfk.json), [video](scenedetect-goldeneye.json). Wall time berasal dari cloud Linux, bukan jaminan kecepatan laptop Windows. Sampel ini tidak menguji akurasi pembicara/kursor, framing portrait, sinkronisasi TTS, kualitas editorial atau viralitas.

Media disimpan hanya di `.data/benchmarks/` yang diabaikan Git. **Tidak didistribusikan bersama proyek.** Lisensi MIT Whisper dan BSD-3-Clause PySceneDetect berlaku pada kode repositori; hak redistribusi semua media uji tidak diasumsikan sama. Tidak ada kode/aset pihak ketiga yang diimpor ke produk.

## Mengulang di Windows

Jalankan dari root hasil Git clone/pull setelah `setup-core.bat`. FFmpeg harus ada di PATH. Unduh fixture publik secara eksplisit; Python menulis byte asli sehingga aman juga dari PowerShell 5.1 (hindari redirect `git show > video.mp4` pada shell tersebut).

```powershell
python -c "from pathlib import Path; Path('.data/benchmarks').mkdir(parents=True, exist_ok=True)"
python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/openai/whisper/86098128c0b4f24f0e2aa2994de830614b474227/tests/jfk.flac', '.data/benchmarks/whisper-jfk.flac')"
python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/Breakthrough/PySceneDetect/e68d06a78e5241d82300d4924a53629feecbcb6b/tests/resources/goldeneye.mp4', '.data/benchmarks/scenedetect-goldeneye.mp4')"

& .\creator-dashboard\.venv\Scripts\python.exe creator-dashboard/benchmark_media.py .data/benchmarks/whisper-jfk.flac --output .data/benchmarks/speech-result.json --expected-sha256 63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715
& .\clippercuan\app\.venv\Scripts\python.exe creator-dashboard/benchmark_media.py .data/benchmarks/scenedetect-goldeneye.mp4 --output .data/benchmarks/scene-result.json --expected-sha256 7262e7b13e8a3bfd389b9188b6c62583b9ba2a2fd35207862faed19d4f0ae5a1 --scene-sample 50.0082916667 10.4687916667 --expected-cuts 1.126125 2.5442083333 3.4200833333 5.630625 6.9235833333
```

Di Linux gunakan `.venv/bin/python` pada venv yang sama. CLI benchmark tidak mengunduh media/model, memanggil provider, atau mengubah ambang produksi. Tanpa acuan cut, precision/recall tidak dihitung. Tanpa timestamp transkrip, tempo ucapan dan cakupan kata tetap `null`.

## Perbandingan fitur halaman publik

Keenam URL berhasil dibaca HTTP 200 pada 1 November 2026. Berikut klaim pada halaman masing-masing; kualitas, batas paket dan akses akun tidak diverifikasi.

| Sumber | Fitur yang terlihat pada halaman | Hubungan dengan proyek |
|---|---|---|
| [SocialVisuals](https://socialvisuals.pro/) | Preset caption/font, penekanan kata, branding/watermark, preview, galeri hasil | Clipper sudah memiliki preset/word highlight dan galeri; Video Studio sekarang memiliki brand kit teks. |
| [Reap](https://reap.video/clipping) | Brand templates, animated captions, auto reframe, transcription, dubbing, scheduler | Brand snapshot dan ekspor multi rasio tersedia; dubbing/scheduler terpadu tetap belum tersedia. |
| [OpusClip](https://www.opus.pro/) | Brand template, animated captions, reframing, AI B-roll, XML, scheduler | Brand/review/rasio ada; AI B-roll, XML untuk NLE dan publishing terpadu belum tersedia. |
| [HeyGen](https://www.heygen.com/id-id/tool/ai-video-clip-generator) | Penyuntingan teks/caption, font/warna, versi terlokalisasi lip-sync | Caption editorial dan kit lokal tersedia; lip-sync/dubbing multibahasa belum tersedia. |
| [Creatify](https://creatify.ai/id/tools/ai-video-clip-generator) | Klip dari video panjang dengan hook/caption; pembuatan klip dari deskripsi atau foto produk | Pemilihan kandidat tersedia; video generatif dari prompt/foto belum menjadi workflow inti. |
| [Vmaker](https://www.vmaker.com/tools/ai-clip-maker) | Font/warna/logo/intros/outros, reframing pembicara, B-roll, caption, ekspor rasio | Kit saat ini teks/warna/font; logo gambar, intro/outro, B-roll generatif dan kualitas tracking setara layanan tidak diklaim. |

Prioritas yang diterapkan: brand kit tersimpan, timing visual berbasis timestamp eksplisit, dan bukti tempo awal/tengah/akhir pada analisis referensi. Upload audio pribadi dan pengembangan manajemen antrean render dikeluarkan sesuai keputusan pengguna. CSV asli tetap ditunda.
