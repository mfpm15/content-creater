from pathlib import Path

import numpy as np

from clipper import highlights, llm


ROOT = Path(__file__).resolve().parents[1]


def test_new_project_uses_balanced_full_width_workspace():
    css = (ROOT / "clipper" / "web" / "dark.css").read_text("utf-8")
    assert ".production-workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(320px,360px)" in css
    assert ".production-preview{position:sticky;top:92px" in css
    html = (ROOT / "clipper" / "web" / "index.html").read_text("utf-8")
    duration_at = html.index('class="card duration-transcription-card')
    format_at = html.index('class="card format-video-card')
    preview_at = html.index('class="production-preview"')
    assert duration_at < format_at < preview_at
    assert html.count('id="durationPreset"') == 1
    assert html.count('class="card duration-transcription-card') == 1
    preview_html = html[preview_at:]
    assert "duration-transcription-card" not in preview_html
    assert ".primary-settings{grid-template-columns:1fr;width:100%;gap:16px}" in css
    assert ".duration-transcription-card{display:grid;grid-template-columns:repeat(12,minmax(0,1fr))" in css
    assert ".duration-transcription-card>.preset-cards{grid-template-columns:repeat(4,minmax(0,1fr))" in css
    assert ".duration-transcription-card>.row3{grid-column:1/-1;grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".duration-transcription-card>.ai-choice{grid-column:8/-1" in css
    assert 'grid-template-areas:"head" "phone" "meta" "summary" "quality"' in css
    assert "grid-area:duration" not in css
    assert ".wizard-content>.source-card,.wizard-content>.recipe-card" in css
    assert "main{min-width:0;padding:0" in css


def test_moment_chain_honors_chosen_model_first():
    chain = llm.chain_for("moments", {
        **llm.DEFAULT_LLM,
        "model_moments": "cc/claude-sonnet-5-5",
        "fallback_models": llm.DEFAULT_FALLBACKS,
    })
    assert chain[0] == "cc/claude-sonnet-5-5"
    assert not any("gemini" in m for m in chain)


def test_local_moment_score_is_absolute_not_artificially_inflated():
    words = [{"w": "biasa", "s": i * 0.5, "e": i * 0.5 + 0.35, "p": 0.95} for i in range(80)]
    segments = []
    for start in range(0, 80, 10):
        idx = list(range(start, start + 10))
        segments.append({"text": "pembahasan biasa tanpa hook atau payoff", "s": words[idx[0]]["s"], "e": words[idx[-1]]["e"], "words": idx})
    transcript = {"words": words, "segments": segments}
    moments = highlights.find_moments(transcript, np.zeros(200), 45, count=3, min_sec=10, max_sec=25)
    assert moments
    assert max(item["score"] for item in moments) < 90
    assert all(item["score"] == item["readiness"] for item in moments)
