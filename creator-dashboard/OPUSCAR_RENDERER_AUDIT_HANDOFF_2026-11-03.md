# Opuscar / GSAP Renderer Audit and Agent Handoff

Tanggal audit: 3 November 2026  
Workspace: `D:\Website\content-creater`  
Komponen utama: `creator-dashboard`  
Status dokumen: handoff untuk agent implementasi berikutnya

## 1. Ringkasan Eksekutif

Pipeline video berhasil menjalankan workflow riset, Scene Plan, Storyboard, TTS, retiming, audio, HyperFrames render, mux, review, dan penyajian MP4 melalui API. Akan tetapi, kualitas visual hasil Cyber Kill Chain tidak memenuhi kontrak produksi Opuscar.

Scene Plan sebenarnya sudah kaya dan spesifik. Ia menjelaskan objek, aksi, setting, metafora, komposisi, foreground, midground, background, kamera, pencahayaan, transisi, dan continuity untuk setiap scene. Masalah utama muncul pada tahap penerjemahan Scene Plan menjadi HTML/GSAP.

Renderer saat ini mereduksi arahan tersebut menjadi beberapa template visual generik berdasarkan `visualFamily`. Akibatnya:

- Banyak scene `process` menjadi tiga kotak 01-02-03 yang sama.
- Scene `concept` jatuh ke template constellation yang sama.
- Scene `comparison` selalu menjadi dua bola generik.
- Scene `data` selalu menjadi angka, bar chart, dan spline.
- Dekorasi cyber seperti orbit, scanner, grid, neon cyan, dan panel glow dipasang global.
- Animasi mayoritas menggunakan entrance, stagger, orbit rotation, scale drift, lalu exit yang sama.
- `subject`, `action`, `setting`, `metaphor`, `composition`, `foreground`, `midground`, `background`, dan `continuity` hampir tidak memengaruhi gambar yang dihasilkan.

Kesimpulan audit: implementasi Opuscar sudah tersedia pada level workflow, metadata, audio, render, review, dan delivery. Namun renderer visualnya masih berupa template motion graphic generik dan belum menjadi scene-directed procedural filmmaking seperti yang diwajibkan pedoman Opuscar.

Video hasil lama harus diperlakukan sebagai artefak diagnosis, bukan target kualitas final.

---

## 2. Permintaan dan Umpan Balik Pengguna

Pengguna menilai hasil video:

- terlalu sering menggunakan tema radar/cyber generik;
- animasi tidak berhubungan dengan isi scene;
- visual terlihat sama antar-scene;
- hasil tidak terasa seperti implementasi kemampuan Opuscar/GSAP;
- perlu dipelajari dan dirancang ulang, bukan hanya dipoles.

Ekspektasi yang harus dipenuhi agent selanjutnya:

1. Jangan mempertahankan template radar/neon sebagai default.
2. Jangan hanya mengganti palette atau easing.
3. Gunakan Scene Plan sebagai arahan produksi yang nyata.
4. Setiap scene harus menggambarkan objek dan aksi yang disebutkan.
5. Gerak harus memiliki anticipation, action, dan follow-through.
6. Hasil revisi harus diperiksa melalui style frames dan contact sheet sebelum full render.

---

## 3. Artefak Uji yang Relevan

### Job

- Job ID: `e8f4aeaaf5b449ea9a43c8aa773e1ed2`
- Slug: `cyber-kill-chain-retest-a23f3a`
- Status akhir: `succeeded`
- Progress: `100`
- Scene count: `19`
- Requested duration: `90` detik
- Minimum duration berdasarkan voice aktual: `108.9` detik
- Final duration: `109` detik

### Output directory

`creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/`

File penting:

- `scene-plan.json`
- `index.html`
- `timing-adjustment.json`
- `voice-lines.json`
- `voice.wav`
- `music-foley.wav`
- `final-audio.wav`
- `audio-manifest.json`
- `subtitles.srt`
- `silent-debug.mp4`
- `silent.mp4`
- `video.mp4`
- `review.json`
- `metadata.json`
- `hyperframes-debug.log`

### MP4 final

- Path: `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/video.mp4`
- API URL: `/api/videos/cyber-kill-chain-retest-a23f3a/video.mp4`
- HTTP status: `200`
- Content-Type: `video/mp4`
- Content-Length: `68336062`
- Resolution: `1080x1920`
- Frame rate: `30 fps`
- Video codec: `H.264`
- Audio codec: `AAC`
- Duration: `109.000000` detik
- SHA-256: `c336c4970808914895af5843d84d35d9a759ebfa132288702ac29f5b75302105`

---

## 4. Log Kronologis Pengujian

### 4.1 Scene Plan siap

Status awal:

```json
{
  "jobId": "e8f4aeaaf5b449ea9a43c8aa773e1ed2",
  "status": "awaiting_scene_plan",
  "progress": 35,
  "step": "Riset dan Scene Plan menunggu persetujuan",
  "revision": 0,
  "duration": 90,
  "sceneCount": 19
}
```

Scene Plan dan Storyboard kemudian disetujui melalui API.

### 4.2 TTS dan retiming

Pipeline berada pada:

```text
STATUS=rendering
PROGRESS=55
STEP=Membuat dubbing dan menyelaraskan timing narasi
```

Retiming selesai dengan hasil:

```json
{
  "method": "measured-voice-retiming",
  "requestedDuration": 90.0,
  "finalDuration": 109,
  "minimumRequiredDuration": 108.9,
  "extended": true,
  "sceneCount": 19
}
```

Scene Plan hasil retiming valid:

```json
{
  "duration": 109,
  "lastSceneEnd": 109.0,
  "sceneCount": 19,
  "invalidRanges": []
}
```

Kesimpulan: sistem retiming bekerja sesuai tujuan dan bukan sumber masalah visual.

### 4.3 Render pipeline pertama gagal

Pipeline mencapai:

```text
STATUS=rendering
PROGRESS=72
STEP=Merender visual dinamis Opuscar / GSAP
DURATION=109
```

Kemudian gagal:

```text
Command ['node', 'D:\Website\content-creater\creator-dashboard\apps\hyperframes\node_modules\hyperframes\bin\hyperframes.mjs', 'render', '-o', 'D:\Website\content-creater\creator-dashboard\output\videos\cyber-kill-chain-retest-a23f3a\silent.mp4', '--fps', '30', '--workers', '1'] returned non-zero exit status 1.
```

Kegagalan ini terjadi cepat dan job berubah ke `failed`.

### 4.4 Render diagnostik langsung

Command renderer yang sama dijalankan langsung dari output directory dengan output diarahkan ke `hyperframes-debug.log`.

Render diagnostik berjalan normal. Contoh progres:

```text
@hf-progress {"code":"capture","done":1292,"total":3270,"pct":47}
@hf-progress {"code":"capture","done":2050,"total":3270,"pct":59}
```

Render selesai dengan hasil:

```json
{
  "streams": [
    {
      "codec_name": "h264",
      "width": 1080,
      "height": 1920,
      "avg_frame_rate": "30/1"
    }
  ],
  "format": {
    "duration": "109.000000",
    "size": "65579635"
  }
}
```

File: `silent-debug.mp4`

Catatan: kegagalan render pipeline pertama perlu diselidiki terpisah. Komposisi yang sama terbukti dapat dirender penuh saat dijalankan langsung. Kemungkinan area investigasi:

- lifecycle subprocess;
- timeout atau process supervision;
- race antara render process dan state writer;
- transient browser/renderer failure;
- penanganan stdout/stderr;
- state job yang ditimpa worker lama setelah recovery manual.

### 4.5 Mux audio

`silent-debug.mp4` disalin ke `silent.mp4`, lalu dimux dengan `final-audio.wav`.

Hasil akhir:

```json
{
  "streams": [
    {
      "codec_name": "h264",
      "width": 1080,
      "height": 1920,
      "avg_frame_rate": "30/1"
    },
    {
      "codec_name": "aac",
      "avg_frame_rate": "0/0"
    }
  ],
  "format": {
    "duration": "109.000000",
    "size": "68336062"
  }
}
```

### 4.6 Review otomatis

Review menghasilkan:

```json
{
  "status": "needs_attention",
  "issues": [
    "Text overflow found in sampled scenes"
  ]
}
```

Audio:

- Integrated loudness: `-14.1 LUFS`
- True peak: `-1.4 dBFS`
- Silence starts: tidak ditemukan

Delivery profile:

- TikTok: passed working profile
- YouTube Shorts: passed working profile
- Instagram Reels: needs attention karena durasi melebihi profil kerja internal

Pacing per scene tidak ditandai bermasalah.

Masalah utama review adalah `text_overflow` pada heading scene. Contoh:

- `STAGE 6: C2 CHANNEL`
- `STAGE 7: ACTIONS ON OBJECTIVES`
- `INTELLIGENCE DRIVEN DEFENSE`
- `REUSED INDICATORS: IP / HASH / DOMAIN`
- `DEFENDER'S ADVANTAGE: 1 BREAK WINS`
- `BLOCKED AT DELIVERY = ATTACK FAILS`
- `CRITICISM 1: PERIMETER FOCUS`
- `NON-LINEAR & CLOUD ATTACKS`
- `KILL CHAIN + MITRE ATT&CK`
- `CORE MASTERY FOR ANALYSTS & SOC`
- `TECHNICAL BREAKDOWN NEXT`

Status `needs_attention` bukan penyebab kritik estetika pengguna. Ia hanya mendeteksi sebagian masalah teknis. Review otomatis belum cukup untuk mendeteksi repetisi template, motion yang tidak relevan, atau kualitas directing.

### 4.7 Sinkronisasi status job

Recovery manual sempat menulis status `succeeded`, tetapi service masih memegang state lama di memory dan mengembalikan `failed`. Setelah dashboard direstart, state terbaru dimuat:

```json
{
  "jobId": "e8f4aeaaf5b449ea9a43c8aa773e1ed2",
  "status": "succeeded",
  "progress": 100,
  "step": "Video Opuscar / GSAP selesai",
  "error": null,
  "duration": 109,
  "sceneCount": 19,
  "slug": "cyber-kill-chain-retest-a23f3a",
  "videoUrl": "/api/videos/cyber-kill-chain-retest-a23f3a/video.mp4",
  "reviewStatus": "needs_attention",
  "httpStatus": 200,
  "contentType": "video/mp4",
  "contentLength": "68336062"
}
```

Agent berikutnya sebaiknya memperbaiki source of truth job state agar recovery tidak memerlukan restart service.

---

## 5. Pedoman Opuscar yang Sudah Dipelajari

Sumber lokal yang wajib dibaca agent berikutnya:

- `creator-dashboard/apps/lemo-opuscar/AGENTS.md`
- `creator-dashboard/apps/lemo-opuscar/DIRECTOR.md`
- `creator-dashboard/apps/lemo-opuscar/TECHNIQUE.md`
- `creator-dashboard/apps/lemo-opuscar/tools/directory/SKILL.md`
- `creator-dashboard/apps/lemo-opuscar/tools/directory/REFERENCE.md`

Kontrak penting dari pedoman tersebut:

1. Agent adalah director, bukan pembuat tech demo.
2. Film dinilai berdasarkan sound, rhythm, camera, dan directing.
3. Treatment harus ditulis sebelum membuka atau meniru demo.
4. Style memiliki invariants look, colour, type, motion, camera grammar, sound palette, native moves, dan pitfalls.
5. Setiap shot harus memiliki alasan framing dan kamera.
6. Gunakan minimal empat gerakan kamera yang berbeda.
7. Harus ada satu signature shot.
8. Transisi harus lahir dari medium, bukan default fade/cut.
9. Adegan prosedural harus memiliki foreground, midground, background, camera intent, dan informative typography.
10. Setiap gerakan bermakna membutuhkan anticipation, action, dan follow-through.
11. Picture harus deterministic dan merupakan function of time.
12. Contact sheet perlu diperiksa minimal dua pass.
13. Frame strip 0.2 detik diperlukan untuk setiap key action.
14. Full-speed viewing dengan sound wajib sebelum delivery.
15. HyperFrames hanya boleh menjadi deterministic frame renderer. Produk dan workflow tetap Opuscar.
16. Demo hanya boleh dipakai untuk teknik. Jangan menyalin struktur, arc, shots, props, atau timeline demo.

---

## 6. Akar Masalah Teknis pada Renderer

### 6.1 File utama

`creator-dashboard/video_drafter.py`

Fungsi kritis:

- `_visual_markup(scene, index)` sekitar baris 397
- `generate_opuscar_composition(plan, aspect_info, model)` sekitar baris 470
- `generate_composition(...)` sekitar baris 816

### 6.2 `_visual_markup` terlalu bergantung pada `visualFamily`

Routing saat ini pada dasarnya:

```python
if family == "data":
    # metric + generic bars + trend line
if family == "process":
    # generic nodes 01, 02, 03
if family == "comparison":
    # generic left orb vs right orb
if family == "signal":
    # generic gyro/prism rings
if family == "network":
    # generic node network
...
return generic constellation
```

Masalah:

- `visualFamily` menjadi sumber utama gambar, padahal seharusnya fallback.
- Arahan visual terperinci tidak digunakan untuk memilih bentuk visual.
- `subject` hanya kadang menjadi label internal.
- `visual` sengaja tidak ditampilkan sebagai teks, tetapi juga tidak diterjemahkan menjadi bentuk.
- `action` tidak menggerakkan objek.
- `setting` tidak membangun set.
- `metaphor` tidak memengaruhi visual grammar.
- `composition` tidak mengatur layout.
- `foreground`, `midground`, dan `background` tidak dirender.
- `continuity` tidak menghubungkan scene.

### 6.3 Dekorasi cyber dipasang global

Dalam setiap section saat ini ada:

```html
<div class="scene-orbit orbit-a"></div>
<div class="scene-orbit orbit-b"></div>
```

Stage global mempunyai:

```html
<div class="bg-grid"></div>
<div class="scanner-line"></div>
```

CSS global mempunyai:

- radial cyan background;
- conic ambient orbit;
- cyan grid;
- scanner line;
- orbit circles;
- cyan panel border;
- panel pulse;
- neon shadow.

Akibatnya semua topik terlihat seperti HUD/radar/cyber dashboard.

Ini juga bertentangan dengan prompt planning di file yang sama, yang menyatakan:

> Jangan memakai radar, HUD, neon, network node, grafik, atau objek teknologi kecuali benar-benar relevan.

### 6.4 Animasi template berulang

Setiap scene biasanya menerima:

```javascript
chapter badge enters
hero title enters
visual wrapper scales and rotates in
subtitle enters
camera drift
orbit-a rotates
orbit-b rotates
all family children stagger in
family-specific generic entrance
scene exits
```

Scene `process` selalu memperoleh:

```javascript
tl.from(".process-node", {
  scale: 0.5,
  opacity: 0,
  stagger: 0.2,
  duration: 0.5,
  ease: "back.out(1.5)"
})
```

Ini menjelaskan mengapa animasi terasa tidak berhubungan dengan narasi.

### 6.5 Scene Plan visualFamily terlalu kasar

Pada output Cyber Kill Chain:

- Scene 3 sampai 10 sebagian besar diberi `process`.
- Scene 14 dan 16 juga diberi `process`.
- Scene 1, 2, 11, 15, 18, 19 diberi `concept`.

Walaupun masing-masing mempunyai objek dan aksi berbeda, semuanya masuk template yang sama.

### 6.6 Test saat ini mengunci template lama

`creator-dashboard/test_video_drafter.py` masih mengharapkan marker lama seperti:

```python
self.assertIn('class="visual-canvas-box data-viz"', result)
self.assertIn('class="sun-disc"', forest_html)
self.assertIn('class="device-shell"', product_html)
```

Test ini membuktikan keluarga visual muncul, tetapi tidak membuktikan bahwa scene direction benar-benar diterjemahkan.

Test baru harus menilai:

- penggunaan field directorial;
- perbedaan structural signature antar-scene;
- tidak adanya global radar/HUD dekoratif;
- action-specific animation;
- layered staging;
- continuity;
- title safety;
- deterministic output.

---

## 7. Bukti Konkret dari Cyber Kill Chain

Scene Plan meminta visual yang spesifik:

1. Steel link under mechanical tension.
2. CSIRT origin plate with tactical stamping.
3. Seven vertically interlocking steel modules.
4. Optical aperture scanning a blueprint.
5. Tungsten exploit core inserted into a sleeve.
6. Capsule moving through a pneumatic conduit.
7. Lock pins shearing under pressure.
8. Expansion anchors locking into substrate.
9. Antenna mast emitting C2 pulses.
10. Vault opening and data cartridges being extracted.
11. Prism refracting chaotic vectors into ordered defense lines.
12. IP/hash/domain index plates entering a registry.
13. Balance scale showing seven attack requirements versus one defensive break.
14. Barrier slamming shut and breaking the delivery capsule.
15. Outer wall protected while an internal node activates.
16. Non-linear route bypassing installation through an identity bridge.
17. Kill Chain spine docking into a MITRE matrix.
18. Professional mastery seal stamped into a console.
19. Seven modules expanding for technical inspection.

Renderer aktual menghasilkan:

- Scene process: tiga node 01-02-03.
- Scene concept: constellation network.
- Scene comparison: dua bola.
- Scene data: generic chart.
- Semua scene: rotating orbit decorations.

Ini adalah gap utama yang harus diselesaikan.

---

## 8. Strategi Re-architecture yang Direkomendasikan

### 8.1 Jangan tambal `_visual_markup` dengan lebih banyak `if visualFamily`

Jika hanya menambah template baru ke fungsi lama, masalah akan berpindah dari empat template menjadi sepuluh template, tetapi renderer tetap tidak memahami scene.

Rekomendasi: pisahkan pipeline menjadi empat tahap.

### Tahap A: Scene interpretation

Buat representasi internal, misalnya `DirectedSceneSpec`, dari field:

- subject
- action
- setting
- metaphor
- composition
- foreground
- midground
- background
- shotPurpose
- camera
- lighting
- typography
- transition
- continuity
- visualFamily sebagai fallback

Output interpretation sebaiknya berupa:

- `setGrammar`
- `heroObjectGrammar`
- `actionGrammar`
- `cameraGrammar`
- `transitionGrammar`
- `continuityToken`
- `palette`
- `layerPlan`
- `motionBeats`

### Tahap B: Procedural primitives

Bangun primitive reusable, bukan template scene penuh. Contoh:

- industrial plate
- chain link
- rail/conduit
- capsule
- lock body and pins
- anchor bolt
- barrier
- mast and pulse
- vault door
- cartridge rack
- prism
- vector field
- registry card
- scale and weights
- wall and internal node
- route bridge
- matrix grid
- seal and hydraulic press

Primitive boleh berupa HTML/CSS/SVG/Canvas, tetapi harus dapat dikomposisikan dan dianimasikan secara spesifik.

### Tahap C: Action choreography

Jangan memakai satu entrance untuk semua scene. Turunkan motion dari action verbs.

Contoh choreographies:

- `pulls taut`: initial slack, anticipation, tension pull, vibration settle.
- `stamps`: press descends, impact squash, recoil, emboss reveal.
- `locks sequentially`: modules enter one by one, latch, light transfer.
- `scans`: aperture focuses, beam travels, findings illuminate.
- `inserts`: core aligns, slides, latch closes, seam flash.
- `travels`: capsule accelerates, camera tracks, airflow trails.
- `shears`: pressure builds, pins bend, snap, fragments fall.
- `anchors`: module lands, bolts deploy, base vibrates, lock indicator settles.
- `emits pulses`: mast telescopes, emitter charges, directional pulses propagate.
- `opens`: lock wheel resolves, door swings with inertia, rack moves out.
- `refracts`: chaotic lines enter prism, split, align, settle.
- `balances`: seven-part load lands, one wedge drops, beam swings and settles.
- `blocks`: barrier anticipates, slams, capsule breaks, fragments rebound.
- `bypasses`: path follows expected route, aborts, arcs over skipped node.
- `docks`: spine aligns, pins engage, matrix cells illuminate outward.
- `stamps seal`: press descends, impact, emblem remains, press retracts.

Setiap meaningful action harus mempunyai anticipation, action, dan follow-through.

### Tahap D: Composition renderer

Renderer harus:

- membangun background set;
- membangun midground hero action;
- membangun foreground occluder/detail;
- menggunakan camera move dari Scene Plan;
- menempatkan judul dalam safe area;
- menggunakan subtitle tanpa menutupi hero object;
- menerapkan transition yang berasal dari objek atau medium;
- membawa continuity token ke scene berikutnya.

---

## 9. Arahan Visual Khusus Cyber Kill Chain

Visual thesis dari Scene Plan:

> Rantai fisik modular baja presisi berubah wujud sesuai fase logis serangan, putus seketika saat kontrol bertahan aktif.

World yang disarankan:

- Industrial mechanical test chamber.
- Graphite, steel gray, warm amber attack highlights, cobalt defense highlights.
- Bukan neon HUD.
- Bukan space grid.
- Bukan radar.
- Bukan constellation.

Continuity token utama:

- satu chain link atau modular steel connector;
- bentuknya berubah menjadi plate, module, aperture body, sleeve, conduit carrier, lock gate, anchor body, mast, vault mechanism, prism frame, registry slot, scale fulcrum, dan matrix spine;
- scene transition terjadi melalui match cut atau physical transformation token tersebut.

Signature shot yang disarankan:

- Scene 13 ke 14.
- Kamera memperlihatkan tujuh beban serangan pada satu sisi timbangan.
- Satu blue defense wedge jatuh pada sisi lain.
- Beam menghantam limit stop.
- Stop tersebut berubah menjadi barrier delivery pada scene berikutnya.
- Barrier menutup dan menghancurkan kapsul.

Ini menggabungkan payoff konseptual, transition dari medium, continuity, dan memorable action.

---

## 10. Perubahan Source yang Direkomendasikan

### Prioritas P0

1. Hapus dekorasi global berikut dari renderer Opuscar:
   - `scene-orbit`
   - `orbit-a`
   - `orbit-b`
   - `bg-grid`
   - `scanner-line`
   - ambient conic orbit
   - radar CSS yang tidak digunakan secara eksplisit

2. Jangan gunakan constellation sebagai fallback universal.

3. Jangan gunakan `visualFamily == process` sebagai alasan menggambar tiga node generik.

4. Tambahkan scene-directed renderer atau adapter terpisah supaya perubahan dapat dites tanpa merusak adapter lain.

5. Perbaiki title layout:
   - font size responsif terhadap panjang;
   - maksimal dua atau tiga baris sesuai safe area;
   - ukur bounding box;
   - kurangi tracking dan font size sebelum overflow;
   - jangan menaruh title di atas hero action.

### Prioritas P1

6. Buat primitive industrial yang diperlukan Cyber Kill Chain.

7. Buat action choreographies spesifik.

8. Gunakan foreground/midground/background pada DOM/canvas.

9. Implementasikan continuity token antar-scene.

10. Buat camera grammar sekurang-kurangnya:
    - locked insert;
    - push-in;
    - pull-out/scale reveal;
    - lateral track;
    - overhead inspection;
    - orbit hanya jika subjek benar-benar memerlukan spatial reveal.

11. Buat transition grammar:
    - shape transform;
    - object wipe;
    - match movement;
    - mechanical closure/opening;
    - light transfer;
    - avoid default fade/cut kecuali punya alasan.

### Prioritas P2

12. Tambahkan quality gate sebelum full render.

13. Tambahkan structural uniqueness score.

14. Tambahkan motion signature uniqueness score.

15. Tambahkan contact sheet approval/review checkpoint.

16. Tambahkan state persistence yang tidak memerlukan restart service setelah manual recovery.

17. Selidiki render subprocess failure yang tidak muncul saat command dijalankan langsung.

---

## 11. Regression Tests yang Harus Ditambahkan

### Test: tidak ada dekorasi radar global

Untuk plan non-radar, hasil HTML tidak boleh mengandung:

```text
scene-orbit
orbit-a
orbit-b
scanner-line
radar-ring
radar-sweep
ambientOrbit
```

### Test: field directorial memengaruhi output

Dua scene dengan visualFamily sama tetapi subject/action berbeda harus memiliki markup atau drawing spec berbeda.

Contoh:

- process + lock pins shearing
- process + capsule travelling

Hasilnya tidak boleh memiliki structural signature yang identik.

### Test: action-specific choreography

Output harus memiliki action marker atau animation spec berbeda, misalnya:

```text
data-action="shear"
data-action="travel"
data-action="anchor"
data-action="open-vault"
```

Atau equivalent internal representation.

### Test: layered composition

Setiap scene-directed visual harus mempunyai tiga layer atau explicit exemption:

```text
scene-background
scene-midground
scene-foreground
```

### Test: title safety

Judul panjang harus menghasilkan class atau computed strategy untuk compact/multiline title dan lolos overflow checker.

### Test: deterministic output

Pemanggilan generator dua kali dengan plan yang sama harus menghasilkan HTML identik.

### Test: uniqueness threshold

Untuk 19 scene Cyber Kill Chain:

- tidak lebih dari dua scene berturut-turut boleh memakai structural grammar sama;
- minimal 70% scene mempunyai action choreography berbeda;
- minimal empat camera grammar digunakan;
- tidak ada global cyber motif tanpa explicit direction.

### Test: continuity

Scene yang memiliki `continuity` harus menghasilkan continuity token atau transition binding yang dapat diverifikasi.

### Test: contact sheet gate

Full render tidak boleh dimulai jika:

- sampled frame overflow;
- duplicate visual structure terlalu tinggi;
- black frame;
- subtitle menutupi hero action;
- scene object terlalu kecil;
- visual audit belum dijalankan.

---

## 12. Acceptance Criteria

Implementasi dianggap selesai hanya jika semua kriteria berikut terpenuhi.

### Visual

- Tidak ada radar, orbit, scanner, network, atau HUD global kecuali diminta scene.
- Setiap tahap Cyber Kill Chain mempunyai representasi objek berbeda dan relevan.
- Scene 4 sampai 10 tidak lagi berupa tiga node generik.
- Scene concept tidak lagi otomatis menjadi constellation.
- Scene comparison tidak lagi otomatis menjadi dua bola.
- Foreground, midground, dan background terlihat nyata pada style frames.
- Subject utama mengisi minimal sepertiga tinggi frame pada key moments.

### Motion

- Setiap key action memiliki anticipation, action, follow-through.
- Minimal empat camera movements berbeda.
- Ada satu signature shot.
- Transisi utama menggunakan physical continuity, bukan default fade.
- Tidak ada pola entrance identik yang mendominasi semua scene.

### Typography

- Semua heading lolos overflow review.
- Subtitle aman dan tidak menutupi hero action.
- Judul panjang tetap terbaca pada 1080x1920.

### Technical

- Deterministic frame rendering.
- Unit tests lulus.
- Contact sheet pass pertama diperiksa, diperbaiki, lalu pass kedua dibuat.
- Frame strips dibuat untuk key actions.
- Final render H.264/AAC 1080x1920 30 fps.
- Audio sekitar -14 LUFS dan true peak tidak melebihi sekitar -1.5 dBTP.
- API mengembalikan `video/mp4` dengan HTTP 200.
- Job state tetap sinkron tanpa restart manual.

### User review

Sebelum full render 109 detik, berikan dahulu:

1. Tiga style frames menggunakan drawing code sebenarnya.
2. Contact sheet dari 6-9 key shots.
3. Penjelasan signature shot dan continuity token.

Jangan menghabiskan waktu untuk full video sebelum visual direction terbukti benar.

---

## 13. File yang Perlu Diperiksa Agent Berikutnya

### Source utama

- `creator-dashboard/video_drafter.py`
- `creator-dashboard/scene_render.py`
- `creator-dashboard/creative_profile.py`
- `creator-dashboard/video_review.py`
- `creator-dashboard/test_video_drafter.py`
- `creator-dashboard/test_studio_controls.py`
- `creator-dashboard/test_animation_clock.py`
- `creator-dashboard/test_production_automation.py`

### Opuscar guidance

- `creator-dashboard/apps/lemo-opuscar/AGENTS.md`
- `creator-dashboard/apps/lemo-opuscar/DIRECTOR.md`
- `creator-dashboard/apps/lemo-opuscar/TECHNIQUE.md`
- `creator-dashboard/apps/lemo-opuscar/tools/directory/SKILL.md`
- `creator-dashboard/apps/lemo-opuscar/tools/directory/REFERENCE.md`

### Output diagnosis

- `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/scene-plan.json`
- `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/index.html`
- `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/review.json`
- `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/hyperframes-debug.log`
- `creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/video.mp4`

---

## 14. Hal yang Jangan Dilakukan

Agent berikutnya jangan:

- hanya mengganti warna cyan menjadi warna lain;
- hanya menghapus radar tetapi mempertahankan tiga node generik;
- menambahkan puluhan template visualFamily baru tanpa scene interpretation;
- menjadikan LLM sebagai generator HTML mentah tanpa schema dan validation;
- membuat full render sebelum style frames/contact sheet lolos;
- menandai pekerjaan selesai hanya karena MP4 valid;
- menganggap `reviewStatus=passed` sebagai bukti directing bagus;
- menyalin demo Opuscar secara langsung;
- merusak engine Three.js, Lottie, Continuous, atau Remotion saat memperbaiki Opuscar;
- mengubah fakta dan narasi pengguna tanpa permintaan.

---

## 15. Saran Struktur Modul Baru

Salah satu kemungkinan struktur:

```text
creator-dashboard/
  opuscar_director.py
  opuscar_scene_spec.py
  opuscar_primitives.py
  opuscar_actions.py
  opuscar_camera.py
  opuscar_transitions.py
  opuscar_composer.py
  opuscar_quality_gate.py
  tests/
    test_opuscar_scene_interpretation.py
    test_opuscar_action_choreography.py
    test_opuscar_visual_uniqueness.py
    test_opuscar_quality_gate.py
```

Tanggung jawab:

- `opuscar_scene_spec.py`: normalisasi arahan sutradara menjadi scene spec.
- `opuscar_primitives.py`: primitive procedural reusable.
- `opuscar_actions.py`: choreography berdasarkan action verbs.
- `opuscar_camera.py`: framing dan camera movement.
- `opuscar_transitions.py`: continuity dan medium-native transitions.
- `opuscar_composer.py`: menghasilkan deterministic document.
- `opuscar_quality_gate.py`: uniqueness, overflow, layer, contact sheet, dan render readiness.

Struktur persis boleh berbeda. Prinsip pemisahannya yang penting.

---

## 16. Prompt Siap Pakai untuk Agent Berikutnya

```text
Audit dan redesign renderer Opuscar/GSAP di workspace D:\Website\content-creater.

Baca terlebih dahulu:
- creator-dashboard/OPUSCAR_RENDERER_AUDIT_HANDOFF_2026-11-03.md
- creator-dashboard/apps/lemo-opuscar/AGENTS.md
- creator-dashboard/apps/lemo-opuscar/DIRECTOR.md
- creator-dashboard/apps/lemo-opuscar/TECHNIQUE.md
- creator-dashboard/apps/lemo-opuscar/tools/directory/SKILL.md
- creator-dashboard/apps/lemo-opuscar/tools/directory/REFERENCE.md

Diagnosis sudah terkonfirmasi: Scene Plan Cyber Kill Chain sangat spesifik, tetapi video_drafter._visual_markup mereduksinya menjadi template visualFamily generik. generate_opuscar_composition juga menambahkan orbit, grid, scanner, neon cyan, dan animasi template ke hampir semua scene. Akibatnya semua scene terasa seperti radar/HUD dan motion tidak mengikuti action.

Tugas:
1. Desain ulang renderer Opuscar agar subject, action, setting, metaphor, composition, foreground, midground, background, camera, transition, dan continuity benar-benar menentukan visual.
2. Jadikan visualFamily fallback, bukan sumber utama gambar.
3. Hilangkan radar/orbit/grid/scanner/HUD global yang tidak diminta.
4. Buat procedural primitives dan action choreography khusus untuk Cyber Kill Chain industrial mechanical treatment.
5. Setiap meaningful action harus memiliki anticipation, action, dan follow-through.
6. Tambahkan minimal empat camera grammars dan satu signature shot.
7. Tambahkan title overflow handling.
8. Tambahkan regression tests untuk visual uniqueness, action specificity, layered staging, continuity, deterministic output, dan larangan motif radar default.
9. Jangan full render dahulu. Hasilkan tiga style frames dan satu contact sheet 6-9 key shots menggunakan drawing code aktual.
10. Jalankan test suite dan dokumentasikan hasilnya.
11. Setelah contact sheet layak, baru full render dan validasi MP4/audio/API.

Gunakan output diagnosis:
creator-dashboard/output/videos/cyber-kill-chain-retest-a23f3a/

Jangan menambal dengan lebih banyak template visualFamily. Lakukan scene-directed procedural composition.
```

---

## 17. Status Handoff

Selesai didokumentasikan:

- kronologi job;
- retiming;
- render failure dan recovery;
- mux dan review;
- status API;
- keluhan pengguna;
- audit pedoman Opuscar;
- akar masalah source;
- bukti template repetition;
- strategi redesign;
- regression tests;
- acceptance criteria;
- daftar file;
- prompt untuk agent berikutnya.

Belum dilakukan pada handoff ini:

- perubahan source renderer;
- pembuatan module baru;
- regression test baru;
- style frame revisi;
- contact sheet revisi;
- render ulang video.

Alasan: perubahan yang dibutuhkan bersifat arsitektural dan tidak aman dilakukan sebagai patch kosmetik. Agent berikutnya harus mengerjakannya sebagai redesign renderer dengan quality gate yang jelas.
