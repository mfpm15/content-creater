"""Shared isolated research worker. Credentials stay in the inherited environment."""
import json
import os
import subprocess
from pathlib import Path
from runtime_config import resolve_python
from security import redact


def research(topic: str, context: str, model: str = "gemini-2.5-flash") -> dict:
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("Riset memerlukan GOOGLE_API_KEY atau GEMINI_API_KEY")
    root = Path(__file__).resolve().parent
    python = resolve_python(root / "apps" / "podcastfy")
    if not python.is_file():
        raise RuntimeError("Environment Google Search belum tersedia")
    process = subprocess.run([str(python), str(root / "google_search_research.py")],
        input=json.dumps({"topic": topic, "context": context, "model": model}),
        text=True, capture_output=True, timeout=300, check=False)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        raise RuntimeError("Respons worker riset tidak valid") from None
    if process.returncode or result.get("error"):
        raise RuntimeError(redact(str(result.get("error") or "Worker riset gagal")))
    if not result.get("sources"):
        raise RuntimeError("Riset tidak menghasilkan sumber")
    return result
