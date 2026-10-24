# Draft Rencana: Menu Article Drafter

Status: DRAFT, belum ada kode. Menunggu keputusan di bagian "Pertanyaan terbuka".

## Tujuan

Satu menu baru di dashboard. Kamu isi informasi draft, tool menghasilkan artikel utuh dalam dua format:

- `.md` (siap taruh di blog / repo)
- `.docx` (Word, bisa dibuka dan diedit)

Artikel boleh berisi elemen gambar dan penjelasan tambahan (kotak catatan, diagram, tabel).

## Hasil studi dua repo referensi

Keduanya agent skill: kumpulan instruksi + template + skrip untuk agent AI, bukan mesin yang bisa dipanggil langsung. Keduanya berlisensi MIT.

| Repo | Isi | Yang berguna untuk kita |
|---|---|---|
| `cathrynlavery/diagram-design` | 45 jenis diagram (arsitektur, flowchart, sequence, timeline, quadrant, dll) sebagai satu file HTML+SVG mandiri. Ada aturan gaya (tanpa shadow, grid 4px, type ramp), `references/*.md`, 130 template contoh, dan skrip `export_svg.py` / `export_png.py` (Playwright). | Aturan gaya + template sebagai prompt panduan LLM, dan alur SVG ke PNG. |
| `tt-a1i/archify` | Diagram interaktif dan halaman "explainer" (kesimpulan dulu, satu panel per pertanyaan) sebagai HTML mandiri. Ekspor PNG/WebP/JPG, cetak PDF. | Pola struktur "kesimpulan dulu, lalu panel penjelas". Interaktivitasnya tidak ikut ke Word. |

Dampak ke desain: Word tidak bisa memuat HTML interaktif. Jadi diagram harus berakhir sebagai gambar PNG. Interaktif (archify) hanya bisa jadi bonus di `.html`, bukan target utama.

## Alur kerja

```
Form input  ->  LLM tulis artikel (Markdown + penanda gambar)
            ->  LLM buat SVG per diagram (aturan gaya diagram-design)
            ->  Playwright render SVG -> PNG
            ->  Simpan .md (+ folder images/) dan .docx (gambar tertanam)
```

### Input form

| Field | Keterangan |
|---|---|
| Judul kerja | Boleh kasar, LLM boleh usulkan judul akhir |
| Audiens | Misal: pemula keamanan siber, manajer non-teknis |
| Bahasa, nada | Indonesia / Inggris; santai / formal / edukatif |
| Panjang target | Misal 800 / 1500 / 3000 kata |
| Poin-poin draft | Teks bebas, bullet dari kamu. Ini sumber utama isi |
| Sumber / catatan | Link, kutipan, data yang boleh dipakai. LLM tidak boleh mengarang fakta di luar ini |
| Permintaan gambar | Daftar: jenis (diagram/tabel/kotak catatan), judul, deskripsi singkat |

Semua input disimpan sebagai `input.json` di folder artikel, jadi bisa dijalankan ulang atau direvisi.

### Penanda gambar di artikel

LLM menulis artikel dengan penanda seperti `{{diagram:arsitektur-login}}` dan `{{callout:catatan-penting}}`. Tahap berikutnya mengganti penanda itu:

- `diagram:*` menjadi PNG hasil render SVG, lengkap dengan teks alt dan keterangan gambar.
- `callout:*` menjadi blockquote di Markdown dan paragraf berbingkai di Word.

### Keluaran

```
creator-dashboard/output/articles/<slug>/
  input.json
  article.md
  article.docx
  images/diagram-1.png, diagram-1.svg, ...
```

## Rancangan teknis

- **Tempat kode:** modul baru `creator-dashboard/article_drafter.py` + halaman baru di `static/`. `server.py` hanya menambah beberapa endpoint (`/api/articles`). Server tetap stdlib.
- **LLM:** panggil 9Router (`http://localhost:20128/v1/chat/completions`, model `ag/gemini-3.8-flash-high`) lewat `urllib`. Tanpa dependensi baru.
- **Pembuat Word:** `python-docx` (belum terpasang). Dipasang di venv khusus `creator-dashboard/.venv-articles`, bukan ke tool lain.
- **Render PNG:** Playwright dengan Microsoft Edge yang sudah ada di mesin ini (`channel="msedge"`), jadi tidak perlu unduh Chromium.
- **Skill referensi:** salin hanya `references/` dan aturan gaya dari `diagram-design` ke `creator-dashboard/article-drafter/diagram-style/` beserta file lisensi MIT. Tidak pakai `npx skills add`.
- **Alur kerja berat dijalankan sebagai proses terpisah** (lewat venv artikel), status dan log tampil di dashboard seperti tool lain.

## Tahapan

| Tahap | Isi | Hasil bisa dicoba |
|---|---|---|
| 1 | Form + LLM tulis artikel + ekspor `.md` dan `.docx` (tanpa gambar) | Artikel utuh dari poin-poin kamu |
| 2 | Diagram: LLM buat SVG, render PNG, tertanam di `.md` dan `.docx` | Artikel dengan diagram |
| 3 | Revisi per bagian (tulis ulang satu section), pilihan gaya Word (font, header), riwayat artikel | Alur kerja nyaman dipakai berulang |
| Opsional | Versi `.html` interaktif ala archify | Bonus untuk web |

## Risiko dan batas

- **Kualitas SVG dari LLM bervariasi.** Mitigasi: batasi ke beberapa jenis diagram dulu (flowchart, arsitektur, timeline, tabel perbandingan), pakai template sebagai contoh di prompt, lalu validasi SVG (parse XML + cek `viewBox`) sebelum render. Kalau gagal, ulang satu kali, lalu beri tanda di artikel, tidak diam-diam dihapus.
- **Gambar AI (ilustrasi foto) belum bisa.** 9Router belum punya provider gambar. Untuk sekarang hanya diagram, tabel, dan kotak catatan. Foto/ilustrasi bisa kamu sisipkan sendiri lewat penanda `{{image:nama-file}}`.
- **Fakta.** LLM hanya boleh memakai isi poin dan sumber dari kamu. Hal yang tidak ada sumbernya ditandai `[PERLU VERIFIKASI]` di artikel, tidak ditulis seolah fakta.
- **Hasil Word sederhana** di tahap 1-2 (judul, paragraf, daftar, tabel, gambar, kutipan). Tata letak majalah tidak dijanjikan.

## Pertanyaan terbuka (perlu keputusan kamu)

1. Bahasa dan nada default: Indonesia semi-formal?
2. Jenis gambar prioritas: diagram saja dulu, atau kamu juga butuh foto/ilustrasi (butuh provider gambar nanti)?
3. Mulai dari tahap 1 saja (cepat), atau langsung tahap 1 + 2?
4. Format Word: cukup polos, atau ada template tertentu (font, header, logo)?
5. Artikel hasil jadi ikut di-push ke GitHub, atau folder `output/` diabaikan git (rekomendasi: diabaikan)?
