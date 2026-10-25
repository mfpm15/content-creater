from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import article_drafter

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent.resolve()
STATIC_DIR = ROOT / "static"
CONFIG_FILE = ROOT / "tools.json"
HOST = os.getenv("CREATOR_DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.getenv("CREATOR_DASHBOARD_PORT", "3210"))
MAX_LOG_LINES = 500


def load_config() -> list[dict[str, Any]]:
    with CONFIG_FILE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    tools = payload.get("tools")
    if not isinstance(tools, list):
        raise ValueError("tools.json must contain a tools array")
    seen: set[str] = set()
    for tool in tools:
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or not tool_id or tool_id in seen:
            raise ValueError("Every tool requires a unique non-empty id")
        seen.add(tool_id)
        raw_directory = tool.get("workingDirectory")
        if not isinstance(raw_directory, str):
            raise ValueError(f"Tool {tool_id} requires workingDirectory")
        resolved_directory = (ROOT / raw_directory).resolve()
        if resolved_directory != WORKSPACE and WORKSPACE not in resolved_directory.parents:
            raise ValueError(f"Tool path escapes workspace: {tool_id}")
        tool["_resolvedDirectory"] = str(resolved_directory)
    return tools


TOOLS = load_config()
TOOLS_BY_ID = {tool["id"]: tool for tool in TOOLS}


class ManagedProcess:
    def __init__(self, tool: dict[str, Any]):
        self.tool = tool
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.logs: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.lock = threading.RLock()
        self.reader_threads: list[threading.Thread] = []

    def is_running(self) -> bool:
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def start(self) -> tuple[bool, str]:
        with self.lock:
            if self.is_running():
                return True, "Tool is already running"
            command = self.tool.get("command")
            if not isinstance(command, list) or not command:
                return False, "This tool is CLI-only and has no persistent service"
            working_directory = Path(self.tool["_resolvedDirectory"])
            if not working_directory.is_dir():
                return False, f"Repository directory is missing: {working_directory.name}"
            environment = os.environ.copy()
            configured_environment = self.tool.get("environment") or {}
            environment.update({str(key): str(value) for key, value in configured_environment.items()})
            environment["PATH"] = str(ROOT / "bin") + os.pathsep + environment.get("PATH", "")
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self.logs.clear()
            self.logs.append(f"$ {' '.join(command)}")
            try:
                self.process = subprocess.Popen(
                    command,
                    cwd=str(working_directory),
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creation_flags,
                )
            except (OSError, ValueError) as exc:
                self.process = None
                self.logs.append(f"START ERROR: {exc}")
                return False, str(exc)
            self.started_at = time.time()
            self.reader_threads = []
            for label, pipe in (("OUT", self.process.stdout), ("ERR", self.process.stderr)):
                if pipe is None:
                    continue
                thread = threading.Thread(
                    target=self._read_pipe,
                    args=(label, pipe),
                    daemon=True,
                    name=f"{self.tool['id']}-{label.lower()}",
                )
                thread.start()
                self.reader_threads.append(thread)
            threading.Thread(target=self._watch_exit, daemon=True).start()
            return True, "Start command submitted"

    def _read_pipe(self, label: str, pipe) -> None:
        try:
            for line in iter(pipe.readline, ""):
                value = line.rstrip()
                if value:
                    with self.lock:
                        self.logs.append(f"[{label}] {value}")
        finally:
            pipe.close()

    def _watch_exit(self) -> None:
        process = self.process
        if process is None:
            return
        exit_code = process.wait()
        with self.lock:
            self.logs.append(f"[SYSTEM] Process exited with code {exit_code}")

    def stop(self) -> tuple[bool, str]:
        with self.lock:
            process = self.process
            if process is None or process.poll() is not None:
                return True, "Tool is not running"
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/pid", str(process.pid), "/t", "/f"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                self.logs.append("[SYSTEM] Stop requested")
                return True, "Tool stopped"
            except OSError as exc:
                self.logs.append(f"[SYSTEM] Stop failed: {exc}")
                return False, str(exc)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            process = self.process
            running = process is not None and process.poll() is None
            return {
                "managedRunning": running,
                "pid": process.pid if running else None,
                "startedAt": self.started_at if running else None,
                "exitCode": None if process is None or running else process.returncode,
            }

    def log_snapshot(self) -> list[str]:
        with self.lock:
            return list(self.logs)


PROCESSES = {tool["id"]: ManagedProcess(tool) for tool in TOOLS}


def sync_tools() -> list[dict[str, Any]]:
    global TOOLS, TOOLS_BY_ID
    try:
        new_tools = load_config()
        for tool in new_tools:
            tid = tool["id"]
            if tid not in PROCESSES:
                PROCESSES[tid] = ManagedProcess(tool)
            else:
                PROCESSES[tid].tool = tool
        TOOLS = new_tools
        TOOLS_BY_ID = {tool["id"]: tool for tool in TOOLS}
    except Exception as exc:
        print(f"[WARN] Failed to reload tools.json: {exc}")
    return TOOLS


def port_is_open(port: int | None) -> bool:
    if not isinstance(port, int):
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.35):
            return True
    except OSError:
        return False


def health_is_ready(url: str | None) -> bool:
    if not isinstance(url, str) or not url:
        return False
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "CreatorDashboard/1.0"})
        with urllib.request.urlopen(request, timeout=0.7) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def public_tool(tool: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in tool.items() if not key.startswith("_") and key not in {"command", "environment"}}
    manager = PROCESSES[tool["id"]]
    snapshot = manager.snapshot()
    port_open = port_is_open(tool.get("port"))
    ready = health_is_ready(tool.get("healthUrl")) if port_open else False
    if tool.get("type") == "cli":
        status = "cli"
    elif tool.get("type") == "desktop" and snapshot["managedRunning"]:
        status = "ready"
        ready = True
    elif ready:
        status = "ready"
    elif snapshot["managedRunning"] or port_open:
        status = "starting"
    else:
        status = "stopped"
    result.update(snapshot)
    result["status"] = status
    result["portOpen"] = port_open
    result["ready"] = ready
    result["repositoryExists"] = Path(tool["_resolvedDirectory"]).is_dir()
    return result


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "CreatorDashboard/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _route_parts(self) -> list[str]:
        return [part for part in urlparse(self.path).path.split("/") if part]

    def _read_body(self, limit: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > limit:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Body terlalu besar atau tidak valid"})
            return None
        return self.rfile.read(length)

    def _article_error(self, exc: Exception) -> None:
        if isinstance(exc, FileNotFoundError):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Tidak ditemukan"})
        elif isinstance(exc, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        elif isinstance(exc, article_drafter.LLMError):
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        else:
            raise exc

    def _articles_get(self, parts: list[str]) -> None:
        try:
            if parts == ["api", "articles"]:
                self._json(HTTPStatus.OK, {"articles": article_drafter.list_articles()})
            elif parts == ["api", "articles", "options"]:
                self._json(HTTPStatus.OK, article_drafter.options())
            elif len(parts) == 4 and parts[2] == "jobs":
                self._json(HTTPStatus.OK, article_drafter.job_status(unquote(parts[3])))
            elif len(parts) == 3:
                self._json(HTTPStatus.OK, article_drafter.get_article(unquote(parts[2])))
            elif len(parts) == 5 and parts[3] == "files":
                name = unquote(parts[4])
                data, content_type = article_drafter.read_file(unquote(parts[2]), name)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        except Exception as exc:  # noqa: BLE001 - dipetakan ke status HTTP di _article_error
            self._article_error(exc)

    def _articles_post(self, parts: list[str]) -> None:
        try:
            if parts == ["api", "articles"]:
                raw = self._read_body(200_000)
                if raw is None:
                    return
                self._json(HTTPStatus.ACCEPTED, article_drafter.start_job(json.loads(raw or b"{}")))
            elif len(parts) == 4 and parts[3] == "resume":
                self._json(HTTPStatus.ACCEPTED, article_drafter.resume_job(unquote(parts[2])))
            elif len(parts) == 4 and parts[3] == "rebuild":
                self._json(HTTPStatus.OK, article_drafter.build_outputs(unquote(parts[2])))
            elif len(parts) == 5 and parts[3] == "images":
                raw = self._read_body(article_drafter.MAX_IMAGE_BYTES + 1024)
                if raw is None:
                    return
                self._json(HTTPStatus.OK, article_drafter.save_image(unquote(parts[2]), unquote(parts[4]), raw))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Body bukan JSON valid"})
        except Exception as exc:  # noqa: BLE001
            self._article_error(exc)

    def do_GET(self) -> None:
        parts = self._route_parts()
        if parts[:2] == ["api", "articles"]:
            self._articles_get(parts)
            return
        if parts == ["api", "tools"]:
            sync_tools()
            self._json(HTTPStatus.OK, {"tools": [public_tool(tool) for tool in TOOLS]})
            return
        if len(parts) == 4 and parts[:2] == ["api", "tools"] and parts[3] == "logs":
            tool_id = parts[2]
            manager = PROCESSES.get(tool_id)
            if manager is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown tool"})
                return
            self._json(HTTPStatus.OK, {"toolId": tool_id, "logs": manager.log_snapshot()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        parts = self._route_parts()
        if parts[:2] == ["api", "articles"]:
            self._articles_post(parts)
            return
        if len(parts) != 4 or parts[:2] != ["api", "tools"]:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
            return
        sync_tools()
        tool_id, action = parts[2], parts[3]
        manager = PROCESSES.get(tool_id)
        if manager is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown tool"})
            return
        if action == "start":
            ok, message = manager.start()
        elif action == "stop":
            ok, message = manager.stop()
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown action"})
            return
        self._json(HTTPStatus.OK if ok else HTTPStatus.CONFLICT, {
            "ok": ok,
            "message": message,
            "tool": public_tool(TOOLS_BY_ID[tool_id]),
        })


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def stop_all() -> None:
    for manager in PROCESSES.values():
        if manager.is_running():
            manager.stop()


def main() -> int:
    server = ReusableThreadingHTTPServer((HOST, PORT), DashboardHandler)
    address = f"http://{HOST}:{PORT}"
    print(f"Creator Control Center running at {address}")
    print("Press Ctrl+C to stop the dashboard and managed tools.")
    if os.getenv("CREATOR_DASHBOARD_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Creator Control Center...")
    finally:
        server.shutdown()
        server.server_close()
        stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
