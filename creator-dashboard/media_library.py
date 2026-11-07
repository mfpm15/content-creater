"""Strict local visual media bin for first-party Video Studio.

Only user-provided raster images are accepted in v1. No remote fetching, no
external URLs sent to the renderer, and no SVG/HTML or arbitrary local paths.
All media is explicitly licensed/owned by the user, not inferred from a URL.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent / "output" / "media-library"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PIXEL_COUNT = 32_000_000
MAX_ASSETS = 300
ID_PATTERN = re.compile(r"[a-f0-9]{32}\Z")
EXTENSIONS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
Image.MAX_IMAGE_PIXELS = MAX_PIXEL_COUNT


def require_id(asset_id: str) -> str:
    if not isinstance(asset_id, str) or not ID_PATTERN.fullmatch(asset_id):
        raise ValueError("ID media tidak valid")
    return asset_id


def _validate_image(data: bytes) -> tuple[str, str, int, int]:
    if len(data) > MAX_FILE_BYTES or not data:
        raise ValueError("Media gambar kosong atau melebihi 8 MB")
    try:
        with Image.open(io.BytesIO(data)) as picture:
            detected = picture.format
            width, height = picture.size
            if detected not in EXTENSIONS:
                raise ValueError("Hanya PNG, JPEG atau WebP yang didukung")
            if not (80 <= width <= 8192 and 80 <= height <= 8192 and width * height <= MAX_PIXEL_COUNT):
                raise ValueError("Dimensi gambar di luar batas yang aman")
            picture.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("File bukan gambar valid atau berisiko") from exc
    ext, mime = EXTENSIONS[detected]
    return ext, mime, width, height


def save(payload: dict, *, root: Path = ROOT) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Media harus objek JSON")
    if payload.get("rightsConfirmed") is not True:
        raise ValueError("Konfirmasi hak penggunaan komersial aset sebelum impor")
    name = str(payload.get("name") or "").strip()
    origin = str(payload.get("source") or "").strip()
    author = str(payload.get("creator") or "").strip()
    if not (1 <= len(name) <= 120) or not (1 <= len(origin) <= 400) or len(author) > 120:
        raise ValueError("Nama, sumber dan kreator wajib dalam batas panjang")
    encoded = payload.get("base64")
    if not isinstance(encoded, str) or not encoded or len(encoded) > (MAX_FILE_BYTES * 4 // 3 + 20):
        raise ValueError("Data gambar melebihi batas")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Data base64 gambar tidak valid") from exc
    ext, mime, width, height = _validate_image(raw)
    root.mkdir(parents=True, exist_ok=True)
    if len(list(root.glob("*.json"))) >= MAX_ASSETS:
        raise ValueError("Perpustakaan media penuh; hapus aset lama")
    asset_id = uuid.uuid4().hex
    name_on_disk = f"{asset_id}.{ext}"
    meta = {
        "id": asset_id, "name": name, "source": origin, "creator": author,
        "rightsConfirmed": True, "createdAt": round(time.time(), 3),
        "sha256": hashlib.sha256(raw).hexdigest(), "filename": name_on_disk,
        "mime": mime, "width": width, "height": height, "bytes": len(raw),
        "url": f"/api/videos/assets/{asset_id}",
    }
    temp_file = root / f"{asset_id}.tmp"
    file_path = root / name_on_disk
    try:
        with temp_file.open("xb") as handle:
            handle.write(raw)
        os.replace(temp_file, file_path)
        (root / f"{asset_id}.json").write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    except BaseException:
        temp_file.unlink(missing_ok=True)
        file_path.unlink(missing_ok=True)
        raise
    return meta


def get(asset_id: str, *, root: Path = ROOT) -> tuple[dict, Path]:
    require_id(asset_id)
    metadata_file = root / f"{asset_id}.json"
    if not metadata_file.is_file() or metadata_file.is_symlink():
        raise FileNotFoundError("Media tidak ditemukan")
    meta = json.loads(metadata_file.read_text("utf-8"))
    filename = str(meta.get("filename", ""))
    if meta.get("id") != asset_id or filename not in {f"{asset_id}.{ext}" for ext, _ in EXTENSIONS.values()}:
        raise ValueError("Metadata media tidak konsisten")
    file_path = root / filename
    if not file_path.is_file() or file_path.is_symlink():
        raise FileNotFoundError("File media tidak ditemukan")
    if file_path.stat().st_size != meta.get("bytes"):
        raise ValueError("Ukuran media tidak sesuai metadata")
    if hashlib.sha256(file_path.read_bytes()).hexdigest() != meta.get("sha256"):
        raise ValueError("Checksum media tidak valid")
    return meta, file_path


def catalogue(*, root: Path = ROOT) -> list[dict]:
    if not root.is_dir():
        return []
    results = []
    for record in sorted(root.glob("*.json"), reverse=True)[:MAX_ASSETS]:
        try:
            meta, _ = get(record.stem, root=root)
            results.append(meta)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
    return results


def stage(asset_id: str, target_public: Path, *, root: Path = ROOT) -> dict:
    """Copy verified immutable media to an isolated render's /public/media folder."""
    meta, file_path = get(asset_id, root=root)
    target = target_public / "media"
    target.mkdir(parents=True, exist_ok=True)
    destination = target / meta["filename"]
    shutil.copyfile(file_path, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != meta["sha256"]:
        destination.unlink(missing_ok=True)
        raise ValueError("Media berubah saat dipindahkan untuk render")
    return {**meta, "publicFile": f"media/{meta['filename']}"}
