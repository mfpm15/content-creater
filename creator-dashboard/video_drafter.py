"""Opuscar-only dynamic video planning and rendering pipeline."""
from __future__ import annotations

import html
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS_DIR = ROOT / "output" / "videos"
HYPERFRAMES_APP_DIR = ROOT / "apps" / "hyperframes"
OPUSCAR_DIR = ROOT / "apps" / "lemo-opuscar"
LLM_URL = os.getenv("VIDEO_LLM_BASE_URL", "http://localhost:20128/v1").rstrip("/")
LLM_MODEL = os.getenv("VIDEO_LLM_MODEL", "ms/GPT-5.6-Think-Deeper")
LLM_KEY = os.getenv("VIDEO_LLM_API_KEY", "9router-local")
LLM_TIMEOUT = int(os.getenv("VIDEO_LLM_TIMEOUT", "120"))

STYLES = {"opuscar_cinematic": {"id": "opuscar_cinematic", "name": "Opuscar Cinematic", "description": "Visual prosedural dinamis berdasarkan tipe adegan."}}
ASPECT_RATIOS = {
    "9:16": {"id": "9:16", "width": 1080, "height": 1920, "label": "9:16 Vertikal"},
    "16:9": {"id": "16:9", "width": 1920, "height": 1080, "label": "16:9 Horizontal"},
    "1:1": {"id": "1:1", "width": 1080, "height": 1080, "label": "1:1 Persegi"},
}
DURATIONS = [15, 30, 45, 60, 90]
ENGINES = {"opuscar": {"id": "opuscar", "name": "Opuscar", "description": "Pipeline film prosedural dinamis.", "defaultStyle": "opuscar_cinematic"}}
DEFAULT_MODELS = [
    {"id": "ms/GPT-5.6-Think-Deeper", "name": "Microsoft GPT-5.6 Think Deeper"},
    {"id": "cc/claude-opus-5-5", "name": "Claude Opus 5.5"},
    {"id": "cc/claude-sonnet-5-5", "name": "Claude Sonnet 5.5"},
]
ALLOWED_MODEL_IDS = {item["id"] for item in DEFAULT_MODELS}
JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}
TIMECODE_RE = re.compile(r"(?m)^\s*(?P<start>\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*(?:-->|-|–|—)\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*[:|]?\s*(?P<body>.*?)(?=^\s*(?:\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*(?:-->|-|–|—)|\Z)", re.S)
FIELD_RE = re.compile(r"(?im)^\s*(narasi|narration|visual|teks(?: layar)?|on.?screen|suara|sound|sfx|tipe|type)\s*:\s*(.+)$")


def get_available_models() -> list[dict]:
    return list(DEFAULT_MODELS)


def options() -> dict:
    return {"engines": list(ENGINES.values()), "styles": list(STYLES.values()), "aspects": list(ASPECT_RATIOS.values()), "durations": DURATIONS, "models": get_available_models(), "defaultEngine": "opuscar", "defaultStyle": "opuscar_cinematic", "defaultAspect": "9:16", "defaultDuration": 60, "defaultModel": LLM_MODEL}


def _seconds(value: str) -> float:
    parts = [float(part) for part in value.split(":")]
    return sum(part * (60 ** index) for index, part in enumerate(reversed(parts)))


def _scene_type(text: str) -> str:
    value = text.lower()
    if any(word in value for word in ("%", "data", "angka", "statistik", "grafik")): return "data"
    if any(word in value for word in ("langkah", "cara", "proses", "pertama", "kedua", "ketiga")): return "process"
    if any(word in value for word in ("banding", "versus", "sebelum", "sesudah")): return "comparison"
    if any(word in value for word in ("ajak", "mulai", "sekarang", "bagikan", "hubungi")): return "call-to-action"
    return "story"


def _parse_fields(body: str) -> dict:
    fields: dict[str, str] = {}
    matches = list(FIELD_RE.finditer(body))
    if not matches:
        return {"narration": " ".join(body.split())}
    for match in matches:
        key = match.group(1).lower()
        value = match.group(2).strip()
        if key in ("narasi", "narration"): fields["narration"] = value
        elif key.startswith("visual"): fields["visual"] = value
        elif key.startswith("teks") or key.startswith("on"): fields["onScreenText"] = value
        elif key in ("suara", "sound", "sfx"): fields["soundCue"] = value
        else: fields["type"] = value
    return fields


def parse_explicit_scenes(script: str) -> list[dict]:
    scenes = []
    for match in TIMECODE_RE.finditer(script):
        start, end = _seconds(match["start"]), _seconds(match["end"])
        if end <= start: raise ValueError("Timecode akhir harus lebih besar dari awal")
        fields = _parse_fields(match["body"])
        narration = fields.get("narration", "").strip()
        scenes.append({"start": start, "end": end, "duration": end - start, "narration": narration, "visual": fields.get("visual", ""), "onScreenText": fields.get("onScreenText", narration[:80]), "soundCue": fields.get("soundCue", ""), "type": fields.get("type") or _scene_type(" ".join(fields.values()))})
    for previous, current in zip(scenes, scenes[1:]):
        if current["start"] < previous["end"]: raise ValueError("Timecode adegan tidak boleh tumpang tindih")
    return scenes


def proportional_scenes(topic: str, script: str, duration: int) -> list[dict]:
    chunks = [item.strip() for item in re.split(r"\n\s*\n|(?<=[.!?])\s+", script) if item.strip()]
    if not chunks: chunks = [topic]
    count = min(12, max(1, len(chunks)))
    chunks = chunks[:count]
    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total = sum(weights)
    cursor = 0.0
    scenes = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        end = float(duration) if index == len(chunks) - 1 else round(cursor + duration * weight / total, 3)
        scenes.append({"start": cursor, "end": end, "duration": end - cursor, "narration": chunk, "visual": "", "onScreenText": chunk[:80], "soundCue": "", "type": _scene_type(chunk)})
        cursor = end
    return scenes


def normalize_scene_plan(data: dict, topic: str, script: str, duration: int) -> dict:
    explicit = parse_explicit_scenes(script)
    source = explicit or (data.get("scenes") if isinstance(data.get("scenes"), list) else [])
    if not source: source = proportional_scenes(topic, script, duration)
    scenes = []
    for index, raw in enumerate(source):
        narration = str(raw.get("narration") or raw.get("script") or "").strip()
        start = float(raw.get("start", 0))
        end = float(raw.get("end", start + float(raw.get("duration", 0))))
        scenes.append({"id": f"scene-{index + 1}", "start": start, "end": end, "duration": end - start, "narration": narration, "visual": str(raw.get("visual") or ""), "onScreenText": str(raw.get("onScreenText") or raw.get("text") or narration[:80]), "soundCue": str(raw.get("soundCue") or raw.get("sound") or ""), "type": str(raw.get("type") or _scene_type(" ".join((narration, str(raw.get("visual") or "")))) )})
    if explicit:
        duration = int(max(scene["end"] for scene in scenes))
    elif scenes:
        weights = [max(1, len(scene["narration"].split())) for scene in scenes]
        cursor = 0.0
        for index, scene in enumerate(scenes):
            end = float(duration) if index == len(scenes) - 1 else round(cursor + duration * weights[index] / sum(weights), 3)
            scene.update(start=cursor, end=end, duration=end - cursor)
            cursor = end
    return {"topic": topic, "duration": duration, "scenes": scenes}


def build_scene_prompt(topic: str, script: str, duration: int, aspect: str) -> str:
    return f"""Buat scene plan Opuscar dinamis. Jangan ubah narasi atau timecode eksplisit. Topik: {topic}\nDurasi: {duration}\nRasio: {aspect}\nInput user:\n{script}\nBalas JSON: {{\"scenes\":[{{\"start\":0,\"end\":5,\"narration\":\"...\",\"visual\":\"...\",\"onScreenText\":\"...\",\"soundCue\":\"...\",\"type\":\"story|data|process|comparison|call-to-action\"}}]}}. Jika tanpa timecode, bagi durasi proporsional terhadap narasi."""


def _call_9router(prompt: str, model: str = "") -> str:
    body = {"model": model or LLM_MODEL, "stream": False, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "Return valid JSON only. Preserve user facts, narration, and explicit timecodes."}, {"role": "user", "content": prompt}]}
    request = urllib.request.Request(f"{LLM_URL}/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:
        data = json.loads(response.read().decode())
    return data["choices"][0]["message"]["content"]


def _clean_json(raw: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match: raise ValueError("LLM tidak mengembalikan JSON")
    return json.loads(match.group())


def _visual_markup(scene: dict) -> str:
    kind = scene["type"]
    if kind == "data": return '<div class="grammar data"><i></i><i></i><i></i><i></i></div>'
    if kind == "process": return '<div class="grammar process"><i>1</i><i>2</i><i>3</i></div>'
    if kind == "comparison": return '<div class="grammar compare"><i></i><b>VS</b><i></i></div>'
    if kind == "call-to-action": return '<div class="grammar cta">✦</div>'
    return '<div class="grammar story"><i></i><i></i><i></i></div>'


def generate_composition(plan: dict, aspect_info: dict, model: str = "") -> str:
    width, height, duration = aspect_info["width"], aspect_info["height"], plan["duration"]
    sections, animation = [], []
    for index, scene in enumerate(plan["scenes"]):
        start, length = scene["start"], scene["duration"]
        sections.append(f'<section class="scene clip type-{html.escape(scene["type"])}" data-start="{start}" data-duration="{length}" data-track-index="{index}">{_visual_markup(scene)}<div class="copy"><small>{index + 1:02d} / {len(plan["scenes"]):02d}</small><h2>{html.escape(scene["onScreenText"])}</h2><p>{html.escape(scene["visual"])}</p></div><div class="subtitle">{html.escape(scene["narration"])}</div></section>')
        animation.append(f"tl.set(s[{index}],{{opacity:1}}, {start}).from(s[{index}].querySelector('.grammar'),{{scale:.78,rotation:-5,opacity:0,duration:.7}}, {start}).from(s[{index}].querySelector('.copy'),{{y:60,opacity:0,duration:.6}}, {start + .12}).set(s[{index}],{{opacity:0}}, {scene['end']});")
    title = html.escape(plan["topic"])
    return f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><title>{title}</title><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#030712;color:#fff;font-family:system-ui;overflow:hidden}}#stage{{width:{width}px;height:{height}px;position:relative;background:radial-gradient(circle at 70% 10%,#164e63,#030712 55%)}}.scene{{position:absolute;inset:0;opacity:0;padding:8%;overflow:hidden}}.scene:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(#22d3ee18 1px,transparent 1px),linear-gradient(90deg,#22d3ee18 1px,transparent 1px);background-size:60px 60px}}.grammar{{position:absolute;left:9%;right:9%;top:13%;height:48%;border:2px solid #22d3ee88;border-radius:42px;background:#071525cc;display:flex;align-items:center;justify-content:center;gap:5%;box-shadow:0 30px 100px #000}}.data i{{width:12%;background:linear-gradient(#22d3ee,#8b5cf6);align-self:flex-end;margin-bottom:8%;border-radius:18px 18px 0 0}}.data i:nth-child(1){{height:28%}}.data i:nth-child(2){{height:50%}}.data i:nth-child(3){{height:72%}}.data i:nth-child(4){{height:90%}}.process i{{width:20%;aspect-ratio:1;border-radius:50%;display:grid;place-items:center;background:#0e7490;font:900 52px system-ui}}.compare i{{width:30%;height:55%;border-radius:30px;background:linear-gradient(135deg,#0891b2,#7c3aed)}}.compare b{{font-size:48px}}.cta{{font-size:220px;color:#fbbf24}}.story i{{position:absolute;border-radius:50%;border:5px solid #22d3ee;box-shadow:0 0 50px #22d3ee}}.story i:nth-child(1){{width:48%;aspect-ratio:1}}.story i:nth-child(2){{width:28%;aspect-ratio:1;left:8%}}.story i:nth-child(3){{width:18%;aspect-ratio:1;right:9%}}.copy{{position:absolute;left:8%;right:8%;top:65%}}small{{color:#22d3ee;letter-spacing:.25em;font-weight:800}}h2{{font-size:{72 if height > width else 58}px;line-height:1.03;margin:18px 0}}.copy p{{font-size:26px;color:#bae6fd}}.subtitle{{position:absolute;left:6%;right:6%;bottom:5%;padding:22px 30px;border-radius:20px;background:#020617e8;text-align:center;font-size:{32 if height > width else 25}px}}.model{{position:absolute;right:3%;top:2%;color:#ffffff66;font-size:15px}}
</style></head><body><div id="stage" data-composition-id="video" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}"><div class="model">OPUSCAR · {html.escape(model)}</div>{''.join(sections)}<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script><script>const tl=gsap.timeline({{paused:true}}),s=document.querySelectorAll('.scene');{''.join(animation)}window.__timelines=window.__timelines||{{}};window.__timelines.video=tl;</script></div></body></html>'''


def audio_manifest(plan: dict) -> dict:
    return {"duration": plan["duration"], "voice": [{"id": scene["id"], "start": scene["start"], "end": scene["end"], "text": scene["narration"]} for scene in plan["scenes"]], "subtitles": [{"start": scene["start"], "end": scene["end"], "text": scene["narration"]} for scene in plan["scenes"]], "soundCues": [{"at": scene["start"], "cue": scene["soundCue"]} for scene in plan["scenes"] if scene["soundCue"]], "music": {"start": 0, "end": plan["duration"], "duckUnderVoice": True, "targetLufs": -14}}


def _srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000); hours, remainder = divmod(milliseconds, 3600000); minutes, remainder = divmod(remainder, 60000); secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_subtitles(path: Path, plan: dict) -> None:
    path.write_text("\n\n".join(f"{index}\n{_srt_time(scene['start'])} --> {_srt_time(scene['end'])}\n{scene['narration']}" for index, scene in enumerate(plan["scenes"], 1)) + "\n", encoding="utf-8")


def list_videos() -> list[dict]:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True); results = []
    for directory in sorted(VIDEOS_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8")); video = directory / "video.mp4"
            if video.is_file(): meta.update(videoSize=video.stat().st_size, videoUrl=f"/api/videos/{directory.name}/video.mp4", htmlUrl=f"/api/videos/{directory.name}/index.html"); results.append(meta)
        except (OSError, ValueError): pass
    return results


def get_video(slug: str) -> dict:
    target = VIDEOS_DIR / slug; meta = json.loads((target / "metadata.json").read_text(encoding="utf-8")); video = target / "video.mp4"
    if not video.is_file(): raise FileNotFoundError(slug)
    meta.update(videoSize=video.stat().st_size, videoUrl=f"/api/videos/{slug}/video.mp4", htmlUrl=f"/api/videos/{slug}/index.html"); return meta


def read_video_file(slug: str, filename: str) -> tuple[bytes, str]:
    if filename not in {"video.mp4", "index.html", "subtitles.srt"}: raise FileNotFoundError(filename)
    path = VIDEOS_DIR / slug / filename
    if not path.is_file(): raise FileNotFoundError(filename)
    return path.read_bytes(), {".mp4": "video/mp4", ".html": "text/html; charset=utf-8", ".srt": "text/plain; charset=utf-8"}.get(path.suffix, "application/octet-stream")


def job_status(job_id: str) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS: raise KeyError(job_id)
        return dict(JOBS[job_id])


def start_job(payload: dict) -> dict:
    topic = str(payload.get("topic") or "").strip()
    if not topic: raise ValueError("Topik video wajib diisi")
    aspect = str(payload.get("aspect") or "9:16"); aspect = aspect if aspect in ASPECT_RATIOS else "9:16"
    duration = int(payload.get("duration") or 60); duration = duration if duration in DURATIONS else 60
    model = str(payload.get("model") or LLM_MODEL); model = model if model in ALLOWED_MODEL_IDS else LLM_MODEL
    job_id = uuid.uuid4().hex
    job = {"jobId": job_id, "topic": topic, "script": str(payload.get("script") or "").strip(), "engine": "opuscar", "style": "opuscar_cinematic", "aspect": aspect, "duration": duration, "model": model, "status": "queued", "step": "Menyiapkan scene plan", "progress": 5, "error": None, "video": None}
    with JOBS_LOCK: JOBS[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"jobId": job_id, "status": "queued"}


def _update_job(job_id: str, values: dict) -> None:
    with JOBS_LOCK: JOBS[job_id].update(values)


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:50] or "video"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _write_procedural_audio(path: Path, plan: dict, sample_rate: int = 48000) -> None:
    """Create music bed and cue-driven foley without external assets."""
    cues = [(float(item["at"]), str(item["cue"]).lower()) for item in audio_manifest(plan)["soundCues"]]
    frames = bytearray()
    for sample in range(round(plan["duration"] * sample_rate)):
        t = sample / sample_rate
        pulse = 0.55 + 0.45 * math.sin(2 * math.pi * 2 * t)
        value = 0.055 * pulse * (math.sin(2 * math.pi * 110 * t) + 0.35 * math.sin(2 * math.pi * 220 * t))
        for cue_at, cue_name in cues:
            local = t - cue_at
            if 0 <= local < 0.35:
                frequency = 1200 if any(word in cue_name for word in ("bell", "chime", "ding")) else 420
                value += 0.18 * (1 - local / 0.35) * math.sin(2 * math.pi * frequency * local)
        frames.extend(int(max(-1, min(1, value)) * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, sample_rate, len(frames) // 2, "NONE", "not compressed"))
        output.writeframes(frames)


def _build_audio(target: Path, plan: dict) -> Path:
    """Synthesize narration per scene, align it, mix music/foley, and normalize."""
    ffmpeg = shutil.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
    python = OPUSCAR_DIR / ".venv" / "Scripts" / "python.exe"
    tts = OPUSCAR_DIR / "core" / "tts" / "tts_zh.py"
    if not Path(ffmpeg).is_file() and not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg tidak ditemukan untuk audio mux")
    if not python.is_file():
        raise RuntimeError("Opuscar voice environment belum tersedia")
    lines = [{"id": scene["id"], "text": scene["narration"], "voice": "id-ID-ArdiNeural", "rate": "+8%"} for scene in plan["scenes"]]
    lines_path = target / "voice-lines.json"
    voice_dir = target / "voice"
    lines_path.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([str(python), str(tts), str(lines_path), str(voice_dir), "--voice", "id-ID-ArdiNeural", "--rate", "+8%"], check=True, timeout=600)
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, scene in enumerate(plan["scenes"]):
        voice_file = voice_dir / f"{scene['id']}.wav"
        inputs.extend(["-i", str(voice_file)])
        delay = round(scene["start"] * 1000)
        label = f"v{index}"
        filters.append(f"[{index}:a]adelay={delay}|{delay},apad,atrim=0:{plan['duration']}[{label}]")
        labels.append(f"[{label}]")
    voice_mix = target / "voice.wav"
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,atrim=0:{plan['duration']}[voice]")
    subprocess.run([ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[voice]", "-ar", "48000", str(voice_mix)], check=True, timeout=600)
    bed = target / "music-foley.wav"
    _write_procedural_audio(bed, plan)
    final = target / "final-audio.wav"
    mix = "[0:a]volume=.32[bed];[bed][1:a]sidechaincompress=threshold=.025:ratio=8:attack=12:release=350[ducked];[ducked][1:a]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]"
    subprocess.run([ffmpeg, "-y", "-i", str(bed), "-i", str(voice_mix), "-filter_complex", mix, "-map", "[a]", "-t", str(plan["duration"]), "-ar", "48000", str(final)], check=True, timeout=600)
    return final


def _mux_video(target: Path, silent: Path, audio: Path, duration: float) -> Path:
    ffmpeg = shutil.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
    output = target / "video.mp4"
    subprocess.run([ffmpeg, "-y", "-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(duration), "-movflags", "+faststart", str(output)], check=True, timeout=600)
    return output


def _run_job(job_id: str) -> None:
    job = job_status(job_id); target = VIDEOS_DIR / _slugify(job["topic"])
    try:
        _update_job(job_id, {"status": "generating", "step": "Menganalisis input menjadi scene plan", "progress": 15})
        explicit = parse_explicit_scenes(job["script"])
        data = {} if explicit else _clean_json(_call_9router(build_scene_prompt(job["topic"], job["script"], job["duration"], job["aspect"]), job["model"]))
        plan = normalize_scene_plan(data, job["topic"], job["script"], job["duration"])
        target.mkdir(parents=True); (target / "scene-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (target / "audio-manifest.json").write_text(json.dumps(audio_manifest(plan), ensure_ascii=False, indent=2), encoding="utf-8"); write_subtitles(target / "subtitles.srt", plan)
        (target / "index.html").write_text(generate_composition(plan, ASPECT_RATIOS[job["aspect"]], job["model"]), encoding="utf-8")
        _update_job(job_id, {"step": "Merender visual dinamis dengan renderer internal", "progress": 50})
        renderer = HYPERFRAMES_APP_DIR / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
        silent = target / "silent.mp4"
        subprocess.run(["node", str(renderer), "render", "-o", str(silent), "--fps", "30"], cwd=target, check=True, timeout=600)
        _update_job(job_id, {"step": "Membuat dubbing, musik, foley, dan subtitle", "progress": 72})
        final_audio = _build_audio(target, plan)
        _update_job(job_id, {"step": "Melakukan mux audio dan video", "progress": 90})
        output = _mux_video(target, silent, final_audio, plan["duration"])
        silent.unlink(missing_ok=True)
        meta = {"slug": target.name, "topic": job["topic"], "engine": "opuscar", "model": job["model"], "style": STYLES["opuscar_cinematic"], "aspect": ASPECT_RATIOS[job["aspect"]], "duration": plan["duration"], "sceneCount": len(plan["scenes"]), "scenePlan": plan, "audioManifest": audio_manifest(plan), "videoBytes": output.stat().st_size, "createdAt": time.time(), "formattedTime": time.strftime("%Y-%m-%d %H:%M:%S")}
        (target / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _update_job(job_id, {"status": "succeeded", "step": "Video Opuscar selesai", "progress": 100, "video": {"slug": target.name, "title": job["topic"], "videoUrl": f"/api/videos/{target.name}/video.mp4", "htmlUrl": f"/api/videos/{target.name}/index.html", "duration": plan["duration"]}})
    except Exception as exc:
        _update_job(job_id, {"status": "failed", "step": f"Gagal: {exc}", "progress": 100, "error": str(exc)})
