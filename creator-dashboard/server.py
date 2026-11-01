from __future__ import annotations

import json
import os
import re
import stat
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from security import redact, redact_tree, local_request_allowed
from runtime_config import resolve_tool_command

import article_drafter
import video_drafter
import youtube_analytics

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
            try:
                command = resolve_tool_command(self.tool)
            except ValueError as exc:
                return False, str(exc)
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
                    start_new_session=os.name != "nt",
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
            threading.Thread(target=self._watch_exit, args=(self.process,), daemon=True).start()
            return True, "Start command submitted"

    def _read_pipe(self, label: str, pipe) -> None:
        try:
            for line in iter(pipe.readline, ""):
                value = line.rstrip()
                if value:
                    with self.lock:
                        self.logs.append(redact(f"[{label}] {value}"))
        finally:
            pipe.close()

    def _watch_exit(self, process) -> None:
        if process is None:
            return
        exit_code = process.wait()
        with self.lock:
            if self.process is process:
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
                    if os.name == "nt":
                        process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
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
            return [redact(line) for line in self.logs]


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
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open(request, timeout=0.7) as response:
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


def public_tools() -> list[dict[str, Any]]:
    catalog=list(TOOLS)
    if not catalog:return []
    # Closed loopback ports can consume the full connect timeout on Windows.
    # Independent probes should not accumulate into one multi-second delay.
    with ThreadPoolExecutor(max_workers=min(8,len(catalog))) as pool:
        return list(pool.map(public_tool,catalog))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "CreatorDashboard/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        host = self.headers.get("Host", "")
        valid = len(self.headers.get_all('Host', [])) == 1 and len(self.headers.get_all('Origin', [])) <= 1
        valid = valid and local_request_allowed(host, self.headers.get('Origin'), self.server.server_port, self.headers.get('Sec-Fetch-Site'))
        if not valid:
            self.send_error(403, "Local Host/Origin required")
            return False
        if self.headers.get_all('Transfer-Encoding') or len(self.headers.get_all('Content-Length', []))>1:
            self.send_error(400, 'Ambiguous request framing')
            return False
        return True

    def log_message(self, format: str, *args) -> None:
        print(redact(f"[{self.log_date_time_string()}] {format % args}"))

    def end_headers(self):
        self.send_header('Referrer-Policy','no-referrer')
        super().end_headers()

    def send_head(self):
        target=Path(self.translate_path(self.path))
        if not target.resolve().is_relative_to(STATIC_DIR.resolve()) or any(part.startswith('.') for part in target.relative_to(STATIC_DIR).parts):
            self.send_error(404);return None
        if target.exists() and not target.is_dir() and not target.is_file():
            self.send_error(404);return None
        return super().send_head()

    def list_directory(self,path):
        self.send_error(404);return None

    def _video_file(self,path,content_type):
        """Stream one validated file descriptor, with real seek support for MP4."""
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):raise FileNotFoundError(path.name)
            size=info.st_size;start=0;end=size-1;status=HTTPStatus.OK
            value=self.headers.get('Range') if content_type=='video/mp4' else None
            if value:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',value.strip())
                try:
                    if not match or not any(match.groups()):raise ValueError
                    left,right=match.groups()
                    if left:
                        start=int(left);end=min(int(right),size-1) if right else size-1
                    else:
                        suffix=int(right)
                        if suffix<=0:raise ValueError
                        start=max(0,size-suffix)
                    if start>=size or end<start:raise ValueError
                except ValueError:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
                status=HTTPStatus.PARTIAL_CONTENT
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            if content_type=='application/zip':self.send_header('Content-Disposition','attachment; filename="production-bundle.zip"')
            self.send_header('Content-Length',str(max(0,end-start+1)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if content_type=='video/mp4':self.send_header('Accept-Ranges','bytes')
            if status==HTTPStatus.PARTIAL_CONTENT:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            if path.name=='index.html':
                self.send_header('Content-Security-Policy',"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            if self.command=='HEAD':return
            source.seek(start);remaining=end-start+1
            try:
                while remaining>0:
                    block=source.read(min(512*1024,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
            except (BrokenPipeError,ConnectionResetError):pass

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(redact_tree(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        try:
            if self.command!='HEAD':self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Browser menutup koneksi saat pindah halaman atau refresh; bukan error server.

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
        body=self.rfile.read(length)
        if len(body)!=length:
            self._json(HTTPStatus.BAD_REQUEST, {"error":"Body tidak lengkap"})
            return None
        return body

    def _article_error(self, exc: Exception) -> None:
        if isinstance(exc, FileNotFoundError):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Tidak ditemukan"})
        elif isinstance(exc, PermissionError):
            self._json(HTTPStatus.CONFLICT, {"error":"Tutup dokumen Word atau aplikasi yang mengunci file, lalu coba lagi"})
        elif isinstance(exc, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        elif isinstance(exc, article_drafter.LLMError):
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        else:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error":"Operasi artikel gagal; data sebelumnya dipertahankan bila transaksi belum selesai"})

    def _articles_get(self, parts: list[str]) -> None:
        try:
            if parts == ["api", "articles"]:
                self._json(HTTPStatus.OK, {"articles": article_drafter.list_articles()})
            elif parts == ["api", "articles", "options"]:
                self._json(HTTPStatus.OK, article_drafter.options())
            elif len(parts) == 4 and parts[2] == "jobs":
                self._json(HTTPStatus.OK, article_drafter.job_status(unquote(parts[3])))
            elif len(parts) == 4 and parts[3] == "evidence":
                from article_tools import evidence_report
                self._json(HTTPStatus.OK, evidence_report(unquote(parts[2])))
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
                if self.command!='HEAD':self.wfile.write(data)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        except Exception as exc:  # noqa: BLE001 - dipetakan ke status HTTP di _article_error
            self._article_error(exc)

    def _articles_post(self, parts: list[str]) -> None:
        try:
            if parts == ["api", "articles", "source"]:
                raw = self._read_body(10_000)
                if raw is None: return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict): raise ValueError("Body harus objek JSON")
                from source_reader import retrieve
                self._json(HTTPStatus.OK, retrieve(str(payload.get("url", ""))))
            elif parts == ["api", "articles"]:
                raw = self._read_body(200_000)
                if raw is None:
                    return
                self._json(HTTPStatus.ACCEPTED, article_drafter.start_job(json.loads(raw or b"{}")))
            elif len(parts) == 4 and parts[3] in {"evidence", "rewrite", "apply-rewrite", "diagram"}:
                raw = self._read_body(200_000)
                if raw is None: return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict): raise ValueError("Body harus objek JSON")
                from article_tools import update_evidence, propose_rewrite, apply_rewrite, add_diagram
                action = {"evidence": update_evidence, "rewrite": propose_rewrite, "apply-rewrite": apply_rewrite, "diagram": add_diagram}[parts[3]]
                self._json(HTTPStatus.OK, action(unquote(parts[2]), payload))
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

    def _videos_get(self, parts: list[str]) -> None:
        try:
            if parts == ["api", "videos"]:
                self._json(HTTPStatus.OK, {"videos": video_drafter.list_videos()})
            elif parts == ["api", "videos", "jobs"]:
                self._json(HTTPStatus.OK, {"jobs": video_drafter.list_jobs()})
            elif parts == ["api", "videos", "options"]:
                self._json(HTTPStatus.OK, video_drafter.options())
            elif parts == ['api','videos','brands']:
                import creative_profile
                self._json(HTTPStatus.OK,creative_profile.catalog(video_drafter.VIDEOS_DIR.parent/'brand-kits.json'))
            elif len(parts) == 4 and parts[2] == "jobs":
                self._json(HTTPStatus.OK, video_drafter.job_status(unquote(parts[3])))
            elif len(parts) == 3:
                self._json(HTTPStatus.OK, video_drafter.get_video(unquote(parts[2])))
            elif len(parts)==4 and parts[3]=='bundle':
                from video_bundle import build
                slug=unquote(parts[2])
                video_drafter.get_video(slug)  # Require a completed result, not a partial render directory.
                with build(video_drafter._video_directory(slug)) as path:
                    self._video_file(path,'application/zip')
            elif len(parts) == 4:
                slug, filename = unquote(parts[2]), unquote(parts[3])
                path, content_type = video_drafter.video_file_path(slug, filename)
                self._video_file(path,content_type)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        except KeyError as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except FileNotFoundError as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except ValueError as exc:
            from video_bundle import BundleBusy
            self._json(HTTPStatus.CONFLICT if isinstance(exc,BundleBusy) else HTTPStatus.BAD_REQUEST,{'error':str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _videos_post(self, parts: list[str]) -> None:
        try:
            if parts==['api','videos','brands']:
                raw=self._read_body(10000)
                if raw is None:return
                payload=json.loads(raw or b'{}')
                if not isinstance(payload,dict):raise ValueError('Body harus objek JSON')
                import creative_profile
                self._json(HTTPStatus.OK,creative_profile.save(video_drafter.VIDEOS_DIR.parent/'brand-kits.json',payload))
            elif parts == ["api", "videos"]:
                raw = self._read_body(200_000)
                if raw is None:
                    return
                self._json(HTTPStatus.ACCEPTED, video_drafter.start_job(json.loads(raw or b"{}")))
            elif len(parts) == 4 and parts[3] == "aspects":
                raw = self._read_body(10_000)
                if raw is None: return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict): raise ValueError("Body harus objek JSON")
                self._json(HTTPStatus.ACCEPTED, {"jobs": video_drafter.create_aspect_jobs(unquote(parts[2]), payload.get("aspects"))})
            elif len(parts) == 5 and parts[2] == "jobs" and parts[4] == "approve":
                raw = self._read_body(10_000)
                if raw is None:
                    return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict) or type(payload.get("revision")) is not int:
                    raise ValueError("Revisi pekerjaan wajib disertakan")
                stage = str(payload.get("stage") or "")
                self._json(HTTPStatus.ACCEPTED, video_drafter.approve_job(unquote(parts[3]), stage, payload["revision"]))
            elif len(parts) == 5 and parts[2] == "jobs" and parts[4] in {"revise", "resume"}:
                raw = self._read_body(10_000)
                if raw is None:
                    return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict) or type(payload.get("revision")) is not int:
                    raise ValueError("Revisi pekerjaan wajib disertakan")
                action = video_drafter.resume_job if parts[4] == "resume" else video_drafter.revise_job
                self._json(HTTPStatus.OK, action(unquote(parts[3]), payload["revision"]))
            elif len(parts) == 5 and parts[2] == "jobs" and parts[4] == "edit":
                raw = self._read_body(500_000)
                if raw is None:
                    return
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict) or type(payload.get("revision")) is not int:
                    raise ValueError("Revisi pekerjaan wajib disertakan")
                self._json(HTTPStatus.OK, video_drafter.update_job_plan(unquote(parts[3]), payload))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Body bukan JSON valid"})
        except video_drafter.RevisionConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Pekerjaan tidak ditemukan"})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _analytics_post(self, parts: list[str]) -> None:
        try:
            raw = self._read_body(youtube_analytics.MAX_CSV_BYTES + youtube_analytics.MAX_TRANSCRIPT_CHARS + 1_000_000)
            if raw is None:
                return
            payload = json.loads(raw or b"{}")
            if not isinstance(payload, dict): raise ValueError("Body harus objek JSON")
            if parts == ["api", "analytics", "source"]:
                from source_reader import retrieve
                result = retrieve(str(payload.get("url", "")))
            elif parts == ["api", "analytics", "import", "inspect"]:
                from analytics_import import inspect_csv
                data = inspect_csv(str(payload.get("csv") or ""))
                result = {key: data[key] for key in ("headers", "preview", "row_count")}
            elif parts == ["api", "analytics", "import"]:
                from analytics_import import mapped_import
                result = mapped_import(str(payload.get("csv") or ""), payload.get("platform"), payload.get("mapping"), payload.get("units", "percent"), payload.get("scenes"))
            elif parts == ["api", "analytics", "observations"]:
                from analytics_learning import create
                result = create(payload)
            elif len(parts) == 5 and parts[:3] == ["api", "analytics", "observations"] and parts[4] == "decision":
                from analytics_learning import decide
                result = decide(parts[3], payload.get("revision"), payload.get("approve"))
            elif parts == ["api", "analytics", "retention"]:
                csv_text = str(payload.get("csv") or "")
                result = youtube_analytics.analyze_retention(
                    csv_text.encode("utf-8"),
                    str(payload.get("transcript") or ""),
                    float(payload["duration"]) if payload.get("duration") not in (None, "") else None,
                    str(payload.get("units") or "auto"),
                )
                if payload.get("scenes"):
                    from analytics_import import scene_retention
                    result["scenes"] = scene_retention(result["points"], result["events"], payload["scenes"])
            elif parts == ["api", "analytics", "package"]:
                result = youtube_analytics.lint_package(
                    str(payload.get("title") or ""),
                    str(payload.get("thumbnail") or ""),
                    str(payload.get("transcript") or ""),
                )
            elif parts == ["api", "analytics", "hook"]:
                result = youtube_analytics.review_hook(str(payload.get("hook") or ""))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
                return
            self._json(HTTPStatus.OK, result)
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Body bukan JSON valid"})
        except (TypeError, ValueError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except FileNotFoundError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Observasi tidak ditemukan"})
        except (OSError, urllib.error.URLError):
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "Sumber atau penyimpanan tidak tersedia"})

    def do_HEAD(self) -> None:
        if self._route_parts()[:1]==['api']:
            self.do_GET()
        else:
            super().do_HEAD()

    def _clipper_proxy(self, path: str) -> None:
        # ponytail: GET-only, fixed upstream; cukup untuk health/production. Tambah rute bila perlu.
        try:
            request = urllib.request.Request(f"http://127.0.0.1:8765{path}")
            token = os.getenv("CLIPPER_TOKEN")
            if token:
                request.add_header("Authorization", f"Bearer {token}")
            with urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open(request, timeout=2) as r:
                body = json.loads(r.read().decode("utf-8"))
            self._json(HTTPStatus.OK, body)
        except Exception as exc:
            self._json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:
        parts = self._route_parts()
        if parts == ["api", "health"]:
            self._json(HTTPStatus.OK,{"ok":True,"service":"creator-dashboard","toolCount":len(TOOLS)})
            return
        if parts == ["api", "clipper", "health"]:
            self._clipper_proxy("/api/health")
            return
        if parts == ["api", "clipper", "production"]:
            self._clipper_proxy("/api/production")
            return
        if parts[:2] == ["api", "videos"]:
            self._videos_get(parts)
            return
        if parts[:2] == ["api", "articles"]:
            self._articles_get(parts)
            return
        if parts == ["api", "analytics", "observations"]:
            from analytics_learning import list_observations
            self._json(HTTPStatus.OK, {"observations": list_observations()})
            return
        if parts == ["api", "tools"]:
            sync_tools()
            self._json(HTTPStatus.OK, {"tools": public_tools()})
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
        if parts[:2] == ["api", "analytics"]:
            self._analytics_post(parts)
            return
        if parts[:2] == ["api", "videos"]:
            self._videos_post(parts)
            return
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


    def do_DELETE(self) -> None:
        parts = self._route_parts()
        if len(parts) == 3 and parts[:2] == ["api", "videos"]:
            try:
                self._json(HTTPStatus.OK, video_drafter.delete_video(unquote(parts[2])))
            except (FileNotFoundError, ValueError) as exc:
                self._json(HTTPStatus.NOT_FOUND if isinstance(exc, FileNotFoundError) else HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def stop_all() -> None:
    for manager in PROCESSES.values():
        if manager.is_running():
            manager.stop()


def main() -> int:
    if HOST not in {'127.0.0.1','localhost'}:
        raise ValueError('Dashboard tanpa autentikasi wajib bind ke loopback IPv4')
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
