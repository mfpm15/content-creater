"""Redaction for public logs and errors. Never persist runtime credentials."""
import os
import re
import json
import base64
import html
from urllib.parse import quote, unquote


def redact_tree(value):
    """Redact before JSON encoding so quotes/backslashes cannot evade matching."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_tree(item) for item in value]
    if isinstance(value, tuple):
        return [redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {redact(str(key)): redact_tree(item) for key, item in value.items()}
    return value


def local_request_allowed(host, origin, port, fetch_site=None):
    """The dashboard has no public authentication: require its exact local origin."""
    from urllib.parse import urlsplit
    try:
        if not host or any(char in host for char in '/\\@?#,') or any(ord(char)<=32 for char in host):
            return False
        parsed=urlsplit('http://'+host)
        if parsed.hostname not in {'127.0.0.1','localhost','::1'} or (parsed.port or 80)!=port:
            return False
        if fetch_site=='cross-site':
            return False
        if origin is not None:
            other=urlsplit(origin)
            if other.scheme!='http' or other.netloc.lower()!=parsed.netloc.lower() or other.path or other.query or other.fragment:
                return False
        return True
    except (ValueError,TypeError):
        return False


def render_environment():
    """Browser rendering does not need the application's provider credentials."""
    from runtime_config import find_browser
    result=os.environ.copy()
    for name in tuple(result):
        application=name.startswith(('ARTICLE_','VIDEO_','LLM_','OPENAI_','CLIPPER_'))
        if name in {'GOOGLE_API_KEY','GEMINI_API_KEY'} or application and any(tag in name for tag in ('API_KEY','TOKEN','PASSWORD','SECRET')):
            result.pop(name)
    result['HYPERFRAMES_NO_TELEMETRY']='1'
    browser=find_browser()
    if browser:result['HYPERFRAMES_BROWSER_PATH']=browser
    # Proxy/CA settings, injected runtime authentication and platform guards remain inherited.
    return result


def redact(value: str) -> str:
    text = str(value)
    for name, secret in os.environ.items():
        if any(tag in name.upper() for tag in ("API_KEY", "TOKEN", "PASSWORD", "SECRET")) and len(secret) >= 4:
            for value in {secret,quote(secret,safe=''),json.dumps(secret)[1:-1],html.escape(secret),html.escape(secret,quote=False)}:
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
