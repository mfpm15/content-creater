"""Web research through Tavily for Video Studio.

Order: TAVILY_API_KEY (direct, HTTPS) first, otherwise 9Router's /v1/search with
provider "tavily" when that provider has credentials in 9Router. Results keep the
same shape as the Google grounding worker, and claims stay unverified.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from security import open_authenticated

DIRECT_URL = "https://api.tavily.com/search"
_PROBE: dict = {"at": 0.0, "ok": False}
PROBE_TTL = 600


def _router_base() -> str:
    return (os.getenv("VIDEO_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "http://localhost:20128/v1").rstrip("/")


def _router_key() -> str:
    return os.getenv("VIDEO_LLM_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "9router-local"


def _post(url: str, key: str, body: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with open_authenticated(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def available() -> bool:
    """True when Tavily can be reached. The 9Router probe is cached because it spends one search credit."""
    if os.getenv("TAVILY_API_KEY"):
        return True
    now = time.time()
    if now - _PROBE["at"] < PROBE_TTL:
        return _PROBE["ok"]
    try:
        _post(f"{_router_base()}/search", _router_key(), {"query": "ping", "provider": "tavily", "max_results": 1}, 8)
        ok = True
    except (urllib.error.URLError, OSError, ValueError):
        ok = False
    _PROBE.update(at=now, ok=ok)
    return ok


def _quality(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith((".go.id", ".gov", ".gov.uk", ".europa.eu", ".int")):
        return "primary-government"
    if host.endswith((".edu", ".ac.id")):
        return "institutional"
    return "web"


def search(topic: str, context: str = "") -> dict:
    query = " ".join(part for part in (topic.strip(), context.strip()[:160]) if part)[:390]
    body = {"query": query, "max_results": 6, "search_depth": "basic", "include_answer": True}
    direct = os.getenv("TAVILY_API_KEY")
    if direct:
        data = _post(DIRECT_URL, direct, body, 30)
    else:
        data = _post(f"{_router_base()}/search", _router_key(), {**body, "provider": "tavily"}, 40)
    rows = data.get("results") or (data.get("data") or {}).get("results") or []
    sources, seen = [], set()
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        sources.append({"id": len(sources) + 1, "title": str(row.get("title") or url).strip(), "url": url,
            "publisher": urlparse(url).hostname or "", "quality": _quality(url), "publicationDate": None,
            "retrievalStatus": "search_result", "claimVerification": "unverified",
            "excerpt": str(row.get("content") or "")[:400]})
    if not sources:
        raise RuntimeError("Tavily tidak menghasilkan sumber")
    summary = str(data.get("answer") or "").strip() or "\n".join(
        f"- {item['title']}: {item['excerpt']}" for item in sources[:4])
    return {"provider": "Tavily", "model": "tavily-search", "topic": topic, "summary": summary,
        "queries": [query], "sources": sources, "sourceCount": len(sources),
        "researchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "verified": False,
        "verificationStatus": "search_results_found_claims_unverified"}
