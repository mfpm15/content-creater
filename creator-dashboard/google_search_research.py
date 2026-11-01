"""Google Search grounded research worker for Video Studio.

Reads one JSON object from stdin and writes one JSON object to stdout.
This worker is intentionally isolated so Creator Dashboard can reuse the
Podcastfy virtual environment where google-genai is already installed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import urlparse


def _value(item, name, default=None):
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _source_quality(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith((".go.id", ".gov", ".gov.uk", ".europa.eu", ".int")):
        return "primary-government"
    if host.endswith((".edu", ".ac.id", ".org")):
        return "institutional"
    return "web"


def research(topic: str, context: str, model: str) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Google Search grounding memerlukan GOOGLE_API_KEY atau GEMINI_API_KEY")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    prompt = f"""Lakukan riset web untuk brief video berikut.
Topik: {topic}
Konteks pengguna: {context or '(tidak ada)'}

Gunakan Google Search. Prioritaskan sumber primer, situs resmi, regulator, dokumentasi resmi, jurnal, dan laporan institusi. Jangan mengarang fakta, angka, tanggal, URL, atau kutipan. Bandingkan sumber jika klaim penting berpotensi berubah. Tulis ringkasan faktual dalam Bahasa Indonesia. Tandai ketidakpastian. Gunakan hanya informasi yang didukung hasil pencarian."""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )

    candidate = (response.candidates or [None])[0]
    metadata = _value(candidate, "grounding_metadata")
    chunks = _value(metadata, "grounding_chunks", []) or []
    sources = []
    seen = set()
    for chunk in chunks:
        web = _value(chunk, "web")
        url = str(_value(web, "uri", "") or "").strip()
        title = str(_value(web, "title", "") or url).strip()
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        sources.append({
            "id": len(sources) + 1,
            "title": title,
            "url": url,
            "publisher": urlparse(url).hostname or "",
            "quality": _source_quality(url),
        })

    if not sources:
        raise RuntimeError("Google Search tidak mengembalikan sumber grounding yang dapat diverifikasi")

    queries = [str(item) for item in (_value(metadata, "web_search_queries", []) or []) if str(item).strip()]
    return {
        "provider": "Google Search grounding",
        "model": model,
        "topic": topic,
        "summary": str(response.text or "").strip(),
        "queries": queries,
        "sources": sources,
        "sourceCount": len(sources),
        "researchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verified": True,
    }


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    result = research(
        str(payload.get("topic") or "").strip(),
        str(payload.get("context") or "").strip(),
        str(payload.get("model") or "gemini-2.5-flash").strip(),
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise
