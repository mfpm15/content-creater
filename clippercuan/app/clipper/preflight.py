"""Read-only candidate checks before expensive media work; no quality prediction."""
from __future__ import annotations

import math


def _number(value) -> float | None:
    if isinstance(value, bool): return None
    try: result = float(value)
    except (TypeError, ValueError, OverflowError): return None
    return result if math.isfinite(result) else None


def bounded_times(start, end, source_duration) -> tuple[float,float]:
    s,e,limit=_number(start),_number(end),_number(source_duration)
    if s is None or e is None:raise ValueError('Waktu klip harus angka terbatas')
    s=max(0.,s)
    if limit is not None and limit>0:e=min(limit,e)
    if e-s<1:raise ValueError('Durasi klip minimal 1 detik')
    return round(s,2),round(e,2)


def analyze(clip: dict, source_duration, transcript: list[dict]) -> dict:
    errors, warnings = [], []
    start, end, duration = _number(clip.get('start')), _number(clip.get('end')), _number(source_duration)
    if start is None or end is None or start < 0 or end <= start:
        errors.append('Waktu klip harus terbatas, mulai ≥ 0 dan selesai setelah mulai')
    elif duration is not None and duration > 0 and end > duration + .05:
        errors.append('Waktu selesai klip melewati durasi sumber')
    if duration is None or duration <= 0:
        warnings.append('Durasi sumber belum diketahui; batas akhir belum dapat dibandingkan')
    if errors:
        return {'can_render': False, 'errors': errors, 'warnings': warnings, 'word_count': 0,
                'method': 'candidate_preflight_not_quality_prediction'}
    override = clip.get('words')
    words = transcript if override is None else override
    if not isinstance(words,list):
        return {'can_render':False,'errors':['Track caption harus berupa daftar kata'], 'warnings':warnings,
                'word_count':0,'method':'candidate_preflight_not_quality_prediction'}
    offset = 0 if override is None else start
    selected, malformed = [], 0
    for word in words:
        if not isinstance(word,dict):malformed+=1;continue
        s, e = _number(word.get('s')), _number(word.get('e'))
        if s is None or e is None or e < s:
            malformed += 1; continue
        s, e = s + offset, e + offset
        if s < end and e > start: selected.append((s, e, str(word.get('w', ''))))
    if malformed:warnings.append(f'{malformed} timestamp kata tidak valid; periksa transkrip')
    if not selected:warnings.append('Tidak ada kata bertimestamp pada rentang ini; periksa narasi/caption')
    if any(s < start - .03 < e or s < end + .03 < e for s, e, _ in selected):
        warnings.append('Batas klip berpotensi memotong kata; periksa titik masuk/keluar')
    rate = len(selected) / (end - start)
    if rate > 4:warnings.append('Kepadatan narasi di atas 4 kata/detik; tinjau keterbacaan caption')
    return {'can_render': True, 'errors': errors, 'warnings': warnings,
            'duration': round(end-start, 3), 'word_count': len(selected), 'words_per_second': round(rate, 2),
            'caption_track': 'clip_override' if override is not None else 'project_transcript',
            'method': 'candidate_preflight_not_quality_prediction'}
