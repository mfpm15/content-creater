# Status implementasi blueprint

Implemented: POSIX process isolation/stop, local Host/Origin guard, backend Clipper auth proxy without redirects, Windows/POSIX Python resolver, selected Linux launchers, per-column retention units, shared LLM environment fallback, dashboard/Clipper error and log redaction, authenticated provider HTTPS/redirect guards, registered local provider secrets, canonical editorial caption resolution for render/preview/subtitle export, undo/redo history, stale-render flag, conservative dominant-speaker selection, delivery result persistence/cache, long-source candidate coverage, optional article research worker, explicit unverified grounding status, private atomic Video Studio checkpoints and recovery classification, narration overflow rejection, basic post-render stream/duration review.

Validation: dashboard 37 unittest checks and HTTP smoke passed. Clipper full suite 169 passed, F/E9 lint passed; after final transport changes 8 targeted editorial/provider checks passed. Two subsequent targeted editorial checks are included in those 8. Full suite was not repeated after the final transport-only changes. Real providers, desktop packages, multi-platform publishing and real-video visual quality were not validated.

Remaining blueprint work (not represented as implemented): retention scene mapping; safe-area checks for title/watermark/source text; platform-targeted project-wide/automatic exports; measured silence snapping; within-shot speaker switching/audio correlation; claim-to-evidence/freshness validation; article section rewriting/diagrams; Lottie preview/export parity; multi-aspect rendering; loudness/peak and browser visual review; cursor/take tracking; Reels/TikTok CSV adapters and learning loop. Data/provider-dependent acceptance requires actual inputs and credentials supplied securely in environment settings.

Security controls reduce exposure; they are not a completed penetration test or a guarantee that credentials can never leak. Raw process memory, user-authored content and third-party applications need separate threat modeling. Existing local provider settings still contain secrets by design and must remain outside version control.

## Kelanjutan setelah sinkronisasi GitHub 8a84b63

- Video Studio: daftar pekerjaan tersimpan, endpoint resume, tombol review/lanjutkan, revision guard pada API edit/approve/revise/resume (HTTP 409 untuk versi usang), snapshot status tanpa alias mutable, dan invalidasi persetujuan saat rencana berubah. Resume kembali ke review sebelum render; checkpoint tanpa rencana mengulang riset setelah aksi eksplisit.
- Editor mempertahankan motion/metafora dan field yang tidak ditampilkan, sehingga klik Simpan tidak menghapus kontrak rencana.
- Checkpoint memakai temporary file unik mode 0600, penulisan atomik, redaksi per nilai JSON, pembatasan ukuran, validasi revisi, dan penolakan symlink/file nonregular saat recovery.
- Analytics: pilihan auto/persen/rasio melalui UI dan API; kolom ambigu ditolak sampai satuan dipilih. Baris invalid, duplikasi timestamp dan kolom tak terpakai dilaporkan; rata-rata dilabeli rata-rata sampel.
- Validasi saat ini: 48 tes dashboard lulus, smoke HTTP lulus, pemeriksaan sintaks JavaScript lulus, dan harness editor memastikan field motion/metafora terpelihara. Tes Clipper tidak diulang karena subtree tersebut tidak berubah pada kelanjutan ini. Provider nyata dan interaksi browser penuh belum diuji.


## Ekspor Clipper per platform

- Sumber profil/asal commit tercatat pada `clipper/platform_specs.json`, dipakai validator dan overlay Studio. Paket desktop menyertakan data ini.
- Studio, REST dan MCP dapat mengantrekan varian TikTok/Shorts/Reels. Encode memakai H.264/AAC, loudness dua tahap, metadata sumber dihapus, lalu output diprobe dan diukur ulang. Rasio/resolusi dipertahankan.
- Mask spoken caption tambahan diukur dengan libass pada seluruh frame, termasuk box/glow/animasi; geometri yang gagal/tidak terukur menahan varian. Title, watermark, dekorasi dan teks bawaan sumber belum diperiksa otomatis.
- SHA-256 mengikat MP4, ASS dan varian yang diunduh. Render lama tanpa metadata hash harus dirender ulang; perubahan visual membatalkan varian lama. Endpoint unduh memeriksa integritas dan menolak artefak yang belum lolos/berubah.
- Raw MP4/ZIP/auto-export lama dipertahankan tanpa klaim lolos gerbang varian. Antrean ekspor terputus diberi status yang dapat diulang; transisi pembatalan terlambat tidak boleh menimpa pekerjaan selesai/retry.
- Auth tetap berlaku; mutasi browser lintas origin/skema dan Origin null ditolak, termasuk pada mode token. Klien nonbrowser tanpa Origin tetap didukung.
- Browser Chromium dengan proyek sintetis terisolasi telah menguji pemilihan zona, antrean, polling, dan unduhan checked variant tanpa error JS. Kemasan desktop baru diperiksa argumen asetnya; paket executable desktop dan platform publikasi nyata belum diuji.

Validasi akhir irisan ekspor: 183 tes Clipper lulus dan ruff F/E9 bersih. Pengujian browser memakai Chromium dengan data sintetis terisolasi; layanan provider eksternal, publikasi ke platform, dan paket desktop nyata belum diuji.
