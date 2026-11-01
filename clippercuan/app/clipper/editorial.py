"""Local, evidence-labelled editorial suggestions; never a performance prediction."""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher


def hook_archetypes(text: str) -> dict:
    lowered = text.casefold()
    rules = {
        'question': r'\?|\b(?:kenapa|mengapa|bagaimana|why|how)\b',
        'number': r'\b\d+(?:[.,]\d+)?\b',
        'personal_experience': r'\b(?:saya|aku|pengalaman|pernah|i tried|my experience)\b',
        'contrast': r'\b(?:tapi|namun|ternyata|sebaliknya|but|instead)\b',
        'demonstration': r'\b(?:lihat|contoh|hasil|perhatikan|watch|example|result)\b',
    }
    matches = {name: match.group(0) for name, pattern in rules.items() if (match := re.search(pattern, lowered))}
    return {'archetypes': list(matches), 'evidence': matches, 'method': 'editorial_heuristic_not_prediction'}


def words_revision(words: list[dict]) -> str:
    return hashlib.sha256(json.dumps(words, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def retakes(words: list[dict], window: float = 25) -> dict:
    """Suggest repeated sentences. Exact repeats can be removed only after approval.

    Numbers/negations remain in the token stream; fuzzy matches are review-only.
    """
    groups, current = [], []
    for index, word in enumerate(words):
        if current and float(word['s']) - float(words[current[-1]]['e']) > .6:
            groups.append(current); current = []
        current.append(index)
        if str(word.get('w', '')).rstrip().endswith(('.', '!', '?')):
            groups.append(current); current = []
    if current: groups.append(current)
    suggestions = []
    for i, earlier in enumerate(groups):
        tokens = re.findall(r'\w+', ' '.join(str(words[k].get('w', '')) for k in earlier).casefold())
        if len(tokens) < 4: continue
        for later in groups[i + 1:]:
            if float(words[later[0]]['s']) - float(words[earlier[-1]]['e']) > window: break
            other = re.findall(r'\w+', ' '.join(str(words[k].get('w', '')) for k in later).casefold())
            similarity = SequenceMatcher(None, tokens, other).ratio()
            if similarity >= .85:
                suggestions.append({'drop_indices': earlier, 'keep_indices': later, 'similarity': round(similarity, 3),
                                    'drop_text': ' '.join(str(words[k].get('w','')) for k in earlier),
                                    'keep_text': ' '.join(str(words[k].get('w','')) for k in later),
                                    'drop_range': [words[earlier[0]]['s'],words[earlier[-1]]['e']],
                                    'keep_range': [words[later[0]]['s'],words[later[-1]]['e']],
                                    'apply_allowed': tokens == other,
                                    'reason': 'Pengulangan persis; take terakhir disarankan, bukan bukti kualitas audio lebih baik' if tokens == other else 'Mirip tetapi makna mungkin berubah; tinjau manual'})
                break
    return {'revision': words_revision(words), 'suggestions': suggestions, 'method': 'local_retakes_review'}
