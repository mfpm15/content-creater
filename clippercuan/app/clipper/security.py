"""Redaction for public logs and errors. Never persist runtime credentials."""
import os
import re
import json
import base64
from urllib.parse import quote, unquote

_SECRETS = set()


def register_secrets(values):
    for value in values:
        if isinstance(value, str) and len(value) >= 4:
            _SECRETS.add(value)


def redact(value: str, secrets=()) -> str:
    text = str(value)
    for secret in tuple(_SECRETS) + tuple(secrets):
        if isinstance(secret, str) and len(secret) >= 4:
            for value in {secret,quote(secret,safe=''),json.dumps(secret)[1:-1]}:
                text = text.replace(value, "[REDACTED]")
    for name, secret in os.environ.items():
        if any(tag in name.upper() for tag in ("API_KEY", "TOKEN", "PASSWORD", "SECRET")) and len(secret) >= 4:
            for value in {secret,quote(secret,safe=''),json.dumps(secret)[1:-1]}:
                text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    def basic(match):
        try:
            if b':' in base64.b64decode(match[2],validate=True):return match[1]+'[REDACTED]'
        except ValueError:pass
        return match[0]
    text = re.sub(r'(?i)(Basic\s+)([A-Za-z0-9+/]+=*)',basic,text)
    text = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", text)
    def query(match):
        key=unquote(match[2])
        if re.search(r'token|secret|signature|credential|authorization|password|(?:^|[_-])key$',key,re.I):
            return match[1]+match[2]+'=[REDACTED]'
        return match[0]
    return re.sub(r'([?&])([^=&\s]+)=([^&\s]+)',query,text)


def open_authenticated(request, timeout):
    """Keep credentials on the configured TLS endpoint; never follow redirects."""
    import urllib.request
    from urllib.parse import urlsplit
    parsed = urlsplit(request.full_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider URL tidak boleh memuat credential, query, atau fragment")
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        raise ValueError("Provider remote wajib HTTPS")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)
