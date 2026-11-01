"""Redaction for public logs and errors. Never persist runtime credentials."""
import os
import re

_SECRETS = set()


def register_secrets(values):
    for value in values:
        if isinstance(value, str) and len(value) >= 4:
            _SECRETS.add(value)


def redact(value: str, secrets=()) -> str:
    text = str(value)
    for secret in tuple(_SECRETS) + tuple(secrets):
        if isinstance(secret, str) and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED]")
    for name, secret in os.environ.items():
        if any(tag in name.upper() for tag in ("API_KEY", "TOKEN", "PASSWORD", "SECRET")) and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", text)
    return re.sub(r"(?i)([?&](?:api_key|key|token|secret)=)[^&\s]+", r"\1[REDACTED]", text)


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
