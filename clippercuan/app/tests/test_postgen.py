from unittest.mock import patch

from clipper import llm, postgen


def test_local_package_has_all_platforms_per_profile():
    for profile in postgen.STYLE:
        r = postgen.local("Ini cara rotasi yang benar. Jangan lupa farming.", "Rotasi yang benar", profile, "id")
        assert set(r["platforms"]) == set(postgen.PLATFORMS)
        assert r["caption"] and r["hashtags"] and r["engine"] == "lokal"
        assert r["platforms"]["youtube_shorts"]["title"].endswith("#shorts")
        for p, spec in postgen.PLATFORMS.items():
            d = r["platforms"][p]
            assert len(d["hashtags"]) <= spec["tags"]
            assert d["ready"].startswith(d["caption"][:20])


def test_english_post_is_fully_english_without_indonesian_template_fragments():
    r = postgen.local("More than 72 billion dollars of the loss is an accounting illusion.",
                      "Anthropic's Accounting Illusion", "podcast", "en")
    ready = r["platforms"]["tiktok"]["ready"]
    assert "A thought-provoking take:" in ready
    assert "What do you think?" in ready
    assert "Pendapat ini" not in ready and "Setuju" not in ready and "#podcastindonesia" not in ready


def test_indonesian_post_is_fully_indonesian_without_english_cta():
    r = postgen.local("Kerugian itu sebagian besar hanya ilusi akuntansi.",
                      "Ilusi Akuntansi Anthropic", "podcast", "id")
    ready = r["platforms"]["tiktok"]["ready"]
    assert "Pendapat ini bikin mikir:" in ready
    assert "Setuju atau nggak?" in ready
    assert "What do you think?" not in ready


def test_profiles_get_distinct_niche_tags():
    ml = postgen.local("Lord", "Lord", "mobile_legends", "id")["hashtags"]
    pod = postgen.local("cerita", "Cerita", "podcast", "id")["hashtags"]
    assert "#mlbb" in ml and "#podcast" in pod


def test_chain_starts_with_gpt_thinker_and_has_no_gemini():
    c = {**llm.DEFAULT_LLM}
    for task in ("moments", "titles", "posts"):
        chain = llm.chain_for(task, c)
        assert chain[0] == llm.GPT_THINKER
        assert not any("gemini" in m for m in chain)
        assert len(chain) == len(set(chain))


def test_chat_chain_falls_back_to_next_model():
    calls = []

    def fake(model, *a, **k):
        calls.append(model)
        if len(calls) == 1:
            raise llm.LLMError("down")
        return '{"ok": 1}'

    with patch.object(llm, "chat", fake):
        out, model = llm.chat_chain("posts", "s", "u", {**llm.DEFAULT_LLM})
    assert out == {"ok": 1} and model == calls[1] and len(calls) == 2


def test_generate_falls_back_to_local_when_all_models_fail():
    with patch.object(llm, "active", lambda *_: True), \
         patch.object(llm, "chat", lambda *a, **k: (_ for _ in ()).throw(llm.LLMError("x"))):
        r = postgen.generate("teks", "Judul", "review", "id")
    assert r["engine"] == "lokal" and "warning" in r
