"""Conservative Wikimedia Commons public-domain image suggestion worker.

Intentionally NOT a general remote-image fetcher: HTTPS hosts, licenses,
response sizes, request counts, asset dimensions and redirect policy are fixed.
A failed search leaves the procedural visual, with an explicit warning.
"""
from __future__ import annotations
import base64
import html
from html.parser import HTMLParser
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import media_library

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "ContentCreatorVideoStudio/0.2 (https://github.com/mfpm15/content-creater) Python-urllib"
MAX_SHOTS = 3
MAX_ITEMS = 6
MAX_API_BYTES = 230_000
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_MATCH_LEN = 4
STOPWORDS = frozenset("dan atau untuk yang dengan dalam dari ini itu lalu sebuah pada ketika bagaimana adalah karena proses konsep penting gambar video teks tentang lebih adalah menunjukkan kita dia saya anda scene shot".split())


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def _plain(value: str, limit: int = 120) -> str:
    parser = _Text()
    parser.feed(str(value)[:2500])
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()[:limit]


def _query(scene: dict) -> str:
    raw = str(scene.get("subject") or scene.get("directionSubject") or scene.get("onScreenText") or "").strip()
    words = [w for w in re.findall(r"[\w-]{4,}", raw, flags=re.UNICODE) if w.casefold() not in STOPWORDS]
    return " ".join(words[:4])[:90]


def _license(meta: dict) -> str | None:
    lic = _plain((meta.get("LicenseShortName") or {}).get("value") or "", 80).casefold()
    # Only public-domain and CC0. Licenses requiring attribution/sharing are
    # omitted until automated credit/derivative compliance is implemented.
    if lic.startswith("cc0") or lic in {"public domain", "public domain mark", "pd", "pdm"}:
        return lic
    return None


def _wikimedia_thumbnail(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    return u.scheme == "https" and u.hostname == "upload.wikimedia.org" and u.port is None and (
        u.path.startswith("/wikipedia/commons/thumb/") or u.path.startswith("/wikipedia/commons/")
    ) and not u.username and not u.password and not u.fragment


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect unduhan media ditolak")


def _download(url: str, cap: int) -> bytes:
    # Only callers with fixed API or URL verified by _wikimedia_thumbnail.
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,image/*"})
    with urllib.request.build_opener(_NoRedirect()).open(req, timeout=9) as res:
        if res.status != 200:
            raise ValueError("Provider media tidak memberi HTTP 200")
        content_length = res.headers.get("Content-Length")
        if content_length and int(content_length) > cap:
            raise ValueError("Media terlalu besar")
        data = res.read(cap + 1)
        if len(data) > cap:
            raise ValueError("Response media terlalu besar")
        return data


def _search(query: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrnamespace": "6", "gsrsearch": query + " filetype:bitmap",
        "gsrlimit": str(MAX_ITEMS), "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl",
        "iiurlwidth": "960", "maxlag": "5",
    })
    payload = json.loads(_download(API + "?" + params, MAX_API_BYTES))
    if not isinstance(payload, dict):
        raise ValueError("Respons pencarian Commons bukan objek JSON")
    query_result = payload.get("query") or {}
    if not isinstance(query_result, dict):
        raise ValueError("Struktur hasil pencarian Commons tidak valid")
    pages = query_result.get("pages") or []
    if not isinstance(pages, list):
        raise ValueError("Daftar hasil pencarian Commons tidak valid")
    return pages[:MAX_ITEMS]


def suggest(plan: dict, *, limit: int = MAX_SHOTS) -> dict:
    """Mutate an in-memory plan, never auto-publish. Human review still required."""
    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list):
        raise ValueError("Scene Plan tidak valid")
    if type(limit) is not int or not 1 <= limit <= MAX_SHOTS:
        raise ValueError("Batas media otomatis tidak valid")
    added, problems, used_files = [], [], set()
    attempts = 0
    for scene in plan["scenes"]:
        # Cap *attempted lookups*, not successful downloads. Without this,
        # a 200-scene film with no Commons matches could make 200 HTTP queries.
        if attempts >= limit:
            break
        if not isinstance(scene, dict):
            problems.append({"scene": "", "reason": "Struktur adegan tidak valid"})
            continue
        if scene.get("assetId"):
            continue
        query = _query(scene)
        if not query:
            continue
        attempts += 1
        try:
            pages = _search(query)
        except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeError) as exc:
            problems.append({"scene": scene.get("id", ""), "reason": "Pencarian media gagal atau dibatasi provider", "errorType": type(exc).__name__})
            continue
        matched = False
        keywords = {w.casefold() for w in query.split() if len(w) >= MIN_MATCH_LEN}
        for page in pages[:MAX_ITEMS]:
            if not isinstance(page, dict):
                continue
            details = page.get("imageinfo")
            if not isinstance(details, list) or not details or not isinstance(details[0], dict):
                continue
            info = details[0]
            metadata = info.get("extmetadata")
            if not isinstance(metadata, dict):
                continue
            try:
                license_name = _license(metadata)
            except (ValueError, AttributeError, TypeError):
                continue
            url = info.get("thumburl") or ""
            title = str(page.get("title") or "")
            if not isinstance(url, str) or not license_name or not _wikimedia_thumbnail(url) or url in used_files:
                continue
            if not any(k in title.casefold() for k in keywords):
                continue
            description = info.get("descriptionurl") or ""
            if not (isinstance(description, str) and description.startswith("https://commons.wikimedia.org/wiki/File:")):
                continue
            try:
                raw = _download(url, MAX_IMAGE_BYTES)
                data = media_library.save({
                    "name": _plain(title.removeprefix("File:"), 120) or "Gambar Wikimedia",
                    "source": (description + " | Lisensi: " + license_name + " (metadata Wikimedia; perlu pemeriksaan)").strip()[:400],
                    "creator": _plain((metadata.get("Artist") or {}).get("value") or "Wikimedia Commons", 120),
                    "rightsConfirmed": True,  # Provider states CC0/PD; legal rights remain unverified
                    "externalLicenseMetadata": True,
                    "base64": base64.b64encode(raw).decode("ascii"),
                })
            except (ValueError, OSError, urllib.error.URLError):
                continue
            scene["assetId"] = data["id"]
            used_files.add(url)
            added.append({"scene": scene.get("id", ""), "assetId": data["id"], "source": description,
                          "license": license_name, "query": query, "rightsReviewRequired": True})
            matched = True
            break
        if not matched:
            problems.append({"scene": scene.get("id", ""), "reason": "Belum menemukan gambar domain publik yang cocok; visual ilustrasi tetap dipakai"})
    return {"mode": "commons_cc0_public_domain", "status": "review_required",
            "attemptedSearches": attempts, "maxSearches": limit,
            "assets": added, "warnings": problems,
            "note": "Hasil otomatis menggunakan metadata lisensi Commons, BUKAN verifikasi hukum atau bukti foto peristiwa. Periksa kecocokan gambar dan sumber sebelum publikasi."}
