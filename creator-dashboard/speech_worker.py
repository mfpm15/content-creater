"""Free Edge speech worker with inherited proxy/CA trust. No playback or paid fallback."""
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from speech_settings import VOICES


async def synthesize(lines, output):
    import edge_tts
    # Extend the library's normal certificate trust with the configured session CA.
    # TLS verification remains enabled. No proxy or credential is logged.
    certificate=os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')
    if certificate:
        from edge_tts.communicate import _SSL_CTX
        _SSL_CTX.load_verify_locations(cafile=certificate)
    proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    for line in lines:
        mp3=output/(line['id']+'.part.mp3');wav=output/(line['id']+'.part.wav')
        temp_words=output/(line['id']+'.part.words.jsonl')
        words=output/(line['id']+'.words.jsonl')
        try:
            await edge_tts.Communicate(line['text'],line['voice'],rate=line['rate'],boundary='WordBoundary',proxy=proxy,connect_timeout=15,receive_timeout=45).save(str(mp3),str(temp_words))
            subprocess.run([shutil.which('ffmpeg'),'-v','error','-nostdin','-y','-i',str(mp3),'-map_metadata','-1','-ac','1','-ar','24000','-c:a','pcm_s16le',str(wav)],check=True,timeout=60)
            wav.replace(output/(line['id']+'.wav'))
            # Provider word boundaries are derived from the SAME audio response,
            # and never estimated from text lengths. The renderer checks them.
            if temp_words.is_file() and 0<temp_words.stat().st_size<=300_000:
                temp_words.replace(words)
        finally:
            mp3.unlink(missing_ok=True);wav.unlink(missing_ok=True);temp_words.unlink(missing_ok=True)


def main():
    source=Path(sys.argv[1]);output=Path(sys.argv[2])
    if source.is_symlink() or not source.is_file() or source.stat().st_size>2000000:raise ValueError('Input suara tidak valid')
    lines=json.loads(source.read_text('utf-8'))
    if not isinstance(lines,list) or not 1<=len(lines)<=200:raise ValueError('Daftar suara harus 1–200 scene')
    ids=set()
    for line in lines:
        if not isinstance(line,dict) or set(line)!={'id','text','voice','rate'} or not isinstance(line['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',line['id']) or line['id'] in ids:raise ValueError('Identitas scene suara tidak valid')
        if not isinstance(line['text'],str) or not line['text'].strip() or len(line['text'])>30000 or line['voice'] not in VOICES.values() or line['rate']!='+0%':raise ValueError('Teks atau pilihan suara tidak valid')
        ids.add(line['id'])
    if output.is_symlink():raise ValueError('Folder suara tidak boleh tautan')
    output.mkdir(parents=True,exist_ok=True)
    asyncio.run(synthesize(lines,output))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Sintesis suara gratis gagal ('+type(exc).__name__+'). Periksa koneksi/proxy dan coba lagi; tidak ada fallback berbayar.',file=sys.stderr)
        sys.exit(1)
