"""Optional isolated browser review of scene-midpoint text geometry."""
import os
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote


def inspect(path: Path, plan: dict, width: int, height: int) -> dict:
    executable = shutil.which('chromium') or shutil.which('google-chrome') or shutil.which('msedge')
    if not executable: return {'status':'unmeasured','reason':'Browser executable unavailable'}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {'status':'unmeasured','reason':'Optional Playwright dependency unavailable'}
    folder = path.parent.resolve()
    screenshots, issues = [], []
    class AssetHandler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(folder),**kwargs)
        def do_GET(self):
            if not Path(self.translate_path(self.path)).resolve().is_relative_to(folder):
                self.send_error(403);return
            super().do_GET()
        def list_directory(self,path):self.send_error(403);return None
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),AssetHandler)
    origin=f'http://127.0.0.1:{server.server_port}'
    threading.Thread(target=server.serve_forever,daemon=True).start()
    def allowed(url):
        parsed = urlsplit(url)
        if parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port == server.server_port:
            return (folder/unquote(parsed.path).lstrip('/')).resolve().is_relative_to(folder)
        return parsed.scheme == 'https' and parsed.hostname == 'cdn.jsdelivr.net'
    try:
        with sync_playwright() as manager:
            browser = manager.chromium.launch(executable_path=executable,
                chromium_sandbox=os.getenv('VIDEO_REVIEW_ALLOW_NO_SANDBOX') != '1')
            try:
                page = browser.new_page(viewport={'width':width,'height':height},service_workers='block',accept_downloads=False)
                page.route('**/*', lambda route: route.continue_() if allowed(route.request.url) else route.abort())
                page.goto(origin+'/'+path.name, wait_until='load', timeout=20000)
                page.wait_for_function('window.__timelines?.video',timeout=10000)
                for index, scene in enumerate(plan['scenes'][:20]):
                    point = (float(scene['start'])+float(scene['end']))/2
                    page.evaluate('(t)=>window.__timelines.video.seek(t)',point)
                    found = page.evaluate('''() => [...document.querySelectorAll('.hero-title,.subtitle-capsule,.scene-title,.subtitle')].filter(e=>{
                      let n=e;while(n){const s=getComputedStyle(n);if(s.visibility==='hidden'||s.display==='none'||Number(s.opacity)===0)return false;n=n.parentElement}return true;
                    }).filter(e=>{const r=e.getBoundingClientRect();return r.left<0||r.top<0||r.right>innerWidth+1||r.bottom>innerHeight+1||e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2}).map(e=>e.textContent.slice(0,120))''')
                    issues.extend({'scene':scene['id'],'code':'text_overflow','text':text} for text in found)
                    name=f'review-frame-{index}.png'
                    page.screenshot(path=str(folder/name))
                    screenshots.append(name)
            finally:
                browser.close()
    except Exception:
        return {'status':'unmeasured','reason':'Isolated browser/timeline unavailable; inspect preview manually'}
    finally:
        server.shutdown();server.server_close()
    return {'status':'needs_attention' if issues else 'sampled', 'method':'scene_midpoint_dom_layout',
            'issues':issues,'screenshots':screenshots,'manual_required':'Transitions, aesthetics and untested frames'}
