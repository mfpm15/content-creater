from __future__ import annotations

import csv
import io
import math
import re
from typing import Any

MAX_CSV_BYTES = 2_000_000
MAX_TRANSCRIPT_CHARS = 300_000
MAX_TEXT_CHARS = 5_000
_GENERIC = {"video", "youtube", "shorts", "viral", "amazing", "terbaik", "penting", "rahasia", "wajib", "lihat", "tonton", "ini", "itu"}


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", ".")
    try:
        number = float(text)
        return number if math.isfinite(number) else None
    except ValueError:
        return None


def _timestamp_seconds(value: Any, duration: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    if ":" in text:
        try:
            parts = [float(x) for x in text.split(":")]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except ValueError:
            return None
    number = _number(text)
    if number is None:
        return None
    lowered = text.lower()
    if duration and ("percent" in lowered or "%" in text):
        return duration * number / 100
    return number


def _transcript_rows(text: str) -> list[tuple[float, float, str]]:
    rows: list[tuple[float, float, str]] = []
    if not text:
        return rows
    blocks = re.split(r"\n\s*\n", text[:MAX_TRANSCRIPT_CHARS].replace("\r", ""))
    stamp = re.compile(r"(?P<a>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*(?:-->|-|–)\s*(?P<b>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)")
    for block in blocks:
        match = stamp.search(block)
        if not match:
            continue
        start = _timestamp_seconds(match.group("a").replace(",", "."))
        end = _timestamp_seconds(match.group("b").replace(",", "."))
        body = " ".join(line.strip() for line in block.splitlines() if line.strip() and not line.strip().isdigit() and not stamp.search(line))
        if start is not None and end is not None and body:
            rows.append((start, end, body[:280]))
    return rows


def analyze_retention(csv_body: bytes, transcript: str = "", duration: float | None = None, units: str = "auto") -> dict[str, Any]:
    if units not in {"auto", "percent", "ratio"}:
        raise ValueError("Satuan retention harus auto, percent, atau ratio")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("Durasi harus berupa angka positif yang terbatas")
    if not csv_body or len(csv_body) > MAX_CSV_BYTES:
        raise ValueError("CSV kosong atau melebihi batas 2 MB")
    try:
        text = csv_body.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = csv_body.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV tidak memiliki header")
    fields = {f.lower().strip(): f for f in reader.fieldnames if f}
    time_key = next((fields[k] for k in fields if any(x in k for x in ("timestamp", "time", "detik", "second", "position"))), None)
    value_key = next((fields[k] for k in fields if any(x in k for x in ("retention", "audience", "percent", "ratio")) and fields[k] != time_key), None)
    if not time_key or not value_key:
        raise ValueError("Header waktu dan retention tidak ditemukan")
    rows = list(reader)
    raw_values = [str(row.get(value_key) or "") for row in rows]
    numbers = [_number(v) for v in raw_values]
    explicit_percent = any("%" in v for v in raw_values) or any(x in value_key.lower() for x in ("percent", "%"))
    if units == "ratio" and explicit_percent:
        raise ValueError("Kolom mengandung persen; pilih satuan persen")
    selected_units = units
    if units == "auto":
        if explicit_percent:
            selected_units = "percent"
        elif "ratio" in value_key.lower():
            selected_units = "ratio"
        elif any(v is not None and v > 1 for v in numbers):
            selected_units = "percent"
        else:
            raise ValueError("Satuan kolom ambigu. Pilih Persen atau Rasio sebelum analisis")
    ratio_units = selected_units == "ratio"
    invalid_rows = 0
    points: list[dict[str, float]] = []
    for row in rows:
        second = _timestamp_seconds(row.get(time_key), duration)
        value = _number(row.get(value_key))
        if second is None or value is None or not math.isfinite(second) or second < 0 or value < 0:
            invalid_rows += 1
            continue
        if ratio_units:
            value *= 100
        points.append({"second": round(second, 3), "retention": round(value, 3)})
    duplicates = len(points) - len({p["second"] for p in points})
    points = sorted({p["second"]: p for p in points}.values(), key=lambda p: p["second"])
    if len(points) < 3:
        raise ValueError("CSV membutuhkan sedikitnya 3 titik retention valid")
    captions = _transcript_rows(transcript)
    events = []
    slopes = []
    for previous, current in zip(points, points[1:]):
        gap = max(current["second"] - previous["second"], 0.001)
        delta = current["retention"] - previous["retention"]
        slopes.append(delta / gap)
        if delta <= -4 or delta / gap <= -1.5:
            spoken = next((body for start, end, body in captions if start <= current["second"] <= end), "")
            events.append({"kind": "cliff", "second": current["second"], "change": round(delta, 2), "retention": current["retention"], "spoken": spoken})
        elif delta >= 4:
            spoken = next((body for start, end, body in captions if start <= current["second"] <= end), "")
            events.append({"kind": "spike", "second": current["second"], "change": round(delta, 2), "retention": current["retention"], "spoken": spoken})
    strongest = sorted(events, key=lambda e: abs(e["change"]), reverse=True)[:12]
    hook_window = [p for p in points if p["second"] <= 3]
    hook_drop = round(points[0]["retention"] - hook_window[-1]["retention"], 2) if len(hook_window) > 1 else 0.0
    ending = points[-1]["retention"]
    warnings = []
    if invalid_rows:
        warnings.append(f"{invalid_rows} baris invalid dilewati.")
    if duplicates:
        warnings.append(f"{duplicates} timestamp duplikat: nilai terakhir dipakai.")
    if hook_drop >= 15:
        warnings.append("Penurunan besar pada 3 detik pertama; periksa kecocokan janji pembuka dan isi.")
    if ending < 20:
        warnings.append("Retention akhir rendah; periksa durasi, pengulangan, dan payoff.")
    if not captions:
        warnings.append("Tambahkan transkrip SRT agar setiap cliff dapat dicocokkan dengan ucapan.")
    return {"normalization": {"units": selected_units, "time_column": time_key, "value_column": value_key, "invalid_rows": invalid_rows, "duplicate_timestamps": duplicates, "unknown_columns": [f for f in reader.fieldnames if f not in {time_key, value_key}]}, "points": points, "events": strongest, "summary": {"start": points[0]["retention"], "end": ending, "hook_drop": hook_drop, "average": round(sum(p["retention"] for p in points) / len(points), 2), "sample_count": len(points)}, "warnings": warnings, "method": "diagnostic_not_causal"}


def lint_package(title: str, thumbnail: str, transcript: str = "") -> dict[str, Any]:
    title = " ".join(str(title)[:MAX_TEXT_CHARS].split())
    thumbnail = " ".join(str(thumbnail)[:500].split())
    if not title:
        raise ValueError("Judul wajib diisi")
    title_words = re.findall(r"[\wÀ-ÿ]+", title.lower())
    thumb_words = re.findall(r"[\wÀ-ÿ]+", thumbnail.lower())
    overlap = sorted(set(title_words) & set(thumb_words) - {"dan", "yang", "di", "the", "a", "of"})
    issues = []
    score = 100
    if len(title) > 70:
        issues.append({"level": "warning", "message": "Judul lebih dari 70 karakter dan berisiko terpotong."}); score -= 15
    if len(title) > 100:
        issues.append({"level": "error", "message": "Judul melewati batas 100 karakter YouTube."}); score -= 25
    if len(title_words) < 3:
        issues.append({"level": "warning", "message": "Judul terlalu pendek untuk menjelaskan nilai video."}); score -= 10
    if len(thumb_words) > 6:
        issues.append({"level": "warning", "message": "Teks thumbnail lebih dari 6 kata; sederhanakan untuk layar kecil."}); score -= 12
    if thumbnail and len(overlap) >= max(2, min(len(title_words), len(thumb_words)) // 2):
        issues.append({"level": "warning", "message": "Thumbnail terlalu banyak mengulang kata pada judul."}); score -= 18
    generic = sorted(set(title_words) & _GENERIC)
    if generic and len(generic) >= max(2, len(set(title_words)) // 2):
        issues.append({"level": "info", "message": "Judul cukup generik; tambahkan hasil, konflik, atau detail konkret."}); score -= 8
    if transcript:
        source = set(re.findall(r"[\wÀ-ÿ]+", transcript.lower()))
        meaningful = [w for w in title_words if len(w) > 4 and w not in _GENERIC]
        unsupported = [w for w in meaningful if w not in source]
        if meaningful and len(unsupported) / len(meaningful) > 0.6:
            issues.append({"level": "warning", "message": "Banyak kata penting pada judul tidak muncul di transkrip; periksa akurasi janji."}); score -= 15
    if not issues:
        issues.append({"level": "ok", "message": "Pasangan judul dan thumbnail ringkas serta tidak berlebihan."})
    return {"score": max(0, score), "issues": issues, "metrics": {"title_chars": len(title), "title_words": len(title_words), "thumbnail_words": len(thumb_words), "overlap": overlap}, "method": "editorial_heuristic"}


def review_hook(hook: str) -> dict[str, Any]:
    hook = " ".join(str(hook)[:MAX_TEXT_CHARS].split())
    if not hook:
        raise ValueError("Hook wajib diisi")
    words = re.findall(r"[\wÀ-ÿ]+", hook.lower())
    checks = {
        "ringkas": 4 <= len(words) <= 18,
        "konkret": bool(re.search(r"\d|\b(cara|hasil|alasan|kesalahan|dalam|tanpa|sebelum|setelah|kenapa|mengapa|bagaimana)\b", hook.lower())),
        "curiosity": "?" in hook or bool(re.search(r"\b(ternyata|tapi|namun|jangan|rahasia|belum|bukan)\b", hook.lower())),
        "mudah_diucapkan": len(hook) <= 120 and not re.search(r"\b\w{18,}\b", hook),
        "tidak_berlebihan": not bool(re.search(r"\b(100%|pasti viral|dijamin|terbaik sepanjang masa|mustahil gagal)\b", hook.lower())),
    }
    score = round(100 * sum(checks.values()) / len(checks))
    suggestions = []
    if not checks["ringkas"]: suggestions.append("Gunakan sekitar 4-18 kata agar cepat dipahami.")
    if not checks["konkret"]: suggestions.append("Tambahkan hasil, masalah, angka, atau sudut yang konkret.")
    if not checks["curiosity"]: suggestions.append("Buat pertanyaan atau kontras yang relevan tanpa clickbait.")
    if not checks["mudah_diucapkan"]: suggestions.append("Sederhanakan agar nyaman diucapkan dalam satu napas.")
    if not checks["tidak_berlebihan"]: suggestions.append("Hapus janji absolut yang tidak dapat dibuktikan.")
    formula = "pertanyaan" if "?" in hook else "angka" if re.search(r"\d", hook) else "kontras" if re.search(r"\b(tapi|namun|bukan|jangan)\b", hook.lower()) else "hasil langsung"
    return {"score": score, "formula": formula, "checks": checks, "suggestions": suggestions or ["Hook sudah cukup jelas; validasi tetap melalui performa penonton nyata."], "method": "editorial_heuristic_not_prediction"}
