"""Opt-in public text retrieval; explicit admin host allowlist and no redirects/credentials."""
import ipaddress
import os
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit
from evidence import safe_url


class TextParser(HTMLParser):
    def __init__(self): super().__init__();self.skip=0;self.parts=[];self.published_at=None
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript'}: self.skip+=1
        values=dict(attrs)
        if tag=='meta' and values.get('property') in {'article:published_time','datePublished'}: self.published_at=values.get('content')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'}: self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(data.strip())


def retrieve(url: str) -> dict:
    url=safe_url(url);host=urlsplit(url).hostname
    allowed={h.strip().lower() for h in os.getenv('RESEARCH_SOURCE_HOSTS','').split(',') if h.strip()}
    if host.lower() not in allowed:raise ValueError('Host sumber belum diizinkan pada RESEARCH_SOURCE_HOSTS; gunakan kutipan manual atau konfigurasi host tersebut')
    if urlsplit(url).port not in (None,443):raise ValueError('Hanya port HTTPS standar yang diizinkan')
    try:addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except OSError:raise ValueError('DNS sumber tidak tersedia') from None
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses): raise ValueError('Hanya sumber publik yang diizinkan')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    request=urllib.request.Request(url,headers={'Accept':'text/html,text/plain','Accept-Encoding':'identity','User-Agent':'CreatorSourceReview/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
            if response.headers.get_content_type() not in {'text/html','text/plain'}:raise ValueError('Sumber bukan teks/HTML')
            if response.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Encoding sumber tidak didukung')
            raw=response.read(1000001)
            if len(raw)>1000000:raise ValueError('Sumber melebihi 1 MB')
    except (OSError,urllib.error.URLError):raise ValueError('Sumber tidak dapat diambil; gunakan kutipan manual') from None
    parser=TextParser();parser.feed(raw.decode('utf-8','replace'))
    return {'url':url,'excerpt':'\n'.join(parser.parts)[:20000],'published_at':parser.published_at,'verified':False,
            'review':'Retrieved text is untrusted evidence; review claims and dates before linking'}
