# Plan: serap ide dari 8 repo referensi

Sumber dibaca 31 Oktober 2026 (README, clone dangkal). Hanya ide dan alur kerja yang diambil; tidak ada kode yang disalin.
Baseline sebelum perubahan: `python -m pytest tests` di `clippercuan/app` = 129 lulus.

| Repo | Ide utama | Status di ClipperCuan | Tindakan |
|---|---|---|---|
| kajisho5/ffmpeg-skill | probe, edit, **check** hasil per platform, template platform, loudness, silence removal | Loudness (`loudnorm`), potong hening, probe sudah ada. **Verifikasi hasil per platform belum ada** | **Slice 1: `delivery.py`** |
| kurbaitaev/ghost-editor | self-check akhir (jeda, level suara, ukuran caption), pilih take terbaik, gaya dari reel referensi | Ukuran caption + jeda sudah ada; self-check terpadu belum | Slice 1 (pakai delivery check) |
| agricidaniel/claude-shorts | skor 5 dimensi, snap batas ke kata/kalimat/hening, ekspor per platform, cursor tracking layar | Skor 9 dimensi + snap kalimat sudah ada. Ekspor per platform + cek belum. Cursor tracking belum | Slice 1 (platform), Slice 2 (snap hening), Slice 3 (cursor) |
| darkzOGx/youtube-automation-agent | gerbang persetujuan, resume per tahap, Shorts dari video, analitik | Resume (`recover_interrupted`, `retry`) dan Shorts sudah ada. Analitik ada di creator-dashboard | Tidak ada perubahan |
| calesthio/openmontage | gerbang persetujuan visual, analisis video referensi, papan produksi | `/api/production` dan pilih kandidat sudah ada | Tidak ada perubahan |
| cth9191/animate | animasi prosedural + storyboard | Sudah ada via Opuscar/HyperFrames di creator-dashboard | Tidak ada perubahan |
| cjpais/handy | STT offline, VAD Silero | faster-whisper + `vad_filter=True` sudah ada | Tidak ada perubahan |
| Panniantong/agent-reach | baca platform lewat satu CLI untuk agent | ClipperCuan sudah punya MCP/CLI/REST | Tidak ada perubahan |

## Slice 1 (dikerjakan): Delivery check per platform
- `clipper/delivery.py`: spesifikasi TikTok / YouTube Shorts / Instagram Reels, `evaluate()` murni, `check()` pakai ffmpeg.
- Cek: rasio 9:16, tinggi minimal, durasi maksimum platform, ada audio, loudness (target -14 LUFS, toleransi), fps minimal.
- Jalur: REST `GET /api/projects/{pid}/clips/{cid}/delivery`, MCP `check_delivery`.
- Tes: unit murni + satu klip sintetis ffmpeg.

## Slice 1b (dikerjakan): framing per-shot, validasi nyata
- `clipper/shots.py`: potongan kamera dari ffmpeg `scene`, termasuk crossfade (kelompok skor kecil yang rapat, `cuts_from_events`); tiap shot `single` / `multi` / `broll`.
- `render.py` menyusun filtergraph per shot; `crop_keys` lama diabaikan kecuali `crop_manual`.
- Panel banyak orang (3 orang di panggung) tidak lagi diklasifikasi gaming: `facetrack.multi_person_frames` menolak facecam bila >=25% frame punya >=2 wajah sebanding, dan `adaptive_split` tidak mengunci panel statis bila >=2 wajah stabil.
- Diuji pada WIRED (1 orang + B-roll), podcast sintetis 2 orang, dan panel Huang & Musk (2560x1440).
- Batas yang diketahui: klip 5 panel masih `multi` untuk ketiga shot (dua orang bergantian tampil di panel atas/bawah dari satu sudut kamera lebar); belum ada pemilihan pembicara aktif per shot.

## Slice 2 (belum): snap batas klip ke jeda hening
Dari claude-shorts. Perlu ubah `candidates.snap_boundary`; risiko memengaruhi ranking, jadi perlu benchmark terpisah.

## Slice 3 (belum): cursor tracking untuk screen recording
Dari claude-shorts. Frame differencing di `facetrack.py`; butuh rekaman layar nyata untuk validasi.
