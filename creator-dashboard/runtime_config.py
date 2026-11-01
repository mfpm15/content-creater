"""Platform-aware executable selection; commands remain server controlled."""
import os
from pathlib import Path


def resolve_python(app_dir: Path) -> Path:
    app_dir = Path(app_dir)
    folder = "Scripts" if os.name == "nt" else "bin"
    return app_dir / ".venv" / folder / ("python.exe" if os.name == "nt" else "python")


def resolve_tool_command(tool: dict) -> list[str] | None:
    command = tool.get("command")
    if os.name == "nt" or not command or command[0] != "cmd":
        return command
    directory = Path(tool["_resolvedDirectory"])
    python = str(resolve_python(directory))
    known = {
        "clippercuan": [python, "-m", "clipper", "--port", "8765", "--strict-port", "--no-browser"],
        "podcastfy": [python, "-m", "podcastfy.api.fast_app"],
        "moneyprinterturbo": [python, "-m", "streamlit", "run", "webui/Main.py", "--server.address", "127.0.0.1", "--server.port", "8501"],
    }
    if tool["id"] not in known:
        raise ValueError("Launcher belum mendukung platform ini; jalankan melalui panduan aplikasi")
    if not Path(python).is_file():
        raise ValueError("Virtual environment aplikasi belum tersedia")
    return known[tool["id"]]
