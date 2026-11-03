"""Read-only local runtime checks. Never contacts providers or reads credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from runtime_config import find_browser, resolve_python

ROOT = Path(__file__).resolve().parent


def command_ok(command, timeout=30):
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ffmpeg_features(binary, option, required):
    try:
        result=subprocess.run([binary,'-hide_banner',option],capture_output=True,timeout=15,check=False)
        names={line.split()[1] for line in result.stdout.decode('utf-8','replace').splitlines() if len(line.split())>1}
        return result.returncode==0 and set(required)<=names
    except (OSError,subprocess.TimeoutExpired):
        return False


def inspect():
    checks = []
    def check(name, good, fix):
        checks.append({'check': name, 'status': 'passed' if good else 'missing', 'action': '' if good else fix})
    python = resolve_python(ROOT)
    check('Dashboard Python', python.is_file(), 'Jalankan setup-core.bat')
    check('Diagram, browser automation, Google Search SDK', command_ok([str(python), '-c', 'from PIL import Image; import playwright; from google import genai']), 'Jalankan ulang setup-core.bat')
    clipper = resolve_python(ROOT.parent/'clippercuan'/'app')
    check('Clipper runtime', command_ok([str(clipper), '-c', 'import fastapi, uvicorn, faster_whisper, cv2, yt_dlp']), 'Jalankan ulang setup-core.bat')
    node = shutil.which('node')
    check('Node.js 22+', bool(node) and command_ok([node, '-e', "process.exit(Number(process.versions.node.split('.')[0])>=22?0:1)"]), 'Pasang Node.js 22+ lalu buka terminal baru')
    for binary in ('ffmpeg', 'ffprobe'):
        found = shutil.which(binary)
        check(binary, bool(found) and command_ok([found, '-version']), 'Pasang FFmpeg/FFprobe dan tambahkan ke PATH')
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        check('FFmpeg libass subtitle', ffmpeg_features(ffmpeg,'-filters',['subtitles']), 'Gunakan build FFmpeg dengan libass/subtitles')
        check('FFmpeg H.264/AAC encoder', ffmpeg_features(ffmpeg,'-encoders',['libx264','aac']), 'Gunakan build FFmpeg dengan libx264 dan AAC')
        check('FFmpeg loudnorm', command_ok([ffmpeg,'-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t','0.1','-af','loudnorm','-f','null','-']), 'Gunakan build FFmpeg lengkap dengan loudnorm')
    check('Chrome/Edge', bool(find_browser()), 'Pasang Chrome/Edge atau atur HYPERFRAMES_BROWSER_PATH')
    app = ROOT/'apps'/'video-studio-remotion'
    check('Remotion runtime', bool(node) and command_ok([node,'--input-type=module','-e',"import {createRequire} from 'node:module'; const r=createRequire(process.argv[1]); r('@remotion/renderer'); r('@remotion/bundler');",str(app/'package.json')]), 'Jalankan ulang setup-core.bat')
    checks.append({'check':'Google Search credential','status':'configured_not_connected' if os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') else 'optional_not_configured','action':'Riset web memerlukan API key dan akses provider; pemeriksaan ini tidak melakukan panggilan jaringan'})
    return {'ok': all(row['status'] != 'missing' for row in checks), 'checks': checks,
            'scope':'Local dependencies only; GPU, model downloads, providers and editorial quality require separate tests'}


if __name__ == '__main__':
    report=inspect()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(0 if report['ok'] else 1)
