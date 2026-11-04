"""Bounded, private production handoff archives. Never include the working directory wholesale."""
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import zipfile
from contextlib import contextmanager
from pathlib import Path

from security import redact, redact_tree

MAX_BYTES=2*1024**3
MAX_TEXT_BYTES=4_000_000
FILES=('video.mp4','lottie.json','index.html','subtitles.srt','scene-plan.json','narration.json','production-prompts.json','audio-manifest.json','research.json','review.json',
       'final-audio.wav','voice.wav','music-foley.wav','remotion-timeline.json','render-report.json','audio-mastering.json')
GATE=threading.BoundedSemaphore(1)
SENSITIVE={'apikey','token','accesstoken','refreshtoken','password','clientsecret','privatekey','authorization','secret'}


class BundleBusy(ValueError):pass


def _clean(value):
    if isinstance(value,dict):
        return {key:'[REDACTED]' if re.sub(r'[^a-z]','',key.lower()) in SENSITIVE else _clean(item) for key,item in value.items()}
    if isinstance(value,list):return [_clean(item) for item in value]
    return redact_tree(value)


def _linked(path):
    return path.is_symlink() or bool(getattr(path,'is_junction',lambda:False)())


@contextmanager
def build(directory: Path):
    if not GATE.acquire(blocking=False):raise BundleBusy('Paket lain sedang disiapkan; coba lagi sebentar')
    acquired=True
    try:
        if _linked(directory) or not directory.is_dir():raise ValueError('Project tidak tersedia')
        root=directory.resolve();selected=[];total=0
        for name in (*FILES,*(f'review-frame-{i}.png' for i in range(20))):
            path=root/name
            if _linked(path):raise ValueError('Paket tidak menerima file tautan')
            if not path.exists():continue
            if not path.is_file() or path.resolve().parent!=root:raise ValueError('Artefak tidak valid')
            size=path.stat().st_size;total+=size
            if total>MAX_BYTES or path.suffix in {'.json','.html','.srt'} and size>MAX_TEXT_BYTES:
                raise ValueError('Paket terlalu besar; unduh video secara terpisah')
            selected.append(path)
        if not any(path.name in {'video.mp4','lottie.json'} for path in selected):raise ValueError('Hasil video belum tersedia')
        with tempfile.TemporaryDirectory(prefix='.handoff-',dir=root) as folder:
            target=Path(folder)/'production-bundle.zip';manifest=[];review_status='unmeasured';written_total=0;review_digest=None
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
                for path in selected:
                    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                    with os.fdopen(fd,'rb') as source:
                        info=os.fstat(source.fileno())
                        if not stat.S_ISREG(info.st_mode):raise ValueError('Artefak bukan file biasa')
                        digest=hashlib.sha256();size=0
                        entry=zipfile.ZipInfo(path.name)
                        entry.compress_type=zipfile.ZIP_STORED if path.suffix in {'.mp4','.png','.wav'} else zipfile.ZIP_DEFLATED
                        entry.external_attr=0o600<<16
                        with archive.open(entry,'w',force_zip64=True) as output:
                            if path.suffix in {'.json','.html','.srt'}:
                                raw=source.read(MAX_TEXT_BYTES+1)
                                if len(raw)>MAX_TEXT_BYTES:raise ValueError('Artefak teks terlalu besar')
                                if path.suffix=='.json':
                                    data=_clean(json.loads(raw))
                                    if path.name=='review.json' and isinstance(data,dict):
                                        review_status=str(data.get('status','unmeasured'));review_digest=data.get('artifact_sha256')
                                    raw=json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')
                                else:raw=redact(raw.decode('utf-8')).encode('utf-8')
                                output.write(raw);digest.update(raw);size=len(raw)
                            else:
                                while block:=source.read(512*1024):
                                    size+=len(block)
                                    if size>info.st_size or size>MAX_BYTES:raise ValueError('Artefak berubah saat paket dibuat; ulangi')
                                    output.write(block);digest.update(block)
                                if size!=info.st_size:raise ValueError('Artefak berubah saat paket dibuat; ulangi')
                        written_total+=size
                        if written_total>MAX_BYTES:raise ValueError('Paket terlalu besar')
                        manifest.append({'file':path.name,'bytes':size,'sha256':digest.hexdigest()})
                media=next((row for row in manifest if row['file']=='video.mp4'),None)
                binding='not_applicable' if media is None else 'not_recorded'
                if media and review_digest:
                    binding='matches_exported_media' if review_digest==media['sha256'] else 'mismatch'
                    if binding=='mismatch':review_status='stale_review'
                note=('Paket produksi lokal.\n\nPeriksa video, subtitle dan fakta sebelum dipublikasikan. '
                      'Paket ini bukan bukti lolos kebijakan platform. Status review: '+review_status+
                      '. Kecocokan review dengan file: '+binding+'. Review visual hanya mencakup sampel yang dijelaskan dalam laporan. '
                      'Lottie tidak menyertakan audio. Preview MP4 dapat memerlukan CDN.\n'
                      'manifest.json mencatat checksum byte hasil ekspor (setelah redaksi), bukan source privat.\n')
                raw=note.encode();archive.writestr('README.txt',raw)
                manifest.append({'file':'README.txt','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
                archive.writestr('manifest.json',json.dumps({'schema_version':1,'review_status':review_status,'review_binding':binding,'manual_review_required':True,'files':manifest},ensure_ascii=False,indent=2))
            GATE.release();acquired=False  # Slow downloads must not block preparation of the next package.
            yield target
    finally:
        if acquired:GATE.release()
