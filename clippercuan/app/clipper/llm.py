"""Klien LLM untuk router kompatibel OpenAI (9router, OpenRouter, LiteLLM, dsb).

Dipakai untuk:
  - memilih momen paling viral dari kandidat transkrip  (model "moments")
  - membuat judul hook pembuka                          (model "titles")
  - membuat caption posting + hashtag                   (model "titles")
Jika LLM mati / gagal, aplikasi otomatis kembali ke skor lokal.
"""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request

from .config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_LLM_BASE_URL = "http://localhost:20128/v1"
DEFAULT_LLM_MODEL = "ag/gemini-3.8-flash-medium"
DEFAULT_LLM = {
    "enabled": False,
    "base_url": DEFAULT_LLM_BASE_URL,
    "api_key": "",
    "model_moments": DEFAULT_LLM_MODEL,
    "model_titles": DEFAULT_LLM_MODEL,
    "temperature": 0.4,
    "timeout": 60,
}


def normalize_base_url(value: str) -> str:
    """Normalisasi root OpenAI-compatible tanpa menggandakan /v1."""
    value = value.strip().rstrip("/")
    if not value:
        return DEFAULT_LLM_BASE_URL
    return value if value.endswith("/v1") else value + "/v1"


def environment_llm() -> dict:
    """Sumber config bersama dashboard; credential tetap hanya di environment proses."""
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    timeout = os.getenv("LLM_TIMEOUT")
    out: dict = {}
    if base_url:
        out["base_url"] = normalize_base_url(base_url)
    if api_key:
        out["api_key"] = api_key
    if model:
        out.update(model_moments=model, model_titles=model)
    if timeout:
        try:
            out["timeout"] = max(1.0, float(timeout))
        except ValueError:
            pass
    return out


# ------------------------------------------------------------------ settings
DEFAULT_ASR = {                 # transkripsi cloud kompatibel OpenAI (/audio/transcriptions)
    "base_url": "https://api.groq.com/openai/v1",
    "api_key": "",
    "model": "whisper-large-v3",
    "timeout": 600,
}

DEFAULT_DOWNLOAD = {
    "cookies_browser": "",      # chrome | edge | firefox | brave | safari — dipakai bila YouTube minta verifikasi
}

DEFAULT_AUTOMATION = {
    "webhook_url": "",          # POST JSON saat proyek selesai/gagal (untuk AI agent / n8n / Zapier)
    "inbox_enabled": False,     # proses otomatis video yang ditaruh di folder inbox
    "inbox_template": "",       # nama template gaya untuk inbox ("" = pengaturan bawaan)
    "export_dir": "",           # salin hasil klip otomatis ke folder ini
}


def load_settings() -> dict:
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text("utf-8"))
        except Exception:
            data = {}
    configured = {**DEFAULT_LLM, **data.get("llm", {}), **environment_llm()}
    configured["base_url"] = normalize_base_url(configured["base_url"])
    return {"llm": configured,
            "automation": {**DEFAULT_AUTOMATION, **data.get("automation", {})},
            "asr": {**DEFAULT_ASR, **data.get("asr", {})},
            "download": {**DEFAULT_DOWNLOAD, **data.get("download", {})}}


def _write_settings(data: dict) -> None:
    """Simpan pengaturan secara atomik agar file lama tidak rusak bila proses terhenti saat menulis."""
    temporary = SETTINGS_FILE.with_suffix(SETTINGS_FILE.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=1), "utf-8")
        temporary.replace(SETTINGS_FILE)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def save_settings(new: dict) -> dict:
    cur = load_settings()
    if "llm" in new:
        llm = {k: v for k, v in new["llm"].items() if k in DEFAULT_LLM}
        if llm.get("api_key") == "••••":   # UI mengirim mask = tidak diubah
            llm.pop("api_key")
        cur["llm"].update(llm)
        cur["llm"]["base_url"] = normalize_base_url(cur["llm"]["base_url"])
    if "asr" in new:
        asr = {k: v for k, v in new["asr"].items() if k in DEFAULT_ASR}
        if asr.get("api_key") == "••••":
            asr.pop("api_key")
        cur["asr"].update(asr)
        cur["asr"]["base_url"] = cur["asr"]["base_url"].strip().rstrip("/")
    if "download" in new:
        cur["download"].update({k: str(v).strip().lower() for k, v in new["download"].items() if k in DEFAULT_DOWNLOAD})
    if "automation" in new:
        cur["automation"].update({k: v for k, v in new["automation"].items() if k in DEFAULT_AUTOMATION})
    _write_settings(cur)
    return cur


def public_settings() -> dict:
    s = load_settings()
    s["llm"]["api_key"] = "••••" if s["llm"]["api_key"] else ""
    s["asr"]["api_key"] = "••••" if s["asr"]["api_key"] else ""
    return s


def cfg() -> dict:
    return load_settings()["llm"]


def explicitly_configured(c: dict | None = None) -> bool:
    """Bedakan konfigurasi nyata dari placeholder bawaan; router lokal tidak wajib API key."""
    c = c or cfg()
    saved = {}
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text("utf-8")).get("llm", {})
        except Exception:
            pass
    env = environment_llm()
    explicit_endpoint = bool(env.get("base_url") or saved.get("base_url") or saved.get("enabled"))
    return bool(explicit_endpoint and c.get("base_url") and c.get("model_moments"))


def active(task: str = "moments") -> bool:
    c = cfg()
    return bool(c["enabled"] and explicitly_configured(c) and c["base_url"] and c.get(f"model_{task}"))


# ------------------------------------------------------------------ transport
class LLMError(RuntimeError):
    pass


def _req(path: str, body: dict | None = None, c: dict | None = None, timeout: float | None = None) -> dict:
    c = c or cfg()
    url = c["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "User-Agent": "ClipperCuan/1.0"}
    if c.get("api_key"):
        headers["Authorization"] = "Bearer " + c["api_key"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout or c.get("timeout", 60)) as r:
            payload = json.loads(r.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise LLMError(f"Respons JSON dari {url} harus berupa object")
            return payload
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"HTTP {e.code} dari {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"Tidak bisa terhubung ke {url} ({e.reason}). Pastikan 9router berjalan.") from None
    except (TimeoutError, socket.timeout):
        raise LLMError(f"Timeout saat menghubungi {url}. Periksa 9Router atau naikkan LLM_TIMEOUT.") from None
    except json.JSONDecodeError:
        raise LLMError(f"Respons bukan JSON dari {url}") from None


def list_models(c: dict | None = None) -> list[str]:
    data = _req("/models", c=c, timeout=20)
    items = data.get("data", data if isinstance(data, list) else [])
    return sorted({m.get("id") if isinstance(m, dict) else str(m) for m in items} - {None})


def chat(model: str, system: str, user: str, c: dict | None = None, max_tokens: int = 4000, json_mode: bool = False) -> str:
    c = c or cfg()
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": float(c.get("temperature", 0.4)),
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _req("/chat/completions", body, c=c)
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Format respons tak dikenal: {str(data)[:300]}")
    content = msg.get("content")
    if isinstance(content, list):  # beberapa router mengirim potongan konten
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not content:
        raise LLMError("Model mengembalikan jawaban kosong (coba naikkan batas token atau ganti model).")
    return content


def _json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError("Model tidak mengembalikan JSON")
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    raise LLMError("JSON dari model tidak valid")


# ------------------------------------------------------------------ tugas
SYS_EDITOR = (
    "Kamu editor video pendek profesional. Nilai secara akurat, bukan menjanjikan viral. Pertahankan ucapan asli; "
    "jangan membuat klaim, engagement bait, atau konteks baru. Utamakan hook 0-3 detik, novelty, emotional shift, "
    "clarity tanpa konteks, payoff, quotability, visual action, information density, clean ending. Penalti intro lambat, "
    "pengulangan, filler, dependensi konteks, klaim menggantung, dan potongan tengah kalimat. Jawab HANYA JSON valid."
)


def pick_moments(cands: list[dict], count: int, language: str | None) -> list[dict]:
    """cands: [{id, start, end, text}] → [{id, score, title, reason, hashtags}] urut terbaik."""
    c = cfg()
    lines = [f'#{x["id"]} [{x["start"]:.0f}s–{x["end"]:.0f}s, {x["end"] - x["start"]:.0f}dtk]: {x["text"][:900]}' for x in cands]
    user = (
        f"Bahasa video: {language or 'tidak diketahui'}. Pilih {count} kandidat TERBAIK yang tidak saling tumpang tindih "
        f"dari daftar berikut.\n\n" + "\n\n".join(lines) +
        "\n\nUntuk tiap pilihan buat judul akurat maksimal 8 kata. Beri confidence dan seluruh dimensi 0-100.\n"
        'Format: {"clips":[{"id":1,"score":80,"confidence":0.8,"title":"...","reason":"...",'
        '"breakdown":{"hook":0,"novelty":0,"emotional_shift":0,"clarity":0,"payoff":0,"quotability":0,'
        '"visual_action":0,"information_density":0,"clean_ending":0},"hashtags":["#topik"]}]}'
    )
    out = _json(chat(c["model_moments"], SYS_EDITOR, user, c, json_mode=True))
    clips = out.get("clips", out) if isinstance(out, dict) else out
    res = []
    for x in clips if isinstance(clips, list) else []:
        try:
            score = max(0, min(100, int(x.get("score", 80))))
            breakdown = {k: max(0, min(100, int(v))) for k, v in (x.get("breakdown") or {}).items() if isinstance(v, (int, float))}
            res.append({"id": int(str(x["id"]).lstrip("#")), "score": score,
                        "confidence": max(0.0, min(1.0, float(x.get("confidence", .6)))),
                        "title": str(x.get("title", "")).strip()[:80], "reason": str(x.get("reason", ""))[:240],
                        "breakdown": breakdown, "hashtags": [str(h) for h in x.get("hashtags", []) if str(h).startswith("#")][:8]})
        except (KeyError, ValueError, TypeError):
            continue
    if not res:
        raise LLMError("Model tidak memilih klip apa pun")
    return res


def make_title(text: str, language: str | None, style: str = "penasaran") -> list[str]:
    c = cfg()
    model = c["model_titles"] or c["model_moments"]
    user = (f"Transkrip klip:\n{text[:2500]}\n\nBuat 3 alternatif judul pembuka akurat ({style}), maksimal 8 kata, "
            f"bahasa sama dengan transkrip ({language or 'auto'}). Format: {{\"titles\":[\"...\"]}}")
    out = _json(chat(model, SYS_EDITOR, user, c, max_tokens=1500))
    titles = out.get("titles", []) if isinstance(out, dict) else out
    return [str(t).strip()[:80] for t in titles if str(t).strip()][:3]


def make_post(text: str, title: str, language: str | None) -> dict:
    c = cfg()
    model = c["model_titles"] or c["model_moments"]
    user = (f"Judul klip: {title}\nTranskrip:\n{text[:2500]}\n\nTulis caption value-first: pembuka manfaat, konteks singkat, "
             f"CTA natural. Buat 4-7 hashtag terkelompok niche/topic/format tanpa spam, bahasa {language or 'sama dengan transkrip'}. "
             'Format: {"caption":"...","hashtags":["#..."],"groups":{"niche":[],"topic":[],"format":[]}}')
    out = _json(chat(model, SYS_EDITOR, user, c, max_tokens=1500))
    return {"caption": str(out.get("caption", ""))[:1200],
            "hashtags": [str(h) for h in out.get("hashtags", []) if str(h).startswith("#")][:7],
            "hashtag_groups": out.get("groups", {})}
