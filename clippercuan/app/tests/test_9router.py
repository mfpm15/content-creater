"""Contract tests for shared 9Router config and transport. No network calls."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("CLIPPER_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from clipper import llm  # noqa: E402
from clipper.server import app  # noqa: E402


class Response(BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def test_url_normalization_and_environment_precedence():
    assert llm.normalize_base_url("http://localhost:20128") == "http://localhost:20128/v1"
    assert llm.normalize_base_url("http://localhost:20128/v1/") == "http://localhost:20128/v1"
    with patch.dict(os.environ, {"LLM_BASE_URL": "http://localhost:20128", "LLM_API_KEY": "secret", "LLM_MODEL": "model-id"}, clear=False):
        c = llm.environment_llm()
    assert c == {"base_url": "http://localhost:20128/v1", "api_key": "secret", "model_moments": "model-id", "model_titles": "model-id"}


def test_chat_request_contract_and_authorization():
    captured = {}

    def fake_open(request, timeout):
        captured.update(url=request.full_url, headers=dict(request.header_items()), body=json.loads(request.data), timeout=timeout)
        return Response(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

    c = {"base_url": "http://localhost:20128/v1", "api_key": "top-secret", "temperature": 0.2, "timeout": 7}
    with patch("urllib.request.urlopen", fake_open):
        assert llm.chat("ag/gemini-3.8-flash-medium", "system", "user", c) == "ok"
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer top-secret"
    assert captured["body"]["model"] == "ag/gemini-3.8-flash-medium"
    assert captured["body"]["messages"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    assert captured["body"]["stream"] is False
    assert captured["timeout"] == 7


def test_invalid_response_and_health_redaction():
    with patch("urllib.request.urlopen", lambda *_args, **_kwargs: Response(b'{"unexpected":true}')):
        try:
            llm.chat("model", "system", "user", {"base_url": "http://localhost:20128/v1", "api_key": "", "timeout": 1})
            assert False, "invalid response must fail"
        except llm.LLMError as exc:
            assert "Format respons" in str(exc)
    with patch.dict(os.environ, {"LLM_API_KEY": "must-not-leak"}, clear=False):
        payload = TestClient(app).get("/api/health").json()
    assert payload["ok"] is True
    assert payload["llm"]["mode"] in {"9router", "local_fallback"}
    assert isinstance(payload["llm"]["credential_configured"], bool)
    assert "must-not-leak" not in json.dumps(payload)


def test_default_placeholder_is_local_fallback_and_explicit_config_can_enable():
    original = llm.SETTINGS_FILE
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
        llm.SETTINGS_FILE = Path(directory) / "settings.json"
        try:
            assert llm.explicitly_configured() is False
            assert llm.active() is False
            llm.save_settings({"llm": {"enabled": True, "base_url": "http://localhost:20128/v1", "model_moments": "model-id"}})
            assert llm.explicitly_configured() is True
            assert llm.active() is True
        finally:
            llm.SETTINGS_FILE = original


def test_ui_assets_workflow_contract_and_no_credentials():
    client = TestClient(app)
    html = client.get("/")
    css = client.get("/style.css")
    js = client.get("/app.js")
    assert html.status_code == css.status_code == js.status_code == 200
    assert "text/html" in html.headers["content-type"]
    assert "text/css" in css.headers["content-type"]
    assert "javascript" in js.headers["content-type"]
    for marker in (b'id="srcTabs"', b'id="url"', b'id="file"', b'id="start"', b'id="startTop"', b'id="localFallback"', b'id="recipes"',
                   b'id="experimentalRecipes"', b'id="storage_lite"', b'id="uiMode"', b'id="durationPreset"', b'id="capStyle"',
                   b'src="studio.js?v=', b'href="premium.css?v=', b'production-flow', b'decoration_mode', b'skip-link', b'bottom-nav', b'Buat Klip', b'Analisis Video', b'Production',
                   b'General', b'Interview', b'Review', b'Gaming', b'Educational'):
        assert marker in html.content
    studio = client.get("/studio.js")
    assert studio.status_code == 200 and b"KANDIDAT" in studio.content and b"CONTENT READINESS" in studio.content
    assert all(marker in studio.content for marker in (b"Caption", b"Frame", b"Dekorasi", b"Audio", b"Detail teknis", b"decoration"))
    assert b"prefers-reduced-motion" in css.content and b"color-scheme:light" in css.content
    assert b":focus-visible" in css.content and b"min-height:44px" in css.content
    assert html.content.count(b'data-nav=') == 5 and html.content.count(b'data-mobile-nav=') == 4
    assert all(route in js.content for route in (b"'new'", b"'history'", b"'results'", b"'advanced'", b"'settings'", b"'p'"))
    assert b"location.replace('#/new')" in js.content and b"aria-current" in js.content
    assert b"mobile-menu" not in html.content and b"nav-scrim" not in html.content
    assert b"/api/projects" in js.content and b"source, settings" in js.content
    assert b"api_key" not in html.content.lower()
    assert b"duration_preset" in js.content
