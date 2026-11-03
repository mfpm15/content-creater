"""Shared isolated research worker. Credentials stay in the inherited environment."""
import json
import os
import subprocess
from pathlib import Path
from runtime_config import resolve_python
from security import redact


def provider():
    selected=os.getenv('RESEARCH_PROVIDER','auto').strip().lower()
    if selected not in {'auto','google','9router'}:raise ValueError('RESEARCH_PROVIDER harus auto, google, atau 9router')
    return ('google' if os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') else '9router') if selected=='auto' else selected


def research(topic: str, context: str, model: str = "gemini-2.5-flash", scope: str = '') -> dict:
    if provider()=='9router':
        from router_research import research as search
        return search(topic,context,scope)
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("Riset memerlukan GOOGLE_API_KEY atau GEMINI_API_KEY")
    root = Path(__file__).resolve().parent
    python = resolve_python(root)
    if not python.is_file():
        raise RuntimeError("Environment riset dashboard belum tersedia; jalankan setup-core.bat")
    process = subprocess.run([str(python), "-X", "utf8", str(root / "google_search_research.py")],
        input=json.dumps({"topic": topic, "context": context, "model": model}),
        text=True, encoding="utf-8", capture_output=True, timeout=300, check=False)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        raise RuntimeError("Respons worker riset tidak valid") from None
    if process.returncode or result.get("error"):
        raise RuntimeError(redact(str(result.get("error") or "Worker riset gagal")))
    if not result.get("sources"):
        raise RuntimeError("Riset tidak menghasilkan sumber")
    return result
