from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
BASE_URL = "http://127.0.0.1:3210"


def fetch(path: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(BASE_URL + path, headers={"User-Agent": "CreatorDashboardTest/1.0"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read(), response.headers.get("Content-Type", "")


def main() -> int:
    environment = os.environ.copy()
    environment["CREATOR_DASHBOARD_HOST"] = "127.0.0.1"
    environment["CREATOR_DASHBOARD_PORT"] = "3210"
    environment["CREATOR_DASHBOARD_NO_BROWSER"] = "1"
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=str(WORKSPACE),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        for _ in range(40):
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"Dashboard exited early with {process.returncode}:\n{output}")
            try:
                status, _, _ = fetch("/api/tools")
                if status == 200:
                    break
            except Exception:
                time.sleep(0.15)
        else:
            raise RuntimeError("Dashboard did not become ready within 6 seconds")

        status, body, content_type = fetch("/api/tools")
        assert status == 200
        assert "application/json" in content_type
        payload = json.loads(body.decode("utf-8"))
        tools = payload["tools"]
        assert len(tools) == 5
        assert {tool["id"] for tool in tools} == {
            "moneyprinterturbo",
            "opencreator",
            "short-video-factory",
            "podcastfy",
            "ai-youtube-shorts",
        }
        assert all(tool["repositoryExists"] for tool in tools)
        assert all("command" not in tool for tool in tools)
        assert all("environment" not in tool for tool in tools)

        status, html, content_type = fetch("/")
        assert status == 200
        assert "text/html" in content_type
        assert b"Creator Control Center" in html

        status, javascript, content_type = fetch("/app.js")
        assert status == 200
        assert "javascript" in content_type
        assert b"function escapeHtml" in javascript

        status, css, content_type = fetch("/styles.css")
        assert status == 200
        assert "text/css" in content_type
        assert b".tool-grid" in css

        print("Dashboard smoke test passed")
        print(f"Tools discovered: {len(tools)}")
        print("Static assets: index.html, app.js, styles.css OK")
        print("API redaction and repository validation OK")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
