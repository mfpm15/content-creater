"""Explicit labels approved with the scene; never infer invented process steps."""

def validate(value):
    if not isinstance(value, dict) or set(value) != {'kind', 'labels'}:
        raise ValueError('diagram harus berisi kind dan labels')
    kind, labels = value['kind'], value['labels']
    if kind not in ('process', 'comparison') or not isinstance(labels, list):
        raise ValueError('diagram kind harus process/comparison')
    if not (2 <= len(labels) <= 5) or (kind == 'comparison' and len(labels) != 2):
        raise ValueError('Diagram proses memerlukan 2–5 label; perbandingan tepat 2')
    if any(not isinstance(x, str) or not x.strip() or len(x) > 48 or any(ord(c)<32 for c in x) for x in labels):
        raise ValueError('Label diagram wajib teks 1–48 karakter tanpa kontrol')
    return {'kind': kind, 'labels': [x.strip() for x in labels]}
