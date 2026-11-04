"""Video Studio uses the same versioned working profiles as Clipper (stdlib only)."""
import json
import math
from pathlib import Path

SPEC=Path(__file__).resolve().parents[1]/'clippercuan'/'app'/'clipper'/'platform_specs.json'


def evaluate(video: dict, duration: float, audio: dict) -> dict:
    profiles=json.loads(SPEC.read_text('utf-8'))
    w,h=int(video.get('width',0)),int(video.get('height',0))
    try:
        numerator,denominator=str(video.get('avg_frame_rate','0/1')).split('/')
        fps=float(numerator)/float(denominator)
        if not math.isfinite(fps):fps=0
    except (ValueError,ZeroDivisionError):fps=0
    reports={}
    for name,spec in profiles['platforms'].items():
        issues=[]
        def issue(code,message):issues.append({'code':code,'message':message})
        ratios=[int(a)/int(b) for a,b in (ratio.split(':') for ratio in spec['aspects'])]
        if not w or not h or not any(abs(w/h-ratio)<=ratio*.02 for ratio in ratios):issue('aspect','Rasio video perlu varian yang sesuai platform')
        if min(w,h)<spec['min_height']:issue('resolution','Resolusi di bawah profil kerja platform')
        if duration>spec['max_sec']:issue('duration','Durasi melebihi profil kerja platform')
        if fps<=0 or fps>60.01:issue('fps','FPS tidak terbaca atau melebihi 60')
        if video.get('codec_name') and video['codec_name']!='h264':issue('codec','Codec video bukan profil H.264 untuk ekspor umum')
        if video.get('pix_fmt') and video['pix_fmt']!='yuv420p':issue('pixel_format','Format piksel bukan YUV 4:2:0 limited-range; periksa kompatibilitas pemutar')
        if audio.get('status') not in ('measured','intentionally_silent'):issue('loudness_unmeasured','Audio belum berhasil diukur')
        elif audio.get('status')=='measured':
            if abs(audio['integrated_lufs']-spec['lufs'])>2:issue('loudness','Loudness di luar target -14 ±2 LUFS')
            if audio['true_peak_dbfs']>-.5:issue('peak','True peak terlalu dekat clipping')
        reports[name]={'label':spec['label'],'status':'needs_attention' if issues else 'passed_working_profile',
                       'issues':issues,'spec_source':profiles['source'],'spec_verified_official':profiles['verified_official']}
    return reports
