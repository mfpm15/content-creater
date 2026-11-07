"""Web research through Tavily (direct REST, no Google and no 9Router) for Video Studio and articles.

Requires TAVILY_API_KEY. Results keep a stable shape and claims stay unverified:
a search result is a lead, not a fact-check.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from urllib.parse import urlparse

from security import open_authenticated

URL = "https://api.tavily.com/search"


def available() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def _post(url: str, key: str, body: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with open_authenticated(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _quality(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith((".go.id", ".gov", ".gov.uk", ".europa.eu", ".int")):
        return "primary-government"
    if host.endswith((".edu", ".ac.id")):
        return "institutional"
    return "web"


def search(topic: str, context: str = "") -> dict:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("Riset web memerlukan TAVILY_API_KEY di .env, lalu restart dashboard")
    query = " ".join(part for part in (topic.strip(), context.strip()[:160]) if part)[:390]
    data = _post(URL, key, {"query": query, "max_results": 6, "search_depth": "basic", "include_answer": True}, 30)
    sources, seen = [], set()
    for row in data.get("results") or []:
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
