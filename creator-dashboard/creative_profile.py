"""Brand snapshots and supplied word timing; never accept CSS or remote assets."""
import copy
import html
import json
import os
import re
import stat
import threading
import uuid
from pathlib import Path

from article_storage import atomic_bytes, json_bytes
from security import redact_tree

FONTS = {'Arial', 'Verdana', 'Georgia', 'Tahoma'}
LOCK = threading.RLock()
DEFAULT = {'name': 'Default', 'accent': '#22d3ee', 'background': '#030712',
           'text': '#ffffff', 'font': 'Arial', 'wordmark': ''}
MAX_STORE_BYTES = 100_000


def brand(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('Brand harus objek')
    result = {key: raw.get(key, value) for key, value in DEFAULT.items()}
    if any(not isinstance(value, str) for value in result.values()):
        raise ValueError('Field brand harus teks')
    result['name'] = result['name'].strip()
    if not 1 <= len(result['name']) <= 60 or len(result['wordmark']) > 24:
        raise ValueError('Nama brand maksimal 60; wordmark maksimal 24 karakter')
    if any(ord(c) < 32 for key in ('name', 'wordmark') for c in result[key]):
        raise ValueError('Nama dan wordmark harus satu baris')
    if result['font'] not in FONTS:
        raise ValueError('Font harus Arial, Verdana, Georgia atau Tahoma')
    for key in ('accent', 'background', 'text'):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', result[key]):
            raise ValueError('Warna brand harus #RRGGBB')
        result[key] = result[key].lower()
    return result


def _check_path(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Brand store tidak boleh melalui symlink/junction')


def catalog(path: Path) -> dict:
    with LOCK:
        _check_path(path)
        if not path.exists():
            return {'revision': 0, 'kits': []}
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_STORE_BYTES:
                raise ValueError('Brand store tidak valid atau terlalu besar')
            data = json.loads(source.read(MAX_STORE_BYTES + 1))
        if (not isinstance(data, dict) or type(data.get('revision')) is not int or data['revision'] < 0
                or not isinstance(data.get('kits'), list) or len(data['kits']) > 50):
            raise ValueError('Brand store tidak valid')
        kits = []
        for row in data['kits']:
            if not isinstance(row, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(row.get('id', ''))):
                raise ValueError('Identitas brand tidak valid')
            kits.append({**brand(row), 'id': row['id']})
        return {'revision': data['revision'], 'kits': kits}


def save(path: Path, payload: dict) -> dict:
    with LOCK:
        data = catalog(path)
        if type(payload.get('revision')) is not int or payload['revision'] != data['revision']:
            raise ValueError('Daftar brand berubah; muat ulang')
        kit = brand(payload.get('brand'))
        found = next((row for row in data['kits'] if row['name'].casefold() == kit['name'].casefold()), None)
        if not found and len(data['kits']) >= 50:
            raise ValueError('Maksimal 50 brand; simpan dengan nama yang sama untuk memperbarui')
        kit = {**kit, 'id': found['id'] if found else uuid.uuid4().hex}
        data['kits'] = [row for row in data['kits'] if row['id'] != kit['id']] + [kit]
        data['revision'] += 1
        atomic_bytes(path, json_bytes(redact_tree(data)))
        return catalog(path)


def timing(scene: dict, raw: dict) -> None:
    cues = raw.get('wordCues')
    if cues is None:
        if raw.get('visualCueWord') is not None:
            raise ValueError('Timestamp kata wajib sebelum memilih cue visual')
        return
    if not isinstance(cues, list) or len(cues) > 400:
        raise ValueError('Maksimal 400 timestamp kata per adegan')
    output, previous = [], scene['start']
    for item in cues:
        if not isinstance(item, dict):
            raise ValueError('Timestamp kata harus objek')
        word = item.get('word', item.get('w'))
        start, end = item.get('start', item.get('s')), item.get('end', item.get('e'))
        if (not isinstance(word, str) or not word.strip() or len(word) > 100
                or type(start) not in (int, float) or type(end) not in (int, float)):
            raise ValueError('Kata dan timestamp numerik wajib')
        if not previous <= start < end <= scene['end']:
            raise ValueError('Timestamp kata di luar adegan atau tumpang tindih')
        previous = end
        output.append({'word': word, 'start': start, 'end': end})
    def tokens(text):
        return re.findall(r"\d+(?:[.,]\d+)*%?|\w+(?:['’]\w+)*", text.casefold())
    if output and tokens(' '.join(cue['word'] for cue in output)) != tokens(scene['narration']):
        raise ValueError('Timestamp harus mempertahankan seluruh kata, angka dan negasi narasi')
    scene['wordCues'] = output
    index = raw.get('visualCueWord')
    if index is not None:
        if type(index) is not int or not 0 <= index < len(output):
            raise ValueError('Pilih indeks kata visual yang valid (mulai 0)')
        scene['visualCueWord'] = index


def reveal(scene: dict, offset: float = 0) -> float:
    if scene.get('visualCueWord') is not None:
        return scene['wordCues'][scene['visualCueWord']]['start']
    return scene['start'] + offset


def styled(document: str, raw: dict | None) -> str:
    if not raw:
        return document
    kit = brand(raw)
    def css(match):
        text = match[1].replace('#22d3ee', kit['accent']).replace('#38bdf8', kit['accent'])
        rgb = ','.join(str(int(kit['accent'][i:i+2], 16)) for i in (1, 3, 5))
        text = re.sub(r'rgba\(\s*(?:34\s*,\s*211\s*,\s*238|56\s*,\s*189\s*,\s*248)\s*,',
                      lambda _: 'rgba(' + rgb + ',', text)
        text = text.replace('#030712', kit['background'])
        return '<style>' + text + f"""
        #stage{{background:{kit['background']}}}
        .hero-title,.subtitle-capsule,.chapter-badge{{font-family:{kit['font']};color:{kit['text']}}}
        .hero-title{{background:none;-webkit-text-fill-color:{kit['text']}}}
        .brand-wordmark{{position:absolute;z-index:9;top:2%;left:20%;width:60%;text-align:center;
          color:{kit['text']};font:24px {kit['font']};pointer-events:none;overflow-wrap:anywhere}}
        """ + '</style>'
    document = re.sub(r'<style>([\s\S]*?)</style>', css, document, count=1)
    if kit['wordmark']:
        document = re.sub(r'(<div id="stage"[^>]*>)', lambda match: match[1]
                          + '<div class="brand-wordmark">' + html.escape(kit['wordmark']) + '</div>', document, count=1)
    return document


def snapshot(raw: dict) -> dict:
    return copy.deepcopy(brand(raw))
