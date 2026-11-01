# Distribusi Creator Control Center

Dokumen ini menjelaskan cara memindahkan proyek ke komputer lain tanpa membawa API key, data proyek, hasil video, cache, dependency hasil instalasi, atau virtual environment lokal.

## Isi yang dibagikan

Paket distribusi berisi source code, konfigurasi contoh, dokumentasi, test, lockfile, dan launcher. Paket sengaja tidak membawa:

- `.env`, `config.toml`, key, dan certificate lokal;
- `.data` yang berisi proyek dan media kerja Clipper Cuan;
- video, audio, upload, render, export, dan output;
- `node_modules`, `.venv`, cache Python/Node, coverage, dan build artifact;
- metadata Git dan hasil audit UI lokal.

Data kerja asli tetap berada di komputer pembuat dan tidak dihapus oleh proses packaging.

## Membuat paket bersih

Dari PowerShell di root proyek:

```powershell
powershell -ExecutionPolicy Bypass -File .\package-release.ps1
```

Hasilnya adalah arsip seperti `creator-control-center-20261029-0830.zip` beserta nilai SHA256 yang ditampilkan di terminal. Skrip melakukan validasi ulang sebelum membuat ZIP dan berhenti bila menemukan secret, dependency lokal, data kerja, atau media yang seharusnya dikecualikan.

Untuk nama versi sendiri:

```powershell
powershell -ExecutionPolicy Bypass -File .\package-release.ps1 -Version 1.0.0
```

## Persyaratan komputer penerima

- Windows 10/11 64-bit;
- Python 3.11 yang tersedia melalui `py` atau `python`;
- Node.js 22 atau lebih baru dan Corepack;
- `uv`;
- FFmpeg dan FFprobe di `PATH`;
- koneksi internet saat memasang dependency dan model pertama kali;
- ruang disk yang cukup untuk dependency, model transkripsi, sumber media, dan render.

Beberapa aplikasi terintegrasi memiliki lisensi dan persyaratan upstream sendiri. Penerima wajib meninjau lisensi tiap folder aplikasi sebelum redistribusi publik atau penggunaan komersial.

## Instalasi pada komputer lain

1. Ekstrak ZIP ke folder biasa yang dapat ditulis, misalnya `D:\CreatorControlCenter`.
2. Buka terminal di folder tersebut.
3. Jalankan `setup-dashboard.bat` untuk dependency tool dashboard.
4. Jalankan `clippercuan\app\start.bat --no-browser` sekali untuk membuat environment Clipper Cuan. Hentikan dengan `Ctrl+C` setelah health service aktif.
5. Salin `.env.example` menjadi `.env` hanya bila launcher yang dipakai memuat dotenv, atau atur environment Windows sesuai kebutuhan.
6. Buat konfigurasi lokal masing-masing aplikasi dari file contoh. Jangan commit atau kirim file berisi credential.
7. Jalankan `start-dashboard.bat` dan buka `http://127.0.0.1:3210`.
8. Jalankan Clipper Cuan dari kartunya di dashboard atau dari `clippercuan\app\start.bat`.

## Pemeriksaan sebelum dibagikan

Jalankan test utama:

```powershell
clippercuan\app\.venv\Scripts\python.exe -m pytest clippercuan\app\tests -q
python -m pytest creator-dashboard\test_dashboard.py creator-dashboard\test_video_drafter.py -q
```

Periksa bahwa arsip tidak berisi data sensitif:

```powershell
$zip = Get-ChildItem .\creator-control-center-*.zip | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::OpenRead($zip.FullName).Entries.FullName |
  Select-String '(^|/)(\.env|config\.toml|\.data|node_modules|\.venv)(/|$)|\.(key|pem|pfx|mp4|mp3|wav)$'
```

Perintah terakhir seharusnya tidak menghasilkan temuan, kecuali `.env.example` yang memang aman sebagai template.

## Data kerja dan backup

Folder `.data` sengaja tidak masuk paket. Untuk memindahkan proyek video milik sendiri, backup folder tersebut secara terpisah dan perlakukan sebagai data privat karena dapat berisi sumber media, transkrip, metadata, serta hasil render. Jangan gabungkan backup data kerja ke paket source code publik.
