"""Two-pass loudness mastering; measured values only, no shell/filter input from users."""
import json
import math
import re
import subprocess
from pathlib import Path

from security import render_environment


def normalize(ffmpeg: str, source: Path, output: Path) -> dict:
    base=[ffmpeg,'-hide_banner','-nostdin','-protocol_whitelist','file,pipe','-i',str(source)]
    first=subprocess.run([*base,'-vn','-af','loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json','-f','null','-'],
                         capture_output=True,timeout=180,env=render_environment())
    if first.returncode:raise RuntimeError('Analisis loudness audio gagal')
    groups=re.findall(r'\{[^{}]*\}',first.stderr.decode('utf-8','replace'))
    if not groups:raise RuntimeError('Pengukuran loudness tidak tersedia')
    stats=json.loads(groups[-1])
    fields=('input_i','input_tp','input_lra','input_thresh','target_offset')
    try:values=[float(stats[key]) for key in fields]
    except (KeyError,TypeError,ValueError):raise RuntimeError('Pengukuran loudness tidak valid') from None
    finite=all(math.isfinite(value) for value in values)
    if finite:
        i,tp,lra,threshold,offset=values
        filter_text=f'loudnorm=I=-14:TP=-1.5:LRA=9:measured_I={i}:measured_TP={tp}:measured_LRA={lra}:measured_thresh={threshold}:offset={offset}:linear=true:print_format=json'
    else:
        # Silence cannot be normalized to a meaningful integrated loudness.
        filter_text='anull'
    try:
        subprocess.run([*base,'-y','-vn','-af',filter_text,'-ar','48000','-c:a','pcm_s16le',str(output)],
                       check=True,capture_output=True,timeout=180,env=render_environment())
    except BaseException:
        output.unlink(missing_ok=True);raise
    return {'method':'two_pass_loudnorm' if finite else 'silence_or_unmeasurable_preserved',
            'target_lufs':-14,'target_true_peak_dbfs':-1.5,'input_lufs':values[0] if finite else None,
            'verification':'Final encoded audio measured separately in review.json'}
