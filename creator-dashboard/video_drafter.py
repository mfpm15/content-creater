"""Reviewed video planning and rendering across independent local adapters."""
from __future__ import annotations

import renderer_contract
import video_preproduction as preproduction
import sound_effects
import speech_settings
import voice_quality
import video_templates
import faceless_quality
import frame_rate
import scene_diagram
import html
import copy
import hashlib
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
from security import open_authenticated, render_environment

from video_job_store import save_job, recover_jobs
from runtime_config import resolve_python
import creative_profile
import continuous_motion
import animation_clock
import scene_render
import opuscar_scene_spec
import opuscar_primitives
import opuscar_quality_gate
import remotion_adapter
import audio_mastering

ROOT = Path(__file__).resolve().parent
VIDEOS_DIR = ROOT / "output" / "videos"
HYPERFRAMES_APP_DIR = ROOT / "apps" / "hyperframes"
OPUSCAR_DIR = ROOT / "apps" / "lemo-opuscar"
PODCASTFY_PYTHON = resolve_python(ROOT / "apps" / "podcastfy")
RESEARCH_WORKER = ROOT / "google_search_research.py"
RESEARCH_MODEL = os.getenv("VIDEO_RESEARCH_MODEL", "gemini-2.5-flash")
LLM_URL = os.getenv("VIDEO_LLM_BASE_URL", os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "http://localhost:20128/v1").rstrip("/")
LLM_MODEL = os.getenv("VIDEO_LLM_MODEL", os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "ms/GPT-5.6-Think-Deeper")
LLM_KEY = os.getenv("VIDEO_LLM_API_KEY", os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "9router-local")
LLM_TIMEOUT = int(os.getenv("VIDEO_LLM_TIMEOUT", "120"))

STYLES = {
    "remotion_editorial": {"id":"remotion_editorial","name":"Remotion Editorial","description":"Diagram editorial dengan timeline frame, caption pendek dan warna brand."},
    "opuscar_cinematic": {"id": "opuscar_cinematic", "name": "Opuscar Cinematic", "description": "Motion graphics dengan objek mekanis terarah dan pemeriksaan style frames sebelum render."},
    "threejs_3d": {"id": "threejs_3d", "name": "Three.js 3D Cinematic", "description": "Objek mekanis 3D per adegan, material logam, kamera terkontrol dan transisi objek."},
    "lottie_motion": {"id": "lottie_motion", "name": "Lottie Motion", "description": "Animasi vektor ringan dengan preview web dan ekspor lottie.json."},
    "continuous_motion": {"id":"continuous_motion","name":"Continuous Motion","description":"Diagram kontinu dengan pilihan konsep, hold dan carrier berlanjut."},
}
ASPECT_RATIOS = {
    "9:16": {"id": "9:16", "width": 1080, "height": 1920, "label": "9:16 Vertikal"},
    "16:9": {"id": "16:9", "width": 1920, "height": 1080, "label": "16:9 Horizontal"},
    "4:5": {"id": "4:5", "width": 1080, "height": 1350, "label": "4:5 Portrait"},
    "1:1": {"id": "1:1", "width": 1080, "height": 1080, "label": "1:1 Persegi"},
}
DURATIONS = [15, 30, 45, 60, 90]
ENGINES = {
    "opuscar": {"id": "opuscar", "name": "Opuscar / GSAP", "description": "Motion graphics prosedural kaya animasi & ilustrasi dinamis (MP4).", "defaultStyle": "opuscar_cinematic", "output": "mp4"},
    "threejs": {"id": "threejs", "name": "Three.js 3D", "description": "Dunia 3D prosedural WebGL dinamis dengan pencahayaan dan kamera orbit (MP4).", "defaultStyle": "threejs_3d", "output": "mp4"},
    "lottie": {"id": "lottie", "name": "Lottie", "description": "Animasi vektor ringan dengan preview web dan JSON.", "defaultStyle": "lottie_motion", "output": "lottie"},
    "continuous": {"id":"continuous","name":"Continuous Motion","description":"Diagram satu dunia dengan carrier berlanjut, jeda gerak, dan MP4 lokal tanpa CDN.","defaultStyle":"continuous_motion","output":"mp4"},
    "remotion": {"id":"remotion","name":"Remotion Editorial","description":"Diagram editorial lokal, caption per potongan teks dan render MP4 berbasis frame.","defaultStyle":"remotion_editorial","output":"mp4"},
}
DEFAULT_MODELS = [
    {"id": "ag/gemini-3.8-flash-high", "name": "Gemini 3.8 Flash High", "provider": "Gemini", "tier": "utama"},
    {"id": "ag/gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash Medium", "provider": "Gemini", "tier": "utama"},
    {"id": "ms/GPT-5.6-Think-Deeper", "name": "GPT-5.6 Think Deeper", "provider": "GPT", "tier": "utama"},
    {"id": "cc/claude-opus-5-5", "name": "Claude Opus 5.5", "provider": "Claude", "tier": "tambahan"},
    {"id": "cc/claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "provider": "Claude", "tier": "tambahan"},
]
ALLOWED_MODEL_IDS = {item["id"] for item in DEFAULT_MODELS}
JOBS_LOCK = threading.Lock()
JOB_DIR = VIDEOS_DIR / ".jobs"
MAX_PLAN_SECONDS = 600
MAX_SCENES = 200
JOBS: dict[str, dict] = recover_jobs(JOB_DIR)
TIMECODE_RE = re.compile(r"(?m)^\s*(?P<start>\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*(?:-->|-|–|—)\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*[:|]?\s*(?P<body>.*?)(?=^\s*(?:\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?)\s*(?:-->|-|–|—)|\Z)", re.S)
FIELD_RE = re.compile(r"(?im)^\s*(narasi|narration|visual|teks(?: layar)?|on.?screen|suara|sound|sfx|tipe|type)\s*:\s*(.+)$")


def get_available_models() -> list[dict]:
    return list(DEFAULT_MODELS)


def options() -> dict:
    default_model = LLM_MODEL if LLM_MODEL in ALLOWED_MODEL_IDS else "ag/gemini-3.8-flash-high"
    research_ready = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")) and PODCASTFY_PYTHON.is_file()
    return {"engines": [{**engine,"runtimeMissing":runtime_issues(engine['id'])} for engine in ENGINES.values()], "motionConcepts":continuous_motion.CONCEPTS, "templates":video_templates.catalogue(), "styles": list(STYLES.values()), "aspects": list(ASPECT_RATIOS.values()), "durations": DURATIONS, "models": get_available_models(), "defaultEngine": "opuscar", "defaultStyle": "opuscar_cinematic", "defaultAspect": "9:16", "defaultDuration": 60, "frameRates":list(frame_rate.RATES), "defaultFps":frame_rate.DEFAULT, "defaultModel": default_model, "workflow": ["brief", "research", "narration", "scene_plan", "storyboard", "render"], "research": {"provider": "Google Search grounding", "model": RESEARCH_MODEL, "required": False, "requiredForModes":["web"], "ready": research_ready,"modes":["planner","web","provided"]}}


def runtime_issues(engine: str) -> list[str]:
    if engine=='remotion':return remotion_adapter.runtime_issues()
    if engine=='lottie':return []
    if engine=='continuous':return continuous_motion.runtime_issues()
    missing=[]
    if not shutil.which('node'):missing.append('Node.js')
    if not shutil.which('ffmpeg') and not (ROOT/'bin'/'ffmpeg.exe').is_file():missing.append('FFmpeg')
    if not (HYPERFRAMES_APP_DIR/'node_modules'/'hyperframes'/'bin'/'hyperframes.mjs').is_file():missing.append('HyperFrames renderer')
    if not resolve_python(OPUSCAR_DIR).is_file():missing.append('Opuscar voice environment')
    if not (OPUSCAR_DIR/'core'/'tts'/'tts_zh.py').is_file():missing.append('Opuscar TTS worker')
    return missing


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
    if len(chunks)>count:
        chunks=[" ".join(chunks[i*len(chunks)//count:(i+1)*len(chunks)//count]) for i in range(count)]
    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total = sum(weights)
    cursor = 0.0
    scenes = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        end = float(duration) if index == len(chunks) - 1 else round(cursor + duration * weight / total, 3)
        scenes.append({"start": cursor, "end": end, "duration": end - cursor, "narration": chunk, "visual": "", "onScreenText": chunk[:80], "soundCue": "", "type": _scene_type(chunk)})
        cursor = end
    return scenes


def _visual_family(text: str, scene_type: str, index: int = 0) -> str:
    """Choose visual form from concrete scene nouns, not from the film topic.

    Matches are scored instead of returning the first broad keyword. This prevents
    a word such as "cyber" or "AI" from turning an entire film into one network
    diagram. Scene type is only a fallback when the scene has no drawable noun.
    """
    value = f" {text.lower()} "
    vocab = {
        "cityscape": ((" kota digital ", 5), (" cityscape ", 5), (" gedung ", 3), (" skyline ", 4), (" pusat operasi ", 4)),
        "balance": ((" timbangan ", 6), (" seimbang ", 4), (" keseimbangan ", 5), (" balance ", 5), (" governance ", 2)),
        "network": ((" jaringan ", 4), (" network ", 4), (" node ", 4), (" server ", 4), (" attack path ", 6), (" koneksi ", 4), (" lateral ", 3), (" perimeter ", 3)),
        "journey": ((" perjalanan ", 4), (" journey ", 4), (" route ", 4), (" rute ", 4), (" jalur ", 3), (" aliran ", 3), (" flow ", 3), (" bergerak ", 1), (" menyebar ", 1), (" menuju ", 1)),
        "device": ((" perangkat ", 4), (" device ", 4), (" mesin ", 3), (" hardware ", 4), (" robot ", 4), (" chip ", 4), (" inti ", 2), (" agen ai ", 3), (" perisai ", 4)),
        "nature": ((" alam ", 4), (" hutan ", 4), (" forest ", 4), (" laut ", 4), (" ocean ", 4), (" sungai ", 4), (" water ", 3), (" iklim ", 3), (" pohon ", 4), (" landscape ", 4)),
        "people": ((" manusia ", 3), (" analis ", 4), (" orang ", 3), (" people ", 3), (" tim ", 3), (" team ", 3), (" komunitas ", 4), (" pengguna ", 3), (" pelanggan ", 3), (" worker ", 3)),
        "evidence": ((" dokumen ", 4), (" bukti ", 4), (" evidence ", 4), (" audit ", 4), (" laporan ", 4), (" report ", 4), (" arsip ", 4), (" timeline ", 3), (" log ", 3), (" keputusan ", 2), (" temuan ", 2)),
        "interface": ((" aplikasi ", 4), (" app ", 3), (" software ", 3), (" ui ", 4), (" interface ", 4), (" dashboard ", 5), (" cursor ", 4), (" window ", 3), (" panel ", 3), (" alert ", 3), (" policy gate ", 5), (" kill switch ", 5)),
        "comparison": ((" versus ", 4), (" vs ", 4), (" dibanding ", 4), (" layar terbagi ", 5), (" split ", 4), (" sisi kiri ", 4), (" sisi kanan ", 4)),
        "data": ((" persen ", 4), (" statistik ", 4), (" metric ", 4), (" angka ", 3), (" grafik ", 4), (" chart ", 4), (" total ", 2)),
        "signal": ((" siap ", 3), (" mulai ", 2), (" sekarang ", 2), (" call to action ", 5), (" simbol kesiapan ", 5)),
        "portal": ((" memasuki ", 3), (" gerbang ", 5), (" tunnel ", 5), (" ruang simulasi ", 6), (" lingkungan simulasi ", 6)),
    }
    scores = {family: sum(value.count(token) * weight for token, weight in tokens) for family, tokens in vocab.items()}
    best_score = max(scores.values(), default=0)
    if best_score:
        candidates = sorted(family for family, score in scores.items() if score == best_score)
        return candidates[index % len(candidates)]
    fallback = {"data": "data", "comparison": "comparison", "call-to-action": "signal"}.get(scene_type)
    if fallback:
        return fallback
    return ("constellation", "portal", "kinetic-type")[sum(ord(c) for c in value) % 3]


def _motion_for(scene_type: str, index: int, family: str = "") -> dict:
    camera_by_family = {
        "network": "target-lock push-in", "journey": "lateral route follow",
        "device": "three-quarter orbit", "nature": "slow crane reveal",
        "people": "pull-back accumulation", "evidence": "document track and focus",
        "interface": "snap-grid zoom", "data": "locked accumulation",
        "comparison": "split converge", "signal": "iris pull-back",
        "constellation": "drifting parallax", "portal": "tunnel push-through",
        "kinetic-type": "planar whip", "cityscape": "dive through skyline",
        "balance": "locked symmetrical reveal",
    }
    transitions = {
        "network": "scan", "journey": "route-wipe", "device": "explode-collapse",
        "nature": "light-sweep", "people": "icon-cascade", "evidence": "document-slide",
        "interface": "ui-expand", "data": "mark-morph", "comparison": "split-wipe",
        "signal": "iris", "constellation": "particle-gather", "portal": "tunnel",
        "kinetic-type": "type-reflow", "cityscape": "depth-wipe",
        "balance": "fulcrum-match",
    }
    return {
        "direction": camera_by_family.get(family, "establish-focus-reveal"),
        "easing": "power3.out" if index == 0 else "power2.inOut",
        "transition": transitions.get(family, "shape-morph"),
        "emphasis": "hook" if index == 0 else "payoff",
    }


def normalize_scene_plan(data: dict, topic: str, script: str, duration: int) -> dict:
    if not isinstance(data,dict) or not math.isfinite(float(duration)) or not 0<duration<=MAX_PLAN_SECONDS:
        raise ValueError('Durasi rencana harus 0–600 detik')
    explicit = parse_explicit_scenes(script)
    source = explicit or (data.get("scenes") if isinstance(data.get("scenes"), list) else [])
    if not source: source = proportional_scenes(topic, script, duration)
    if len(source)>MAX_SCENES or any(not isinstance(raw,dict) for raw in source):raise ValueError('Rencana maksimal 200 adegan berbentuk objek')
    scenes = []
    for index, raw in enumerate(source):
        narration = str(raw.get("narration") or raw.get("script") or "").strip()
        try:
            start = float(raw.get("start", 0))
            end = float(raw["end"]) if 'end' in raw else start+float(raw.get('duration',0))
        except (TypeError,ValueError,OverflowError):raise ValueError('Waktu adegan harus numerik') from None
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end>MAX_PLAN_SECONDS:
            raise ValueError('Waktu adegan harus angka terbatas dalam 0–600 detik')
        visual = str(raw.get("visual") or "")
        scene_type = str(raw.get("type") or _scene_type(" ".join((narration, visual))))
        # Deliberately exclude the global topic. A cyber-security film can contain
        # a city, a person, a document, an interface and a network in successive
        # shots; the title must not force every shot into the network family.
        raw_subject = str(raw.get("subject") or "").strip()
        # Older plans sometimes copied the complete production direction into
        # subject. Treat long sentences and exact visual copies as instructions,
        # never as drawable labels.
        subject = raw_subject
        if subject == visual or len(subject) > 48 or subject.count(" ") > 6 or any(mark in subject for mark in (".", ":", ";")):
            subject = ""
        semantic_text = " ".join((visual, narration, subject, str(raw.get("setting") or ""), str(raw.get("metaphor") or ""), str(raw.get("onScreenText") or "")))
        family = str(raw.get("visualFamily") or _visual_family(semantic_text, scene_type, index))
        motion = _motion_for(scene_type, index, family)
        # Old plans contain generic v2 motion. Preserve only explicit directorial
        # fields; regenerate generic direction/transition from the chosen family.
        old_motion = raw.get("motion")
        if isinstance(old_motion, dict) and raw.get("visualFamily"):
            motion.update(old_motion)
        scenes.append({
            "id": f"scene-{index + 1}", "start": start, "end": end, "duration": end - start,
            "narration": narration, "visual": visual, "onScreenText": str(raw.get("onScreenText") or raw.get("text") or narration[:80]),
            "soundCue": str(raw.get("soundCue") or raw.get("sound") or ""), "type": scene_type,
            "visualFamily": family, "subject": subject,
            "directionSubject": str(raw.get("directionSubject") or raw_subject),
            "continuityToken": str(raw.get("continuityToken") or ""),
            "action": str(raw.get("action") or motion["direction"]), "setting": str(raw.get("setting") or ""),
            "metaphor": str(raw.get("metaphor") or ""), "camera": str(raw.get("camera") or motion["direction"]),
            "transition": str(raw.get("transition") or motion["transition"]), "colorMood": str(raw.get("colorMood") or "adaptive"),
            "shotPurpose": str(raw.get("shotPurpose") or ("hook" if index == 0 else "develop")),
            "composition": str(raw.get("composition") or "clear hierarchy with protected title and subtitle safe areas"),
            "foreground": str(raw.get("foreground") or ""), "midground": str(raw.get("midground") or visual),
            "background": str(raw.get("background") or raw.get("setting") or ""),
            "lighting": str(raw.get("lighting") or "motivated cinematic lighting"),
            "typography": str(raw.get("typography") or "concise high-contrast editorial title"),
            "continuity": str(raw.get("continuity") or "carry color, direction, or shape from the previous shot"),
            "motion": motion,
        })
    source_has_timing = bool(source) and all(
        isinstance(item, dict) and "start" in item and ("end" in item or "duration" in item)
        for item in source
    )
    if explicit:
        duration = int(math.ceil(max(scene["end"] for scene in scenes)))
    elif source_has_timing:
        previous_end = 0.0
        for scene in scenes:
            if scene["start"] < previous_end or scene["end"] <= scene["start"]:
                raise ValueError("Timecode scene hasil edit tidak valid atau tumpang tindih")
            previous_end = scene["end"]
        duration = max(duration, int(math.ceil(scenes[-1]["end"])))
    elif scenes:
        weights = [max(1, len(scene["narration"].split())) for scene in scenes]
        cursor = 0.0
        for index, scene in enumerate(scenes):
            end = float(duration) if index == len(scenes) - 1 else round(cursor + duration * weights[index] / sum(weights), 3)
            scene.update(start=cursor, end=end, duration=end - cursor)
            cursor = end
    for scene,raw in zip(scenes,source):
        creative_profile.timing(scene,raw)
        if 'diagram' in raw:scene['diagram']=scene_diagram.validate(raw['diagram'])
        if 'renderControls' in raw:scene['renderControls']=scene_render.validate(raw['renderControls'])
    result={"topic": topic, "duration": duration, "scenes": scenes}
    if "fps" in data:result["fps"]=frame_rate.validate(data["fps"])
    if data.get("templateId"):result["templateId"]=video_templates.get(data["templateId"])["id"]
    if "speech" in data:result["speech"]=speech_settings.validate(data["speech"])
    if 'creativeBrief' in data:
        if not isinstance(data['creativeBrief'],str) or len(data['creativeBrief'])>4000:raise ValueError('Arahan produksi maksimal 4.000 karakter')
        result['creativeBrief']=data['creativeBrief']
    if 'audioMode' in data:
        if data['audioMode'] not in ('music','tts','none'):raise ValueError('Audio harus music atau tts')
        result['audioMode']=data['audioMode']
    if data.get('brand') is not None:result['brand']=creative_profile.snapshot(data['brand'])
    if data.get('creativeDirection') is not None:
        direction=data['creativeDirection']
        if not isinstance(direction,dict) or len(json.dumps(direction,allow_nan=False).encode('utf-8'))>16000:
            raise ValueError('Creative direction harus objek JSON maksimal 16 KB')
        result['creativeDirection']=copy.deepcopy(direction)
    if data.get('motionDesign') is not None:
        result['motionDesign']=continuous_motion.design({**data['motionDesign'],'fps':frame_rate.get(result)},scenes,duration)
        if result.get('speech'):result['motionDesign']['voiceMode']=result['speech']['mode']
        result['motionBeatSheet']=continuous_motion.beat_sheet(result)
    if result.get('speech') and 'audioMode' in result:result['audioMode']=result['speech']['mode']
    return result


def build_scene_prompt(topic: str, script: str, duration: int, aspect: str) -> str:
    input_material = script.strip() or "Tidak ada naskah. Kembangkan treatment orisinal hanya dari judul, tanpa membuat data, kutipan, nama lembaga, hasil riset, atau klaim faktual spesifik yang tidak diberikan."
    return f"""Bertindak sebagai creative director, sutradara motion design, penulis narasi, editor, sound designer, dan storyboard artist senior. Hasil harus langsung dapat dipakai tim produksi, bukan outline generik dan bukan kumpulan slide.

TUJUAN FILM
- Bangun satu ide utama yang jelas, hook yang terbaca dalam 1-2 detik, eskalasi informasi, turning point, dan payoff/CTA yang memperoleh ruang bernapas.
- Gunakan perubahan visual bermakna setiap 2-5 detik sesuai kepadatan narasi, tetapi hindari potongan acak. Setiap shot wajib meneruskan bentuk, arah gerak, warna, objek, atau gagasan dari shot sebelumnya.
- Buat narasi ringkas, natural, mudah diucapkan, dan sesuai durasi. Jangan memenuhi seluruh durasi dengan suara; sisakan jeda untuk penekanan visual.
- Jika hanya ada judul, kembangkan treatment edukatif atau konseptual yang aman. Jangan mengarang statistik, tanggal, kutipan, hasil riset, merek, atau klaim absolut.
- Jika pengguna memberi naskah, fakta, angka, ejaan, urutan, negasi, dan timecode wajib dipertahankan.

ARAH VISUAL
- Film harus menunjukkan objek konkret dan aksi yang dapat dianimasikan. Hindari kata abstrak tanpa representasi visual.
- Variasikan establishing, wide, medium, close-up, macro/detail, overhead, tracking, orbit, locked, push-in, pull-back, dan reveal berdasarkan fungsi dramatik, bukan sekadar variasi.
- Untuk setiap shot, rancang foreground, midground, background, focal point, depth, negative space, protected title area, dan subtitle-safe area.
- Gerak kamera harus termotivasi oleh informasi: reveal, follow, compare, inspect, transition, atau payoff. Hindari gerakan kamera dekoratif.
- Gunakan metafora visual hanya bila memperjelas gagasan. Jangan memakai radar, HUD, neon, network node, grafik, atau objek teknologi kecuali benar-benar relevan.
- Field visual adalah instruksi produksi dan tidak boleh disalin menjadi label layar. subject hanya nama objek pendek apabila objek memang perlu dilabeli.
- Teks layar 2-6 kata, satu gagasan per kartu, kontras tinggi, tidak mengulang narasi secara utuh.

PACING DAN EDITING
- Tentukan start/end yang berurutan, tanpa overlap atau celah tak disengaja, sampai tepat {duration} detik.
- Hook: pola visual kuat dan pertanyaan/konflik yang jelas. Build: informasi berkembang melalui sebab-akibat. Turn: perubahan perspektif. Payoff: kesimpulan visual yang memuaskan.
- Tentukan transition yang berasal dari bentuk, arah, cahaya, kamera, atau aksi di dalam shot. Hindari transisi template tanpa hubungan.
- Sound cue harus spesifik dan hemat: impact, riser, whoosh, click, ambience, tonal hit, atau silence. Jelaskan fungsi audio, bukan hanya nama efek.

Topik/judul: {topic}
Durasi total: {duration} detik
Rasio: {aspect}
Materi pengguna:
{input_material}

Balas satu objek JSON valid saja dengan:
1. creativeDirection: logline, audiencePromise, narrativeArc, visualThesis, pacingArc, paletteLogic, typographySystem, motionLanguage, soundStrategy, continuitySystem, riskChecks.
2. scenes: array berisi start, end, narration, onScreenText, soundCue, type, shotPurpose, visualFamily, subject, action, setting, visual, metaphor, composition, foreground, midground, background, camera, lighting, colorMood, typography, transition, continuity.
Untuk engine opuscar/threejs/remotion saja, renderControls opsional mengendalikan gambar: camera (legacy/locked/push-in/pull-out/pan-left/pan-right/orbit), strength (angka 0–1), lighting (legacy/soft/dramatic), transition (legacy/fade/cut/slide). Kamera 2D hanya mengubah ilustrasi, bukan judul/subtitle. Arahan bebas tetap catatan produksi, bukan kode. Jangan menambahkan kontrol ini pada lottie/continuous. Untuk Remotion/Lottie, diagram opsional {{kind: process|comparison, labels: [teks]}} memakai 2–5 label proses atau tepat 2 label perbandingan, masing-masing maksimal 48 karakter dan berdasarkan naskah. Tanpa diagram eksplisit, tidak ada langkah proses yang dikarang. Remotion mendukung visualFamily process/data/comparison dan concept (keluarga lain menjadi concept), durasi ditutup tanpa gap, judul maksimal 120 karakter; jangan mengarang angka diagram.

Pastikan jumlah scene proporsional terhadap durasi, setiap scene berbeda fungsi dan visualnya, total timing tepat {duration} detik, serta seluruh keputusan cukup detail untuk divisualkan tanpa menebak maksud sutradara."""

def _research_web(topic: str, script: str) -> dict:
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("Web Search wajib aktif. Atur GOOGLE_API_KEY atau GEMINI_API_KEY lalu restart dashboard")
    if not PODCASTFY_PYTHON.is_file():
        raise RuntimeError("Environment Google Search belum tersedia")
    payload = json.dumps({"topic": topic, "context": script, "model": RESEARCH_MODEL}, ensure_ascii=False)
    process = subprocess.run(
        [str(PODCASTFY_PYTHON), str(RESEARCH_WORKER)], input=payload, text=True,
        capture_output=True, timeout=max(LLM_TIMEOUT, 120), env=os.environ.copy(),
    )
    try:
        result = json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Respons Google Search tidak valid") from exc
    if process.returncode or result.get("error"):
        raise RuntimeError(str(result.get("error") or process.stderr or "Google Search gagal"))
    if not result.get("sources"):
        raise RuntimeError("Google Search tidak menghasilkan sumber yang dapat diverifikasi")
    return result


def _research_context(research: dict) -> str:
    sources = "\n".join(
        f"[{item['id']}] {item['title']} | {item['publisher']} | {item['url']}"
        for item in research.get("sources", [])
    )
    return f"RINGKASAN RISET — KLAIM MASIH PERLU REVIEW:\n{research.get('summary', '')}\n\nSUMBER GROUNDING:\n{sources}"


def _call_9router(prompt: str, model: str = "") -> str:
    body = {"model": model or LLM_MODEL, "stream": False, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "Return valid JSON only. Preserve user facts, narration, and explicit timecodes."}, {"role": "user", "content": prompt}]}
    request = urllib.request.Request(f"{LLM_URL}/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}, method="POST")
    with open_authenticated(request, timeout=LLM_TIMEOUT) as response:
        data = json.loads(response.read().decode())
    return data["choices"][0]["message"]["content"]


def _clean_json(raw: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match: raise ValueError("LLM tidak mengembalikan JSON")
    return json.loads(match.group())


def _visual_markup(scene: dict, index: int) -> str:
    directed = opuscar_scene_spec.interpret(scene)
    if directed:
        return opuscar_primitives.markup(directed, index)
    kind = scene["type"]
    family = scene.get("visualFamily") or _visual_family(" ".join((scene.get("visual", ""), scene.get("narration", ""))), kind, index)
    family=renderer_contract.opuscar_family(scene,family)
    # Only an explicit subject may become an internal label. The visual field is
    # production direction and must never be copied or truncated onto the frame.
    explicit_subject = str(scene.get("subject") or "").strip()
    subject = html.escape(explicit_subject[:32]) if explicit_subject else ""
    label = f'<span class="visual-label">{subject}</span>' if subject else ""
    if family == "data":
        # A decorative chart is not evidence. Display only an approved literal
        # metric, preserving its sign, decimal separators and percent suffix.
        metrics=renderer_contract.literal_numbers(scene)
        metric=html.escape(metrics[0]) if metrics else ""
        return f'''<div class="visual-canvas-box data-viz" data-family="data">
            <div class="metric-counter"><span class="num">{metric}</span></div>
        </div>'''
    if family == "unsupported":
        text = html.escape(scene.get("onScreenText", ""))
        return f'<div class="visual-canvas-box editorial-viz" data-family="editorial" data-interpretation="unsupported"><strong>{text}</strong></div>'
    if kind == "call-to-action" or family == "signal":
        return f'''<div class="visual-canvas-box cta-viz family-signal" data-family="signal">
            <div class="prism-gyro"><div class="gyro-ring gr1"></div><div class="gyro-ring gr2"></div><div class="gyro-ring gr3"></div><div class="prism-core">✦</div></div>
            {label}<div class="cta-flare"></div>
        </div>'''
    if family == "network":
        nodes = ''.join(f'<span class="net-node node-{n}"></span>' for n in range(1, 8))
        return f'''<div class="visual-canvas-box network-viz" data-family="network"><svg class="network-links" viewBox="0 0 800 700"><path d="M90 160 L300 90 L430 260 L690 145 M165 530 L350 390 L650 520 M90 160 L165 530 M300 90 L350 390 M430 260 L650 520 L690 145"/></svg>{nodes}<div class="network-core">{subject[:18] if subject else "◆"}</div></div>'''
    if family == "journey":
        return f'''<div class="visual-canvas-box journey-viz" data-family="journey"><svg viewBox="0 0 800 700"><path class="route-path" d="M70 570 C180 390 250 590 370 360 S590 130 730 185"/><circle class="route-stop s1" cx="70" cy="570" r="16"/><circle class="route-stop s2" cx="370" cy="360" r="16"/><circle class="route-stop s3" cx="730" cy="185" r="22"/></svg>{label}</div>'''
    if family == "device":
        return f'''<div class="visual-canvas-box device-viz" data-family="device"><div class="device-shell"><div class="device-layer dl1"></div><div class="device-layer dl2"></div><div class="device-layer dl3"></div><div class="device-core"></div></div>{label}</div>'''
    if family == "nature":
        return f'''<div class="visual-canvas-box nature-viz" data-family="nature"><div class="sun-disc"></div><div class="terrain back"></div><div class="terrain mid"></div><div class="terrain front"></div><div class="nature-flow"></div>{label}</div>'''
    if family == "people":
        people = ''.join(f'<span class="person-icon p{n}"><i></i><b></b></span>' for n in range(1, 10))
        return f'''<div class="visual-canvas-box people-viz" data-family="people"><div class="people-field">{people}</div><div class="community-ring"></div>{label}</div>'''
    if family == "evidence":
        return f'''<div class="visual-canvas-box evidence-viz" data-family="evidence"><div class="document-card doc-back"></div><div class="document-card doc-main"><i></i><i></i><i></i><mark></mark></div><div class="evidence-loupe"></div>{label}</div>'''
    if family == "interface":
        return f'''<div class="visual-canvas-box interface-viz" data-family="interface"><div class="ui-window main-ui"><div class="ui-top"></div><i></i><i></i><i></i></div><div class="ui-window ui-card-a"></div><div class="ui-window ui-card-b"></div><div class="cursor-mark"></div>{label}</div>'''
    if family == "cityscape":
        buildings = ''.join(f'<span class="city-building cb{n}"><i></i><i></i><i></i></span>' for n in range(1, 8))
        return f'''<div class="visual-canvas-box city-viz" data-family="cityscape"><div class="city-glow"></div><div class="city-buildings">{buildings}</div><div class="city-wave"></div>{label}</div>'''
    if family == "balance":
        return f'''<div class="visual-canvas-box balance-viz" data-family="balance"><div class="balance-beam"><span class="balance-pan left-pan"></span><span class="balance-hub"></span><span class="balance-pan right-pan"></span></div><div class="balance-base"></div>{label}</div>'''
    if family == "portal":
        return f'''<div class="visual-canvas-box portal-viz" data-family="portal"><div class="portal-ring pr1"></div><div class="portal-ring pr2"></div><div class="portal-ring pr3"></div><div class="portal-core">{subject[:18]}</div></div>'''
    if family == "kinetic-type":
        words = [html.escape(x) for x in (scene.get("onScreenText") or subject).split()[:5]]
        return f'''<div class="visual-canvas-box kinetic-viz" data-family="kinetic-type">{''.join(f'<strong>{word}</strong>' for word in words)}</div>'''
    return f'<div class="visual-canvas-box editorial-viz" data-family="editorial" data-interpretation="unsupported"><strong>{html.escape(scene.get("onScreenText", ""))}</strong></div>'



def generate_opuscar_composition(plan: dict, aspect_info: dict, model: str = "") -> str:
    width, height, duration = aspect_info["width"], aspect_info["height"], plan["duration"]
    sections, animation = [], []
    for index, scene in enumerate(plan["scenes"]):
        start, length = scene["start"], scene["duration"]
        kind = scene["type"]
        controls=scene_render.validate(scene.get('renderControls',{}))
        family = scene.get("visualFamily") or _visual_family(" ".join((scene.get("visual", ""), scene.get("narration", ""))), kind, index)
        if family not in {'data','process','comparison','signal','network','journey','device','nature','people','evidence','interface','cityscape','balance','portal','kinetic-type','constellation','concept'}:
            family='concept'
        directed = opuscar_scene_spec.interpret(scene)
        if directed: family = "directed"
        layout = ("full-bleed" if family in ("cityscape", "nature") else "split-stage" if family in ("comparison", "balance") else "focus-stage")
        sections.append(f'''<section class="scene clip type-{html.escape(kind)} family-{html.escape(family)} layout-{layout} transition-{html.escape(scene.get("transition", "shape-morph"))}" id="sc_{index}" data-family="{html.escape(family)}" data-start="{start}" data-duration="{length}">
            <div class="scene-inner">
                <div class="chapter-badge"><span class="badge-dot"></span> {index + 1:02d} / {len(plan["scenes"]):02d} · {html.escape(kind.upper())}</div>
                <div class="content-stack">
                    <div class="copy-wrapper"><h2 class="hero-title">{html.escape(scene["onScreenText"])}</h2></div>
                    <div class="visual-wrapper" style="{scene_render.lighting_filter(scene) if not directed else ""}">{_visual_markup(scene, index)}</div>
                </div>
                <div class="subtitle-capsule"><span class="sound-wave"><i></i><i></i><i></i></span><span>{html.escape(scene["narration"])}</span></div>
            </div>
        </section>''')
        if directed:
            # Directed props and camera are sampled from absolute time by the bridge.
            animation.append(f'tl.to({{}}, {{duration:{length}}}, {start});')
            continue
        entrance=scene_render.entrance(scene,f'#sc_{index} .scene-inner') if controls['transition']!='legacy' else f'tl.fromTo("#sc_{index} .scene-inner", {{opacity:0,scale:1.08,filter:"blur(14px)"}}, {{opacity:1,scale:1,filter:"blur(0px)",duration:0.55,ease:"power3.out"}}, {start});'
        drift=scene_render.camera_tween(scene,f'#sc_{index} .visual-canvas-box') if controls['camera']!='legacy' else f'tl.to("#sc_{index} .visual-canvas-box", {{y: {(-10 if family in ("nature","constellation") else 0)}, scale: {1.018 if family in ("device","portal","interface") else 1.0}, duration: Math.max(1.2, {length} * 0.48), yoyo:true, repeat:1, ease:"sine.inOut"}}, {start + 0.35});'
        animation.append(f'''
        {entrance}
        tl.from("#sc_{index} .chapter-badge", {{x: -70, opacity: 0, duration: 0.5, ease: "back.out(1.4)"}}, {start + 0.03});
        tl.from("#sc_{index} .hero-title", {{y: -55, scale: 1.12, opacity: 0, duration: 0.62, ease: "power3.out"}}, {creative_profile.reveal(scene, .06)});
        tl.from("#sc_{index} .visual-wrapper", {{scale: 0.58, rotation: -7, opacity: 0, duration: 0.8, ease: "back.out(1.55)"}}, {creative_profile.reveal(scene, .12)});
        tl.from("#sc_{index} .subtitle-capsule", {{y: 45, opacity: 0, duration: 0.5, ease: "power3.out"}}, {start + 0.18});
        {drift}
        tl.from("#sc_{index} [data-family='{family}'] > *", {{opacity:0, y:{24 if index % 2 == 0 else -24}, stagger:0.07, duration:0.55, ease:"power2.out"}}, {start + 0.22});
        ''')
        if family == "data":
            animation.append(f'''
            tl.from("#sc_{index} .metric-counter", {{scale:0.72,opacity:0,duration:0.55,ease:"back.out(1.5)"}}, {start + 0.2});
            ''')
        if family == "process":
            animation.append(f'''
            tl.from("#sc_{index} .process-node", {{scale: 0.5, opacity: 0, stagger: 0.2, duration: 0.5, ease: "back.out(1.5)"}}, {start + 0.25});
            ''')
        if family == "comparison":
            animation.append(f'''
            tl.from("#sc_{index} .side-left", {{x: -50, opacity: 0, duration: 0.6, ease: "power2.out"}}, {start + 0.2});
            tl.from("#sc_{index} .side-right", {{x: 50, opacity: 0, duration: 0.6, ease: "power2.out"}}, {start + 0.2});
            tl.from("#sc_{index} .vs-divider", {{scale: 0, rotation: 180, duration: 0.5, ease: "back.out(2)"}}, {start + 0.35});
            ''')
        if family == "journey":
            animation.append(f'''tl.fromTo("#sc_{index} .route-path", {{strokeDashoffset:1200}}, {{strokeDashoffset:0,duration:Math.min(2.2,{length}*.65),ease:"power2.inOut"}}, {start + 0.2});''')
        elif family == "device":
            animation.append(f'''tl.from("#sc_{index} .device-layer", {{x:(i)=> (i-1)*-150, rotation:(i)=>(i-1)*-12, stagger:.12,duration:.75,ease:"back.out(1.4)"}}, {start + 0.25});''')
        elif family == "people":
            animation.append(f'''tl.from("#sc_{index} .person-icon", {{scale:0,stagger:.06,duration:.38,ease:"back.out(2)"}}, {start + 0.25});''')
        elif family == "evidence":
            animation.append(f'''tl.from("#sc_{index} .document-card", {{y:120,rotation:-8,stagger:.14,duration:.65,ease:"power3.out"}}, {start + 0.2}); tl.fromTo("#sc_{index} .evidence-loupe", {{x:-170,y:120}}, {{x:40,y:-10,duration:Math.max(1.4,{length}*.55),ease:"power1.inOut"}}, {start + .7});''')
        elif family == "interface":
            animation.append(f'''tl.from("#sc_{index} .ui-window", {{scale:.4,x:120,stagger:.12,duration:.55,ease:"back.out(1.6)"}}, {start + .2});''')
        elif family == "cityscape":
            animation.append(f'''tl.from("#sc_{index} .city-building", {{scaleY:0,transformOrigin:"bottom",stagger:.07,duration:.7,ease:"power3.out"}}, {start + .15}); tl.from("#sc_{index} .city-wave", {{scaleX:0,transformOrigin:"left",duration:1.1,ease:"power2.inOut"}}, {start + .55});''')
        elif family == "balance":
            animation.append(f'''tl.fromTo("#sc_{index} .balance-beam", {{rotation:-14}}, {{rotation:0,duration:Math.max(1.2,{length}*.45),ease:"elastic.out(1,.45)",overwrite:"auto"}}, {start + .2});''')
        elif family in ("constellation", "network"):
            animation.append(f'''tl.from("#sc_{index} .star, #sc_{index} .net-node", {{scale:0,stagger:.08,duration:.4,ease:"back.out(2)"}}, {start + .2});''')
        exit_start = max(start + 0.1, scene['end'] - 0.22)
        animation.append(scene_render.exit_tween(scene,f'#sc_{index} .scene-inner') if controls['transition']!='legacy' else f'''
        tl.to("#sc_{index} .scene-inner", {{opacity:0,scale:1.035,filter:"blur(8px)",duration:0.22,ease:"power2.in"}}, {exit_start});
        ''')

    unit = min(width, height) / 1080
    title = html.escape(plan["topic"])
    return f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><title>{title}</title><style>
*{{box-sizing:border-box}}
html,body{{margin:0;background:#030712;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow:hidden}}
#stage{{width:{width}px;height:{height}px;position:relative;background:#10151d;overflow:hidden}}
.scene{{position:absolute;inset:0;padding:{round(54*unit)}px {round(76*unit)}px {round(80*unit)}px;overflow:hidden}}
.scene-inner{{width:100%;height:100%;position:relative;display:flex;flex-direction:column;align-items:center;gap:{round(16*unit)}px}}
.chapter-badge{{position:relative;z-index:4;align-self:flex-start;display:inline-flex;align-items:center;gap:8px;padding:9px 18px;border-radius:99px;background:rgba(8,47,73,.72);border:1px solid rgba(34,211,238,.48);color:#67e8f9;font-size:{round(18*unit)}px;font-weight:850;letter-spacing:.14em;box-shadow:0 8px 30px rgba(0,0,0,.25)}}
.badge-dot{{width:10px;height:10px;border-radius:50%;background:#22d3ee;box-shadow:0 0 14px #22d3ee}}
.content-stack{{position:relative;z-index:2;flex:1;min-height:0;width:100%;display:grid;grid-template-rows:minmax(0,28%) minmax(0,1fr);gap:{round(16*unit)}px;align-items:stretch}}
.copy-wrapper{{width:100%;min-height:0;text-align:left;display:flex;align-items:center}}
.hero-title{{max-width:920px;font-size:{round(68*unit)}px;line-height:1.04;margin:0;font-weight:950;background:linear-gradient(120deg,#fff 20%,#bae6fd 67%,#38bdf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-shadow:0 12px 42px rgba(0,0,0,.86);letter-spacing:-.035em;text-wrap:balance;overflow-wrap:anywhere}}
.visual-wrapper{{min-height:0;width:100%;display:flex;align-items:center;justify-content:center;padding:6px 0 12px}}
.visual-canvas-box{{transform:translate(0,0);width:100%;height:min(100%,760px);min-height:0;max-height:760px;border-radius:34px;background:#171e29;border:1px solid #334155;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden}}
.visual-canvas-box>div:not(.visual-label),.visual-canvas-box>svg{{max-width:88%;max-height:84%}}
.subtitle-capsule{{position:relative;flex:none;z-index:5;width:100%;max-height:24%;padding:{round(18*unit)}px {round(28*unit)}px;border-radius:{round(22*unit)}px;background:#080f20;border:1px solid #334155;display:flex;align-items:center;gap:{round(18*unit)}px;font-size:{round(30*unit)}px;line-height:1.34;color:#f8fafc;overflow-wrap:anywhere}}
.subtitle-capsule>span:last-child{{min-width:0}}
.sound-wave{{display:flex;gap:4px;align-items:center}}
.sound-wave i{{width:4px;height:22px;background:#22d3ee;border-radius:3px}}
.sound-wave i:nth-child(2){{height:32px}}
.sound-wave i:nth-child(3){{height:16px}}
.data-viz{{flex-direction:column;gap:{round(30*unit)}px;padding:{round(24*unit)}px}}
.metric-counter{{position:relative;z-index:2;font-size:{round(122*unit)}px;font-weight:950;color:#22d3ee;text-shadow:0 0 45px rgba(34,211,238,.7);line-height:1}}
.metric-counter small{{display:block;font-size:16px;color:#94a3b8;letter-spacing:0.18em;margin-top:6px}}
.process-viz{{gap:24px;padding:46px}}
.process-node{{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;gap:14px;flex:1}}
.p-num{{width:118px;height:118px;border-radius:32px;background:linear-gradient(135deg,#0e7490,#0284c7 60%,#7c3aed);border:2px solid #67e8f9;display:grid;place-items:center;font-size:40px;font-weight:950;color:#fff;box-shadow:0 0 38px rgba(34,211,238,.55);transform:rotate(-5deg)}}
.p-line{{width:84px;height:5px;background:rgba(34,211,238,.28);position:relative;overflow:hidden}}
.p-pulse{{position:absolute;width:25px;height:100%;background:#22d3ee;box-shadow:0 0 10px #22d3ee;animation:pulseLine 1.5s infinite}}
@keyframes pulseLine{{0%{{left:-30px}}100%{{left:60px}}}}
.compare-viz{{gap:34px;padding:42px}}
.compare-side{{display:flex;flex-direction:column;align-items:center;gap:12px;width:38%}}
.orb-core{{width:210px;height:210px;border-radius:50%;box-shadow:0 0 55px rgba(34,211,238,.65);animation:orbBreathe 1.8s ease-in-out infinite alternate}}@keyframes orbBreathe{{to{{transform:scale(1.1);filter:brightness(1.22)}}}}
.left-orb{{background:radial-gradient(circle at 35% 35%,#64748b,#1e293b);border:2px solid #94a3b8}}
.right-orb{{background:radial-gradient(circle at 35% 35%,#22d3ee,#7c3aed);border:3px solid #38bdf8;box-shadow:0 0 60px rgba(34,211,238,0.8)}}
.status-chip{{padding:6px 14px;border-radius:99px;font-size:15px;font-weight:800}}
.chip-down{{background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.4)}}
.chip-up{{background:rgba(34,211,238,0.15);color:#22d3ee;border:1px solid rgba(34,211,238,0.4)}}
.vs-divider{{position:relative;display:grid;place-items:center;width:70px;height:70px;border-radius:50%;background:#090d16;border:2px solid #8b5cf6;box-shadow:0 0 30px #8b5cf6}}
.vs-text{{font-size:26px;font-weight:900;color:#c084fc}}
.cta-viz{{position:relative}}
.prism-gyro{{position:relative;width:470px;height:470px;display:grid;place-items:center}}
.gyro-ring{{position:absolute;border-radius:50%;border:2px solid #f59e0b;box-shadow:0 0 35px rgba(245,158,11,0.5)}}
.gr1{{width:100%;height:100%;animation:spinSlow 8s linear infinite}}
.gr2{{width:75%;height:75%;border-color:#22d3ee;animation:spinRev 6s linear infinite}}
.gr3{{width:50%;height:50%;border-color:#a855f7;animation:spinSlow 4s linear infinite}}
.prism-core{{font-size:80px;color:#fbbf24;filter:drop-shadow(0 0 35px #f59e0b)}}
@keyframes spinSlow{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}
@keyframes spinRev{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(-360deg)}}}}
.visual-label{{position:absolute;left:36px;bottom:28px;z-index:5;max-width:82%;padding:9px 14px;border-left:3px solid #22d3ee;background:rgba(2,6,23,.72);font-size:18px;font-weight:700;color:#bae6fd;text-transform:uppercase;letter-spacing:.08em}}
.network-links,.constellation-viz svg,.journey-viz svg{{position:absolute;inset:5%;width:90%;height:90%;fill:none;stroke:#22d3ee;stroke-width:4;opacity:.55}}.net-node,.star{{position:absolute;width:22px;height:22px;border-radius:50%;background:#67e8f9;box-shadow:0 0 24px #22d3ee;z-index:2}}.node-1,.st1{{left:12%;top:20%}}.node-2,.st2{{left:35%;top:12%}}.node-3,.st3{{left:52%;top:35%}}.node-4,.st4{{right:13%;top:20%}}.node-5,.st5{{right:20%;bottom:20%}}.node-6{{left:40%;bottom:18%}}.node-7{{left:15%;bottom:20%}}.network-core,.constellation-core,.portal-core{{position:relative;z-index:3;padding:22px 28px;border-radius:22px;background:#06182b;border:2px solid #22d3ee;font-size:24px;font-weight:900;text-align:center;box-shadow:0 0 45px #0891b255;text-transform:uppercase}}
.route-path{{stroke:#38bdf8;stroke-width:12;stroke-linecap:round;stroke-dasharray:1200}}.route-stop{{fill:#f59e0b;stroke:#fef3c7;stroke-width:6}}.route-subject{{position:absolute;right:12%;top:13%;max-width:60%;font-size:28px;font-weight:900;text-align:right;text-transform:uppercase}}
.device-shell{{position:relative;width:470px;height:470px;transform:rotateX(58deg) rotateZ(-35deg);transform-style:preserve-3d}}.device-layer{{position:absolute;inset:55px;border-radius:48px;border:3px solid #67e8f9;background:linear-gradient(145deg,#0e7490aa,#312e81bb);box-shadow:0 0 35px #22d3ee55}}.dl1{{transform:translateZ(-100px)}}.dl2{{transform:translateZ(0)}}.dl3{{transform:translateZ(100px)}}.device-core{{position:absolute;inset:160px;border-radius:24px;background:#f59e0b;transform:translateZ(145px);box-shadow:0 0 45px #f59e0b}}
.nature-viz{{background:linear-gradient(#0c4a6e 0 38%,#082f49 65%,#020617)}}.sun-disc{{position:absolute;width:190px;height:190px;border-radius:50%;right:13%;top:12%;background:#fde68a;box-shadow:0 0 80px #f59e0b99}}.terrain{{position:absolute;left:-8%;right:-8%;bottom:0;border-radius:50% 50% 0 0}}.terrain.back{{height:56%;background:#155e75;clip-path:polygon(0 55%,22% 15%,42% 62%,63% 8%,100% 60%,100% 100%,0 100%)}}.terrain.mid{{height:42%;background:#166534;clip-path:polygon(0 54%,25% 12%,50% 62%,74% 18%,100% 52%,100% 100%,0 100%)}}.terrain.front{{height:27%;background:#052e16}}.nature-flow{{position:absolute;width:65%;height:16px;left:20%;bottom:24%;background:#38bdf8;border-radius:50%;transform:rotate(-8deg);box-shadow:0 0 28px #38bdf8}}
.people-field{{display:grid;grid-template-columns:repeat(3,120px);gap:42px;z-index:2}}.person-icon{{position:relative;width:100px;height:125px;display:block}}.person-icon i{{position:absolute;width:48px;height:48px;border-radius:50%;left:26px;background:#67e8f9}}.person-icon b{{position:absolute;width:82px;height:68px;left:9px;bottom:0;border-radius:42px 42px 15px 15px;background:linear-gradient(#0ea5e9,#7c3aed)}}.community-ring{{position:absolute;width:620px;height:620px;border:3px dashed #22d3ee55;border-radius:50%}}
.document-card{{position:absolute;width:430px;height:560px;border-radius:12px;background:#e2e8f0;box-shadow:0 25px 60px #0009}}.doc-back{{transform:translate(60px,-35px) rotate(8deg);background:#94a3b8}}.doc-main{{transform:translate(-45px,20px) rotate(-4deg);padding:65px 48px}}.doc-main i{{display:block;height:14px;margin:25px 0;background:#334155;border-radius:8px}}.doc-main mark{{display:block;width:72%;height:55px;margin-top:55px;background:#f59e0b88}}.evidence-loupe{{position:absolute;width:190px;height:190px;border:16px solid #22d3ee;border-radius:50%;box-shadow:0 0 40px #22d3ee88}}.evidence-loupe:after{{content:"";position:absolute;width:120px;height:20px;background:#22d3ee;right:-95px;bottom:-45px;transform:rotate(45deg)}}
.ui-window{{position:absolute;border:2px solid #38bdf866;background:#0f172acc;border-radius:25px;box-shadow:0 25px 60px #0008}}.main-ui{{width:620px;height:410px;padding:70px 45px}}.ui-top{{position:absolute;left:0;right:0;top:0;height:55px;border-bottom:1px solid #38bdf855}}.main-ui i{{display:block;height:26px;margin:26px 0;border-radius:9px;background:linear-gradient(90deg,#22d3ee 35%,#1e293b 35%)}}.ui-card-a{{width:240px;height:150px;right:55px;top:70px;transform:rotate(7deg)}}.ui-card-b{{width:210px;height:125px;left:60px;bottom:75px;transform:rotate(-8deg)}}.cursor-mark{{position:absolute;width:0;height:0;border-left:28px solid #f59e0b;border-top:20px solid transparent;border-bottom:20px solid transparent;transform:rotate(35deg) translate(110px,-80px)}}
.portal-ring{{position:absolute;border-radius:50%;border:4px solid #22d3ee;box-shadow:0 0 45px #22d3ee88;animation:spinSlow 8s linear infinite}}.pr1{{width:580px;height:580px}}.pr2{{width:420px;height:420px;border-color:#a855f7;animation-direction:reverse}}.pr3{{width:260px;height:260px;border-color:#f59e0b}}.kinetic-viz{{flex-wrap:wrap;align-content:center;gap:18px;padding:70px}}.kinetic-viz strong{{font-size:72px;line-height:.92;padding:8px 16px;background:#e2e8f0;color:#020617;transform:rotate(-3deg)}}.kinetic-viz strong:nth-child(even){{background:#22d3ee;transform:rotate(4deg)}}
.city-viz{{align-items:flex-end;background:radial-gradient(circle at 70% 20%,#0e749055,transparent 35%),linear-gradient(#020617,#082f49)}}.city-buildings{{height:72%;width:92%;display:flex;align-items:flex-end;justify-content:center;gap:16px;z-index:2}}.city-building{{position:relative;width:11%;height:var(--h,55%);background:linear-gradient(110deg,#0f172a,#155e75);border-top:2px solid #67e8f9;box-shadow:0 0 25px #22d3ee33}}.city-building:nth-child(2n){{--h:82%}}.city-building:nth-child(3n){{--h:66%}}.city-building i{{display:block;width:42%;height:5px;margin:24px auto;background:#f59e0b;box-shadow:0 0 12px #f59e0b}}.city-wave{{position:absolute;left:4%;bottom:31%;width:92%;height:14px;background:linear-gradient(90deg,#ef4444,#f59e0b,#22d3ee);clip-path:polygon(0 45%,12% 10%,24% 75%,38% 20%,52% 80%,68% 15%,82% 68%,100% 30%,100% 70%,82% 100%,68% 48%,52% 100%,38% 52%,24% 100%,12% 40%,0 75%);filter:drop-shadow(0 0 14px #ef4444)}}
.balance-viz{{flex-direction:column}}.balance-beam{{position:relative;width:70%;height:16px;background:#67e8f9;border-radius:8px;transform-origin:center;box-shadow:0 0 25px #22d3ee}}.balance-hub{{position:absolute;width:76px;height:76px;border-radius:50%;background:#f59e0b;left:50%;top:50%;transform:translate(-50%,-50%);box-shadow:0 0 25px #f59e0b}}.balance-pan{{position:absolute;width:190px;height:190px;border:8px solid #38bdf8;border-radius:50%;top:-87px;background:#0f172a}}.left-pan{{left:-45px}}.right-pan{{right:-45px;border-color:#a855f7}}.balance-base{{width:0;height:0;border-left:100px solid transparent;border-right:100px solid transparent;border-bottom:280px solid #155e75;margin-top:-5px}}.layout-full-bleed .visual-canvas-box{{border-radius:18px}}.layout-split-stage .visual-canvas-box{{background:linear-gradient(90deg,rgba(8,47,73,.8),rgba(3,7,18,.96))}}
.editorial-viz{{padding:10%;font-size:{round(44*unit)}px;text-align:center;overflow-wrap:anywhere}}
{opuscar_primitives.CSS}
</style></head><body>
<div id="stage" data-composition-id="video" data-fps="{frame_rate.get(plan)}" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}">
    {''.join(sections)}
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js"></script>
    <script>
    function fitText(element, maxHeight, maxLines) {{
        const initial = parseFloat(getComputedStyle(element).fontSize);
        let size = initial;
        for (; size > 1; size -= 1) {{
            element.style.fontSize = size + 'px';
            const lineHeight = parseFloat(getComputedStyle(element).lineHeight);
            if (element.scrollWidth <= element.clientWidth + 1 &&
                element.scrollHeight <= Math.min(maxHeight, lineHeight * maxLines) + 1) break;
        }}
        element.dataset.fittedFontSize = size;
    }}
    function fitSceneText() {{
        for (const scene of document.querySelectorAll('.scene')) {{
            // A hidden scene measures as zero-sized: fit only after its timeline reveals it.
            if (getComputedStyle(scene).display === 'none') continue;
            const title = scene.querySelector('.hero-title');
            fitText(title, title.parentElement.clientHeight, 3);
            const capsule = scene.querySelector('.subtitle-capsule');
            const style = getComputedStyle(capsule);
            const available = scene.querySelector('.scene-inner').clientHeight * .24 -
                parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - 2;
            fitText(capsule.lastElementChild, available, 5);
            const metric = scene.querySelector('.metric-counter');
            if (metric) fitText(metric, metric.parentElement.clientHeight * .8, 1);
        }}
    }}
    fitSceneText();
    document.fonts.ready.then(fitSceneText);
    const tl = gsap.timeline({{paused: true}});
    {''.join(animation)}
    window.__timelines = window.__timelines || {{}};
    window.__timelines.video = tl;
    {(Path(__file__).with_name('opuscar_actions.js')).read_text(encoding='utf-8')}
    const drawDirectedScenes = createDirectedRenderer();
    {animation_clock.SCRIPT}
    attachAnimationClock(tl, drawDirectedScenes, {duration});
    // GSAP hides scenes during initial font measurement. Refit AFTER every deterministic seek.
    const seekBeforeTextFit = window.__seek;
    window.__seek = function(seconds) {{
        const result = seekBeforeTextFit(seconds);
        fitSceneText();
        return result;
    }};
    window.render = window.__seek;
    </script>
</div>
</body></html>'''


def generate_threejs_composition(plan: dict, aspect_info: dict, model: str = "") -> str:
    width, height, duration = aspect_info["width"], aspect_info["height"], plan["duration"]
    sections, animation = [], []
    for index, scene in enumerate(plan["scenes"]):
        start, length = scene["start"], scene["duration"]
        kind = scene["type"]
        controls=scene_render.validate(scene.get('renderControls',{}))
        entrance=scene_render.entrance(scene,f'#th_sc_{index}',True) if controls['transition']!='legacy' else f'tl.to("#th_sc_{index}", {{opacity:1, duration: 0.45, ease: "power2.out"}}, {start});'
        exit_animation=scene_render.exit_tween(scene,f'#th_sc_{index}') if controls['transition']!='legacy' else f'tl.to("#th_sc_{index}", {{opacity: 0, scale: 1.05, duration: 0.35, ease: "power2.in"}}, {max(start + 0.1, scene["end"] - 0.35)});'
        sections.append(f'''<section class="scene-hud" id="th_sc_{index}" data-start="{start}" data-duration="{length}">
            <div class="chapter-badge"><span class="badge-dot"></span> TAHAP {index + 1:02d} / {len(plan["scenes"]):02d} · 3D {html.escape(kind.upper())}</div>
            <div class="hud-center">
                <div class="reticle-box">
                    <span class="hud-corner tl"></span><span class="hud-corner tr"></span>
                    <span class="hud-corner bl"></span><span class="hud-corner br"></span>
                    <h2 class="hero-title">{html.escape(scene["onScreenText"])}</h2>
                </div>
            </div>
            <div class="subtitle-capsule"><span class="sound-wave"><i></i><i></i><i></i></span><span>{html.escape(scene["narration"])}</span></div>
        </section>''')
        animation.append(f'''
        tl.set("#th_sc_{index}", {{display:"flex", opacity:0}}, {start});
        {entrance}
        tl.from("#th_sc_{index} .chapter-badge", {{y: -25, opacity: 0, duration: 0.5, ease: "back.out(1.4)"}}, {start + 0.05});
        tl.from("#th_sc_{index} .reticle-box", {{scale: 0.78, opacity: 0, duration: 0.6, ease: "back.out(1.5)"}}, {creative_profile.reveal(scene, .1)});
        tl.from("#th_sc_{index} .subtitle-capsule", {{y: 25, opacity: 0, duration: 0.45, ease: "power2.out"}}, {start + 0.2});
        {exit_animation}
        tl.set("#th_sc_{index}", {{display: "none"}}, {scene['end']});
        ''')

    shot_controls=json.dumps([{'start':shot['start'],'end':shot['end'],'controls':scene_render.validate(shot.get('renderControls',{}))} for shot in plan['scenes']],allow_nan=False)
    title = html.escape(plan["topic"])
    return f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><title>{title}</title><style>
*{{box-sizing:border-box}}
html,body{{margin:0;background:#020617;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow:hidden}}
#stage{{width:{width}px;height:{height}px;position:relative;background:#101722;overflow:hidden}}
#webglCanvas{{position:absolute;inset:0;width:100%;height:100%;z-index:1}}
.hud-layer{{position:absolute;inset:0;z-index:2;pointer-events:none}}
.scene-hud{{position:absolute;inset:0;display:none;flex-direction:column;align-items:stretch;padding:{height*.10}px {width*.16}px {height*.24}px {width*.08}px}}
.chapter-badge{{color:#fbbf24;font-size:{max(12,round(min(width,height)*.022))}px;letter-spacing:.12em}}
.badge-dot,.hud-corner,.sound-wave{{display:none}}
.hud-center{{width:100%;height:22%;margin-top:3%;display:flex;align-items:flex-start}}
.reticle-box{{width:100%;text-align:left}}
.hero-title{{font-size:{round(min(width,height)*.065)}px;line-height:1.12;margin:0;font-weight:800;overflow-wrap:anywhere}}
.subtitle-capsule{{margin-top:auto;width:100%;font-size:{round(min(width,height)*.032)}px;line-height:1.35;color:#e2e8f0;overflow-wrap:anywhere;padding:1.5% 2%;border-left:3px solid #fbbf24;background:#101722}}
</style></head><body>
<div id="stage" data-composition-id="video" data-fps="{frame_rate.get(plan)}" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}">
    <canvas id="webglCanvas"></canvas>
    <div class="hud-layer">
        {''.join(sections)}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js"></script>
    <script>
    const width = {width}, height = {height}, duration = {duration};
    const canvas = document.getElementById('webglCanvas');
    const renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' }});
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 15);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
    scene.add(ambientLight);
    const keyLight = new THREE.DirectionalLight(0xfff4df, 3.0);
    keyLight.position.set(6, 8, 10);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0x94b6dc, 4.0, 40);
    rimLight.position.set(-6, -4, 8);
    scene.add(rimLight);
    const shotControls = {shot_controls};
    {scene_render.THREE_SCRIPT}

    {Path(__file__).with_name('three_scene.js').read_text(encoding='utf-8')}
    const drawShot = createThreeShots({json.dumps([{'start':s['start'],'end':s['end'],'spec':opuscar_scene_spec.interpret(s),'controls':scene_render.validate(s.get('renderControls',{}))} for s in plan['scenes']],ensure_ascii=True).replace('<', chr(92)+'u003c')});

    // GSAP master timeline that drives both 3D WebGL clock and HTML HUD
    const tl = gsap.timeline({{ paused: true }});
    const clock = {{ t: 0 }};
    tl.to(clock, {{
        t: duration,
        duration: duration,
        ease: "none",
    }}, 0);
    function drawThreeFrame(t) {{
            drawShot(t);
            document.querySelectorAll('.scene-hud').forEach(section=>{{
                if(getComputedStyle(section).display==='none')return;
                for(const [selector,base,budget] of [['.hero-title',.065,.15],['.subtitle-capsule',.032,.13]]){{
                    const element=section.querySelector(selector);let fs=Math.min(width,height)*base;
                    element.style.fontSize=fs+'px';
                    while((element.scrollHeight>height*budget || element.scrollWidth>element.clientWidth+1) && fs>Math.min(width,height)*.014){{fs-=1;element.style.fontSize=fs+'px';}}
                }}
            }});
            applySceneControls(t);
            camera.lookAt(0, 0, 0);
            renderer.render(scene, camera);
    }}

    {''.join(animation)}

    window.__timelines = window.__timelines || {{}};
    window.__timelines.video = tl;
    {animation_clock.SCRIPT}
    attachAnimationClock(tl, drawThreeFrame, duration);
    </script>
</div>
</body></html>'''


def generate_composition(plan: dict, aspect_info: dict, model: str = "", engine: str = "opuscar") -> str:
    if engine=='remotion':return remotion_adapter.preview(plan)
    if engine=='continuous':return continuous_motion.composition(plan,aspect_info)
    if engine == "threejs":
        document=generate_threejs_composition(plan, aspect_info, model)
    else:document=generate_opuscar_composition(plan, aspect_info, model)
    return creative_profile.styled(document,plan.get('brand'))


def audio_manifest(plan: dict) -> dict:
    result = {"duration": plan["duration"], "voice": [{"id": scene["id"], "start": scene["start"], "end": scene["end"], "text": scene["narration"]} for scene in plan["scenes"]], "subtitles": [{"start": scene["start"], "end": scene["end"], "text": scene["narration"]} for scene in plan["scenes"]], "soundCues": [{"at": scene["start"], "cue": scene["soundCue"]} for scene in plan["scenes"] if scene["soundCue"]], "music": {"start": 0, "end": plan["duration"], "duckUnderVoice": True, "targetLufs": -14,
            "beat_markers": [round(.125+i*.5,3) for i in range(math.ceil(plan['duration']*2)) if .125+i*.5<plan['duration']],
            "beat_method": "known_procedural_envelope_peaks_2hz_not_external_music_detection"}}
    if plan.get('motionDesign'):
        holds=continuous_motion.beat_sheet(plan)['beats']
        result['music']['beat_markers']=[t for t in result['music']['beat_markers'] if not any(b['holdStart']+.04<t<b['holdEnd']-.04 for b in holds)]
        result['voiceMode']=plan['motionDesign']['voiceMode']
        if result['voiceMode']=='music':
            result['voice']=[]
            result['music']['duckUnderVoice']=False
    if plan.get('audioMode'):
        result['voiceMode']=plan['audioMode']
        if plan['audioMode']=='music':result['voice']=[];result['music']['duckUnderVoice']=False
    if 'speech' in plan:
        speech=speech_settings.validate(plan['speech'])
        result.update(speech=speech,voiceMode=speech['mode'])
        if not speech['sfx'] or speech['mode']=='none':result['soundCues']=[]
        else:
            for cue,scene in zip(result['soundCues'],[s for s in plan['scenes'] if s['soundCue']]):cue['at']=creative_profile.reveal(scene,0)
        result['sfx']={'enabled':speech['sfx'] and speech['mode']!='none','source':'short_local_procedural_cues'}
        result['music']={'enabled':False,'duckUnderVoice':False,'beat_markers':[]}
        if speech['mode']=='none':result['voice']=[]
    return result


def _srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000); hours, remainder = divmod(milliseconds, 3600000); minutes, remainder = divmod(remainder, 60000); secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_subtitles(path: Path, plan: dict) -> None:
    path.write_text("\n\n".join(f"{index}\n{_srt_time(scene['start'])} --> {_srt_time(scene['end'])}\n{scene['narration']}" for index, scene in enumerate(plan["scenes"], 1)) + "\n", encoding="utf-8")


def _result_metadata(directory: Path, meta: dict) -> dict:
    video, lottie = directory / "video.mp4", directory / "lottie.json"
    meta.update(htmlUrl=f"/api/videos/{directory.name}/index.html")
    if (directory/"final-audio.wav").is_file():meta["voiceUrl"]=f"/api/videos/{directory.name}/final-audio.wav"
    if (directory / "review.json").is_file():
        meta["review"] = json.loads((directory / "review.json").read_text("utf-8"))
    if video.is_file():
        meta.update(videoSize=video.stat().st_size, videoUrl=f"/api/videos/{directory.name}/video.mp4")
    elif lottie.is_file():
        meta.update(lottieSize=lottie.stat().st_size, lottieUrl=f"/api/videos/{directory.name}/lottie.json")
    else:
        raise FileNotFoundError(directory.name)
    return meta


def list_videos() -> list[dict]:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True); results = []
    for directory in sorted(VIDEOS_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            results.append(_result_metadata(directory, meta))
        except (OSError, ValueError): pass
    return results


def _video_directory(slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", slug):
        raise ValueError("Slug project video tidak valid")
    target = (VIDEOS_DIR / slug).resolve()
    root = VIDEOS_DIR.resolve()
    if target.parent != root:
        raise ValueError("Path project video tidak valid")
    return target


def get_video(slug: str) -> dict:
    target = _video_directory(slug)
    if not target.is_dir(): raise FileNotFoundError(slug)
    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    result = _result_metadata(target, meta)
    research_path = target / "research.json"
    if research_path.is_file():
        result["research"] = json.loads(research_path.read_text(encoding="utf-8"))
    plan_path = target / "scene-plan.json"
    if plan_path.is_file():
        result["scenePlan"] = json.loads(plan_path.read_text(encoding="utf-8"))
        result["storyboard"] = _storyboard(result["scenePlan"])
    return result


def create_aspect_jobs(slug: str, aspects: list[str]) -> list[dict]:
    if not isinstance(aspects, list) or not 1 <= len(aspects) <= len(ASPECT_RATIOS) or any(not isinstance(a, str) or a not in ASPECT_RATIOS for a in aspects):
        raise ValueError("Pilih satu atau beberapa rasio yang didukung")
    source = get_video(slug)
    plan = source.get("scenePlan")
    engine = source.get("engine")
    if not plan or engine not in ENGINES:
        raise ValueError("Hasil ini belum memiliki rencana yang dapat digunakan ulang")
    jobs = []
    with JOBS_LOCK:
        for aspect in dict.fromkeys(aspects):
            key = uuid.uuid4().hex
            job = {"jobId": key, "pipelineVersion":2, "fps": frame_rate.get(plan), "topic": plan["topic"], "script": "", "engine": engine,
                   "style": ENGINES[engine]["defaultStyle"], "templateId":plan.get("templateId",""), "aspect": aspect, "duration": plan["duration"],
                   "model": source.get("model", LLM_MODEL), "status": "awaiting_scene_plan", "step": "Review layout rasio baru sebelum render",
                   "progress": 35, "error": None, "research": source.get("research"), "scenePlan": copy.deepcopy(plan),
                   "storyboard": None, "video": None, "revision": 0, "approvals": {},
                   "rendererReview":renderer_contract.inspect(plan,engine), "facelessQuality":faceless_quality.inspect(plan) if plan.get("templateId") else None, "origin": {"slug": slug, "scene_plan_digest": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()}}
            if "speech" in plan:job["speech"]=plan["speech"]
            if engine=='continuous':job['motionDesign']=plan.get('motionDesign')
            if engine=='remotion':job['audioMode']=plan.get('audioMode','music')
            save_job(JOB_DIR, job)
            JOBS[key] = job
            jobs.append(copy.deepcopy(job))
    return jobs


def delete_video(slug: str) -> dict:
    target = _video_directory(slug)
    if not target.is_dir(): raise FileNotFoundError(slug)
    shutil.rmtree(target)
    return {"ok": True, "slug": slug}


class RevisionConflict(ValueError):
    """The browser is acting on a superseded workflow revision."""


def _check_revision(job: dict, expected_revision: int | None) -> None:
    if expected_revision is not None and (type(expected_revision) is not int or expected_revision != job.get("revision", 0)):
        raise RevisionConflict("Versi pekerjaan berubah; muat ulang sebelum melanjutkan")


def list_jobs() -> list[dict]:
    with JOBS_LOCK:
        return [{k: copy.deepcopy(job.get(k)) for k in ("jobId", "topic", "aspect", "status", "revision", "step")}
                for job in JOBS.values() if job.get("status") != "succeeded"]


def resume_job(job_id: str, expected_revision: int) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS:
            raise KeyError(job_id)
        job = JOBS[job_id]
        _check_revision(job, expected_revision)
        if job["status"] not in {"interrupted", "failed"}:
            raise ValueError("Pekerjaan ini tidak dapat dilanjutkan dari status sekarang")
        # Restore review, never restart an expensive render without renewed approval.
        job.update(revision=int(job.get("revision", 0)) + 1, error=None, approvals={}, storyboard=None)
        has_plan = bool(job.get("scenePlan"))
        job.update(status="awaiting_scene_plan" if has_plan else "queued",
                   step="Periksa kembali Scene Plan sebelum menyetujui" if has_plan else "Mengulang riset",
                   progress=35 if has_plan else 5)
        save_job(JOB_DIR, job)
        result = copy.deepcopy(job)
    if not has_plan:
        threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return result


def update_job_plan(job_id: str, payload: dict) -> dict:
    stage = str(payload.get("stage") or "")
    if stage not in {"scene_plan", "storyboard"}: raise ValueError("Tahap editor tidak valid")
    with JOBS_LOCK:
        if job_id not in JOBS: raise KeyError(job_id)
        job = JOBS[job_id]
        expected = "awaiting_scene_plan" if stage == "scene_plan" else "awaiting_storyboard"
        if job["status"] != expected: raise ValueError("Project tidak sedang berada pada tahap yang dapat diedit")
        _check_revision(job, payload.get("revision"))
        raw_plan = payload.get("scenePlan")
        if not isinstance(raw_plan, dict) or not isinstance(raw_plan.get("scenes"), list):
            raise ValueError("Scene plan tidak valid")
        if raw_plan.get('motionDesign') is not None and job.get('engine')!='continuous':
            raise ValueError('Desain kontinu hanya tersedia untuk adapter Continuous Motion')
        if job.get('speech') and 'speech' not in raw_plan:raw_plan={**raw_plan,'speech':job['speech']}
        if job.get("templateId") and "templateId" not in raw_plan:
            raw_plan={**raw_plan,"templateId":job["templateId"]}
        plan = normalize_scene_plan(raw_plan, job["topic"], "", job["duration"])
        if plan.get("templateId") and job.get("engine") != "remotion":
            raise ValueError("Template Faceless hanya berlaku untuk Remotion")
        if plan.get("templateId", "") != job.get("templateId", ""):
            raise ValueError("Pilihan template tidak boleh diganti selama review; buat pekerjaan baru")
        if job.get('engine') not in {'remotion','lottie'} and any('diagram' in scene for scene in plan['scenes']):
            raise ValueError('Diagram berlabel hanya tersedia untuk Remotion dan Lottie')
        if job.get('engine') not in {'opuscar','threejs','remotion'} and any('renderControls' in scene for scene in plan['scenes']):
            raise ValueError('Kontrol kamera/lighting render hanya tersedia untuk Opuscar, Three.js dan Remotion')
        if job.get('engine')=='remotion':
            if not plan.get('speech') and plan.get('audioMode')!=job.get('audioMode'):raise ValueError('Mode audio Remotion wajib dipertahankan saat mengedit')
            remotion_adapter.manifest(plan,ASPECT_RATIOS[job['aspect']])
        elif 'audioMode' in plan:raise ValueError('audioMode hanya tersedia pada adapter Remotion')
        if job.get('engine')=='continuous' and not plan.get('motionDesign'):
            raise ValueError('Desain gerak kontinu wajib dipertahankan saat mengedit')
        # Clicking approve also saves the editor. Preserve approval for an unchanged plan.
        if plan == job.get("scenePlan"):
            return copy.deepcopy(job)
        job["approvals"] = {}
        job.pop("productionPacket",None)
        job["narrationDraft"]=preproduction.from_plan(plan,"user_edit")
        job.pop("visualReview", None)
        job.pop("visualFrames", None)
        job.pop("visualContactSheet", None)
        if stage == "storyboard":
            job["status"] = "awaiting_scene_plan"
        if "speech" in plan:
            job["speech"]=plan["speech"]
            if job["engine"]=="remotion":job["audioMode"]=plan["audioMode"]
            if job["engine"]=="continuous":job["motionDesign"]=plan["motionDesign"]
        job["fps"] = frame_rate.get(plan)
        job["rendererReview"]=renderer_contract.inspect(plan,job.get("engine","opuscar"))
        job["facelessQuality"]=faceless_quality.inspect(plan) if job.get("templateId") else None
        job["scenePlan"] = plan
        job["storyboard"] = _storyboard(plan) if stage == "storyboard" else None
        job["step"] = "Perubahan editor tersimpan"
        job["revision"] = int(job.get("revision", 0)) + 1
        save_job(JOB_DIR, job)
        return dict(job)


def read_video_file(slug: str, filename: str) -> tuple[bytes, str]:
    path,content_type=video_file_path(slug,filename)
    return path.read_bytes(),content_type


def video_file_path(slug: str, filename: str) -> tuple[Path, str]:
    if filename not in {"video.mp4", "index.html", "subtitles.srt", "lottie.json", "scene-plan.json", "final-audio.wav", "voice.wav", "narration.json", "production-prompts.json", "research.json", "review.json", "audio-manifest.json", "contact-sheet.png"} and not re.fullmatch(r"review-frame-\d{1,3}\.png", filename): raise FileNotFoundError(filename)
    path = _video_directory(slug) / filename
    if path.is_symlink() or not path.is_file(): raise FileNotFoundError(filename)
    return path, {".mp4": "video/mp4", ".html": "text/html; charset=utf-8", ".srt": "text/plain; charset=utf-8", ".json": "application/json; charset=utf-8", ".png": "image/png", ".wav":"audio/wav"}.get(path.suffix, "application/octet-stream")


def job_status(job_id: str) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS: raise KeyError(job_id)
        return copy.deepcopy(JOBS[job_id])


def approve_job(job_id: str, stage: str, expected_revision: int | None = None) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS: raise KeyError(job_id)
        job = JOBS[job_id]
        _check_revision(job, expected_revision)
        expected = {"scene_plan": "awaiting_scene_plan", "storyboard": "awaiting_storyboard"}.get(stage)
        if not expected or job["status"] != expected:
            raise ValueError(f"Tahap {stage} tidak dapat disetujui dari status {job['status']}")
        if job.get('pipelineVersion')==2:renderer_contract.verify(job['scenePlan'],job['engine'])
        if stage == 'storyboard' and job.get('pipelineVersion')==2:
            preproduction.verify_packet(job.get('productionPacket'),job['scenePlan'],job['engine'],job['aspect'])
        if stage == "storyboard" and job.get('engine') == 'opuscar' and opuscar_quality_gate.required(job['scenePlan']):
            document=generate_composition(job['scenePlan'],ASPECT_RATIOS[job['aspect']],job.get('model',''),engine='opuscar')
            opuscar_quality_gate.verify(document,job.get('visualReview'))
        job.setdefault("approvals", {})[stage] = job.get("revision", 0)
        job["status"] = "queued"
        job["step"] = "Persetujuan diterima"
        save_job(JOB_DIR, job)
    threading.Thread(target=_continue_job, args=(job_id, stage), daemon=True).start()
    return {"jobId": job_id, "status": "queued", "approved": stage}


def revise_job(job_id: str, expected_revision: int | None = None) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS: raise KeyError(job_id)
        job = JOBS[job_id]
        _check_revision(job, expected_revision)
        if job["status"] != "awaiting_storyboard": raise ValueError("Revisi hanya tersedia pada tahap Storyboard")
        job.update(revision=int(job.get("revision", 0)) + 1, approvals={})
        job.update(status="awaiting_scene_plan", step="Scene Plan menunggu persetujuan", progress=30, storyboard=None)
        save_job(JOB_DIR, job)
        return dict(job)


def start_job(payload: dict) -> dict:
    if not isinstance(payload,dict):raise ValueError('Brief harus objek JSON')
    topic = str(payload.get("topic") or "").strip()
    if not topic: raise ValueError("Topik video wajib diisi")
    script=str(payload.get('script') or '').strip()
    creative_brief=payload.get('creativeBrief','')
    if not isinstance(creative_brief,str) or len(creative_brief)>4000:raise ValueError('Arahan produksi maksimal 4.000 karakter')
    if len(topic)>500 or len(script)>30000:raise ValueError('Topik maksimal 500 karakter; naskah maksimal 30.000 karakter')
    research_mode=payload.get('researchMode','planner')
    if research_mode not in {'planner','web','provided'}:raise ValueError('Mode perencanaan tidak dikenal')
    research_ready = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")) and PODCASTFY_PYTHON.is_file()
    # UI baru menonaktifkan Web Search ketika provider belum siap. Untuk klien lama,
    # permintaan web yang membawa naskah dialihkan ke mode lokal. Permintaan tanpa
    # naskah tetap diterima agar kontrak API lama tidak rusak; thread riset akan
    # melaporkan kegagalan konfigurasi seperti sebelumnya.
    if research_mode == 'web' and not research_ready:
        research_mode = 'planner'
    if research_mode=='provided' and not script:raise ValueError('Mode naskah sendiri memerlukan naskah; periksa fakta sebelum menyetujui')
    aspect = str(payload.get("aspect") or "9:16"); aspect = aspect if aspect in ASPECT_RATIOS else "9:16"
    duration = int(payload.get("duration") or 60); duration = duration if duration in DURATIONS else 60
    fallback_model = LLM_MODEL if LLM_MODEL in ALLOWED_MODEL_IDS else "ag/gemini-3.8-flash-high"
    model = str(payload.get("model") or fallback_model); model = model if model in ALLOWED_MODEL_IDS else fallback_model
    engine = str(payload.get("engine") or "opuscar")
    if engine not in ENGINES or ENGINES[engine].get("disabled"): raise ValueError("Render Adapter belum tersedia")
    template_id = payload.get("templateId") or ""
    template = video_templates.get(template_id) if template_id else None
    if template and engine != template["engine"]:
        raise ValueError("Template ini hanya mendukung Remotion; pilih adapter Remotion")
    fps = frame_rate.validate(payload.get("fps", frame_rate.DEFAULT))
    style = ENGINES[engine]["defaultStyle"]
    job_id = uuid.uuid4().hex
    job = {"jobId": job_id, "pipelineVersion":2, "creativeBrief":creative_brief.strip(), "fps": fps, "topic": topic, "script": script, "researchMode":research_mode, "engine": engine, "style": style, "templateId": template_id, "aspect": aspect, "duration": duration, "model": model, "status": "queued", "step": "Menyiapkan rencana", "progress": 5, "error": None, "research": None, "scenePlan": None, "storyboard": None, "video": None, "revision": 0, "approvals": {}}
    if payload.get('voiceMode')!='music':job['speech']=speech_settings.build(payload.get('speechLanguage','id'),payload.get('voiceMode','tts'),payload.get('sfx',True))
    if engine=='remotion':
        if payload.get('voiceMode','tts') not in ('music','tts','none'):raise ValueError('Audio harus music atau tts')
        job['audioMode']=payload.get('voiceMode','tts')
    if engine=='continuous':
        job['motionDesign']=continuous_motion.design({'concept':payload.get('motionConcept'),'voiceMode':payload.get('voiceMode','tts'),'fps':fps},
                [{'start':0,'end':duration}],duration)
    if template:
        job["brand"]=creative_profile.snapshot(template["brand"])
    if payload.get('brandId'):
        kit=next((row for row in creative_profile.catalog(VIDEOS_DIR.parent/'brand-kits.json')['kits'] if row['id']==payload['brandId']),None)
        if not kit:raise ValueError('Brand tidak ditemukan; muat ulang daftar')
        job['brand']=creative_profile.snapshot(kit)
    with JOBS_LOCK:
        JOBS[job_id] = job
        save_job(JOB_DIR, job)
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"jobId": job_id, "status": "queued"}


def _update_job(job_id: str, values: dict) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(values)
        save_job(JOB_DIR, JOBS[job_id])


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:50] or "video"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _write_procedural_audio(path: Path, plan: dict, sample_rate: int = 48000) -> None:
    """Create music bed and cue-driven foley without external assets."""
    cues = [(float(item["at"]), str(item["cue"]).lower()) for item in audio_manifest(plan)["soundCues"]]
    frames = bytearray()
    holds=continuous_motion.beat_sheet(plan)['beats'] if plan.get('motionDesign') else []
    hold_index=0
    for sample in range(round(plan["duration"] * sample_rate)):
        t = sample / sample_rate
        pulse = 0.55 + 0.45 * math.sin(2 * math.pi * 2 * t)
        value = 0.055 * pulse * (math.sin(2 * math.pi * 110 * t) + 0.35 * math.sin(2 * math.pi * 220 * t))
        for cue_at, cue_name in cues:
            local = t - cue_at
            if 0 <= local < 0.35:
                frequency = 1200 if any(word in cue_name for word in ("bell", "chime", "ding")) else 420
                value += 0.18 * (1 - local / 0.35) * math.sin(2 * math.pi * frequency * local)
        if holds:
            while hold_index+1<len(holds) and t>=holds[hold_index]['end']:hold_index+=1
            hold=holds[hold_index]
            # Leave audible pauses only on this adapter, with short ramps against clicks.
            if hold['holdStart']<=t<=hold['holdEnd']:
                edge=min(t-hold['holdStart'],hold['holdEnd']-t)
                value*=max(0,1-edge/.04)
        frames.extend(int(max(-1, min(1, value)) * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, sample_rate, len(frames) // 2, "NONE", "not compressed"))
        output.writeframes(frames)


def _build_audio(target: Path, plan: dict) -> Path:
    """Synthesize narration per scene, align it, mix music/foley, and normalize."""
    ffmpeg = shutil.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
    if not Path(ffmpeg).is_file() and not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg tidak ditemukan untuk audio mux")
    speech=speech_settings.validate(plan['speech']) if 'speech' in plan else None
    if speech and speech['mode']=='none':
        final=target/'final-audio.wav'
        with wave.open(str(final),'wb') as out:
            out.setparams((1,2,48000,0,'NONE','not compressed'))
            remaining=round(plan['duration']*48000)
            while remaining:
                n=min(remaining,48000);out.writeframes(b'\x00\x00'*n);remaining-=n
        (target/'audio-mastering.json').write_text(json.dumps({'method':'intentional_silence','status':'intentionally_silent'}))
        return final
    if not speech and (plan.get('audioMode')=='music' or plan.get('motionDesign',{}).get('voiceMode')=='music'):
        bed=target/'music-foley.wav'
        _write_procedural_audio(bed,plan)
        final=target/'final-audio.wav'
        mastering=audio_mastering.normalize(ffmpeg,bed,final)
        (target/'audio-mastering.json').write_text(json.dumps(mastering),encoding='utf-8')
        return final
    python = resolve_python(OPUSCAR_DIR)
    tts = OPUSCAR_DIR / "core" / "tts" / "tts_zh.py"
    if not python.is_file():
        raise RuntimeError("Opuscar voice environment belum tersedia")
    voice_name=speech['voice'] if speech else 'id-ID-ArdiNeural'
    voice_rate=speech['rate'] if speech else '+8%'
    voiced=[scene for scene in plan['scenes'] if scene['narration'].strip()]
    if not voiced:raise ValueError('Narasi kosong; pilih tanpa suara atau isi narasi')
    lines = [{"id": scene["id"], "text": scene["narration"], "voice": voice_name, "rate": voice_rate} for scene in voiced]
    lines_path = target / "voice-lines.json"
    voice_dir = target / "voice"
    lines_path.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
    command=[str(python),str(ROOT/'speech_worker.py'),str(lines_path),str(voice_dir)] if speech else [str(python),str(tts),str(lines_path),str(voice_dir),'--voice',voice_name,'--rate',voice_rate]
    subprocess.run(command,check=True,timeout=600,env=render_environment())
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, scene in enumerate(voiced):
        voice_file = voice_dir / f"{scene['id']}.wav"
        # Never turn an empty/silent provider response into an apparently successful dubbed film.
        # The gate checks signal presence; correct spoken words still require human review.
        check = voice_quality.require_audible(voice_file)
        voice_duration = check["duration"]
        if voice_duration > float(scene["end"]) - float(scene["start"]) + 0.05:
            raise RuntimeError(f"Narasi {scene['id']} melebihi slot adegan; revisi timing atau narasi sebelum render")
        inputs.extend(["-i", str(voice_file)])
        delay = round(scene["start"] * 1000)
        label = f"v{index}"
        filters.append(f"[{index}:a]adelay={delay}|{delay},apad,atrim=0:{plan['duration']}[{label}]")
        labels.append(f"[{label}]")
    voice_mix = target / "voice.wav"
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,atrim=0:{plan['duration']}[voice]")
    subprocess.run([ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[voice]", "-ar", "48000", str(voice_mix)], check=True, timeout=600)
    if speech:
        final=target/'final-audio.wav'
        cues=audio_manifest(plan)['soundCues']
        premaster=target/'voice-sfx-premaster.wav'
        source=voice_mix
        try:
            if speech['sfx'] and cues:
                effects=target/'sound-effects.wav'
                sound_effects.write(effects,plan['duration'],cues)
                mix='[0:a]asplit=2[voice][detector];[1:a]volume=.32[fx];[fx][detector]sidechaincompress=threshold=.02:ratio=6:attack=4:release=120[ducked];[voice][ducked]amix=inputs=2:duration=first:normalize=0[a]'
                subprocess.run([ffmpeg,'-v','error','-nostdin','-y','-i',str(voice_mix),'-i',str(effects),'-filter_complex',mix,'-map','[a]','-t',str(plan['duration']),str(premaster)],check=True,timeout=600,env=render_environment())
                source=premaster
            mastering=audio_mastering.normalize(ffmpeg,source,final)
        finally:premaster.unlink(missing_ok=True)
        (target/'audio-mastering.json').write_text(json.dumps(mastering),encoding='utf-8')
        return final
    bed = target / "music-foley.wav"
    _write_procedural_audio(bed, plan)
    final = target / "final-audio.wav"
    mix = "[0:a]volume=.32[bed];[bed][1:a]sidechaincompress=threshold=.025:ratio=8:attack=12:release=350[ducked];[ducked][1:a]amix=inputs=2:normalize=0[a]"
    premaster=target/'premaster-audio.wav'
    try:
        subprocess.run([ffmpeg, "-y", "-i", str(bed), "-i", str(voice_mix), "-filter_complex", mix, "-map", "[a]", "-t", str(plan["duration"]), "-ar", "48000", str(premaster)], check=True, timeout=600,env=render_environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        mastering=audio_mastering.normalize(ffmpeg,premaster,final)
        (target/'audio-mastering.json').write_text(json.dumps(mastering),encoding='utf-8')
    finally:premaster.unlink(missing_ok=True)
    return final


def _mux_video(target: Path, silent: Path, audio: Path, duration: float) -> Path:
    ffmpeg = shutil.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
    output = target / "video.mp4"
    subprocess.run([ffmpeg, "-y", "-i", str(silent), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1", "-map_chapters", "-1", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(duration), "-movflags", "+faststart", str(output)], check=True, timeout=600)
    return output


def _storyboard(plan: dict) -> list[dict]:
    return [{
        "id": scene["id"], "number": index + 1, "start": scene["start"], "end": scene["end"],
        "duration": scene["duration"], "type": scene["type"], "shotPurpose": scene.get("shotPurpose", "develop"),
        "narration": scene["narration"], "text": scene["onScreenText"], "visual": scene["visual"],
        "visualFamily": scene.get("visualFamily", "constellation"), "subject": scene.get("subject", ""),
        **({"diagram": scene["diagram"]} if "diagram" in scene else {}),
        "action": scene.get("action", ""), "setting": scene.get("setting", ""),
        "composition": scene.get("composition", ""), "foreground": scene.get("foreground", ""),
        "midground": scene.get("midground", ""), "background": scene.get("background", ""),
        "camera": scene.get("camera", ""), "lighting": scene.get("lighting", ""),
        "colorMood": scene.get("colorMood", "adaptive"), "typography": scene.get("typography", ""),
        "transition": scene.get("transition", "shape-morph"), "continuity": scene.get("continuity", ""),
        "soundCue": scene.get("soundCue", ""), "motion": scene["motion"],
    } for index, scene in enumerate(plan["scenes"])]


def _run_job(job_id: str) -> None:
    job = job_status(job_id)
    try:
        mode=job.get('researchMode','planner')
        provided=mode=='provided'
        web=mode=='web'
        step = "Mencari sumber melalui Google Search" if web else "Menyusun naskah lokal untuk review" if provided else "Menyusun creative direction dengan model terpilih"
        _update_job(job_id, {"status": "researching", "step": step, "progress": 10})
        if web:
            research = _research_web(job["topic"], job["script"])
        elif provided:
            research = {'provider':'Naskah pengguna lokal','mode':'provided','summary':'Rencana lokal deterministik tanpa panggilan model atau Web Search. Fakta tidak diverifikasi otomatis.','sources':[],'sourceCount':0}
        else:
            research = {'provider':'Creative planning 9Router','mode':'planner','summary':'Treatment dikembangkan dari judul oleh model terpilih tanpa Web Search. Klaim faktual spesifik harus ditinjau sebelum persetujuan.','sources':[],'sourceCount':0}
        _update_job(job_id, {"research": research, "step": "Konteks siap; menyusun Scene Plan sinematik", "progress": 20})
        explicit = parse_explicit_scenes(job["script"])
        planning_input = job["script"]
        if web:
            planning_input += "\n\n" + _research_context(research)
        # Mode provided tetap merupakan jalur lokal deterministik. Ini penting untuk
        # naskah bertimecode dan produksi offline: model tetap dapat dipilih di UI,
        # tetapi hanya dipakai oleh mode planner/web yang memang meminta generasi AI.
        if job.get('narrationDraft'):
            saved=job['narrationDraft']
            draft=preproduction.narration(saved['text'],saved['source'],allow_empty=saved['source']=='provided_timecodes')
        elif explicit:
            draft=preproduction.narration(' '.join(s['narration'] for s in explicit),'provided_timecodes',allow_empty=True)
        elif job['script'].strip():
            draft=preproduction.narration(job['script'],'provided_script')
        else:
            _update_job(job_id,{'status':'writing_narration','step':'Menulis narasi utuh sebelum pembagian scene','progress':22})
            response=_clean_json(_call_9router(preproduction.script_prompt(job['topic'],_research_context(research)+'\nArahan produksi: '+job.get('creativeBrief',''),job['duration'],job.get('speech',{}).get('language','id')),job['model']))
            draft=preproduction.narration(response.get('narration'),'generated')
        _update_job(job_id,{'narrationDraft':draft,'initialNarrationDraft':draft,
            'status':'planning_scenes','step':'Membagi narasi menjadi shot dan arahan visual','progress':28})
        prompt=build_scene_prompt(job['topic'],planning_input,job['duration'],job['aspect'])
        prompt+='\nBahasa judul layar: '+job.get('speech',{}).get('language','id')+'. Pertahankan naskah pengguna; jangan menerjemahkan narasi terkunci.\nArahan produksi (bukan narasi): '+job.get('creativeBrief','')+'\nAdapter yang dipilih: '+job['engine']+'.'+preproduction.scene_instruction(draft)
        prompt+=renderer_contract.planner_instruction(job['engine'])
        if job.get("templateId"):
            chosen=video_templates.get(job["templateId"])
            prompt+="\nVISUAL TEMPLATE "+chosen["name"]+": "+chosen["direction"]+" Sesuaikan setiap scene dengan cerita; jangan gunakan satu motif berulang."
        if job.get('speech'):prompt+='\nAudio ikuti konfigurasi aktual: '+json.dumps(job['speech'])+'. Hanya elemen yang diaktifkan yang akan dibuat; SFX singkat harus mendukung aksi.'
        if job.get('motionDesign'):
            concept=next(row for row in continuous_motion.CONCEPTS if row['id']==job['motionDesign']['concept'])
            prompt+='\nKonsep wajib: '+concept['idea']+' '+concept['carry']+' Tutup seluruh durasi tanpa gap.'
        data = {} if explicit or provided else _clean_json(_call_9router(prompt, job["model"]))
        if job.get('motionDesign'):data['motionDesign']=job['motionDesign']
        else:data.pop('motionDesign',None)
        if job.get('engine')=='remotion':data['audioMode']=job['audioMode']
        else:data.pop('audioMode',None)
        if "speech" in job:data["speech"]=job["speech"]
        if job.get("creativeBrief"):data["creativeBrief"]=job["creativeBrief"]
        data["fps"]=frame_rate.get(job)
        if job.get("templateId"):data["templateId"]=job["templateId"]
        plan = normalize_scene_plan(data, job["topic"], job["script"], job["duration"])
        preproduction.verify_narration(draft,plan)
        if not explicit:preproduction.verify_timing(plan,job["duration"])
        if job.get('engine')=='remotion':remotion_adapter.manifest(plan,ASPECT_RATIOS[job['aspect']])
        if job.get('engine') not in {'remotion','lottie'} and any('diagram' in scene for scene in plan['scenes']):
            raise ValueError('Diagram berlabel hanya tersedia untuk Remotion dan Lottie')
        if job.get('engine') not in {'opuscar','threejs','remotion'} and any('renderControls' in scene for scene in plan['scenes']):
            raise ValueError('Model mengembalikan kontrol render yang tidak didukung adapter ini')
        if job.get('brand'):plan['brand']=copy.deepcopy(job['brand'])
        _update_job(job_id, {"status": "awaiting_scene_plan", "step": "Riset dan Scene Plan menunggu persetujuan", "progress": 35, "scenePlan": plan,"rendererReview":renderer_contract.inspect(plan,job["engine"]),
            "facelessQuality":faceless_quality.inspect(plan) if job.get("templateId") else None})
    except Exception as exc:
        _update_job(job_id, {"status": "failed", "step": f"Gagal: {exc}", "progress": 100, "error": str(exc)})


def _continue_job(job_id: str, approved_stage: str) -> None:
    job = job_status(job_id)
    try:
        if job.get("pipelineVersion")==2:renderer_contract.verify(job["scenePlan"],job["engine"])
        if approved_stage == "scene_plan":
            packet=preproduction.compile_packet(job['scenePlan'],job['engine'],job['aspect'])
            storyboard = _storyboard(job["scenePlan"])
            for shot,compiled in zip(storyboard,packet['shots']):shot['productionPrompt']=compiled['prompt']
            _update_job(job_id,{'productionPacket':packet})
            if job['engine']=='opuscar' and opuscar_quality_gate.required(job['scenePlan']):
                _update_job(job_id,{'step':'Membuat style frames untuk review Storyboard','progress':40})
                preview=VIDEOS_DIR/_slugify(job['topic']+'-review')
                preview.mkdir(parents=True)
                document=generate_composition(job['scenePlan'],ASPECT_RATIOS[job['aspect']],job.get('model',''),engine='opuscar')
                (preview/'index.html').write_text(document,encoding='utf-8')
                report=opuscar_quality_gate.inspect(preview,job['scenePlan'],ASPECT_RATIOS[job['aspect']])
                _update_job(job_id,{'visualReview':report,
                    'visualFrames':[f'/api/videos/{preview.name}/{name}' for name in report['frames']],
                    'visualContactSheet':f'/api/videos/{preview.name}/contact-sheet.png' if report.get('contactSheet') else None})
            _update_job(job_id, {"status": "awaiting_storyboard", "step": "Storyboard menunggu persetujuan", "progress": 45, "storyboard": storyboard})
            return
        plan = job["scenePlan"]
        if job.get('pipelineVersion')==2:preproduction.verify_packet(job.get('productionPacket'),plan,job['engine'],job['aspect'])
        if job['engine']=='opuscar' and opuscar_quality_gate.required(plan):
            opuscar_quality_gate.verify(generate_composition(plan,ASPECT_RATIOS[job['aspect']],job.get('model',''),engine='opuscar'),job.get('visualReview'))
        missing=runtime_issues(job['engine'])
        if missing:raise RuntimeError('Runtime render belum siap: '+', '.join(missing)+'. Siapkan runtime atau gunakan adapter Lottie.')
        target = VIDEOS_DIR / _slugify(job["topic"])
        target.mkdir(parents=True)
        (target / "research.json").write_text(json.dumps(job["research"], ensure_ascii=False, indent=2), encoding="utf-8")
        (target/'production-prompts.json').write_text(json.dumps(preproduction.compile_packet(plan,job['engine'],job['aspect']),ensure_ascii=False,indent=2),encoding='utf-8')
        (target/'narration.json').write_text(json.dumps(preproduction.from_plan(plan),ensure_ascii=False,indent=2),encoding='utf-8')
        (target / "scene-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (target / "audio-manifest.json").write_text(json.dumps(audio_manifest(plan), ensure_ascii=False, indent=2), encoding="utf-8"); write_subtitles(target / "subtitles.srt", plan)
        (target / "index.html").write_text(generate_composition(plan, ASPECT_RATIOS[job["aspect"]], job["model"], job["engine"]), encoding="utf-8")
        if job["engine"] == "lottie":
            if plan.get('speech',{}).get('mode')=='tts':_build_audio(target,plan)
            lottie = generate_lottie(plan, ASPECT_RATIOS[job["aspect"]])
            (target / "lottie.json").write_text(json.dumps(lottie, ensure_ascii=False), encoding="utf-8")
            from lottie_adapter import preview
            (target / "index.html").write_text(preview(lottie), encoding="utf-8")
            meta = {"slug": target.name, "topic": job["topic"], "engine": "lottie", "model": job["model"], "style": STYLES["lottie_motion"], "aspect": ASPECT_RATIOS[job["aspect"]], "duration": plan["duration"], "fps": frame_rate.get(plan), "sceneCount": len(plan["scenes"]), "research": job["research"], "createdAt": time.time(), "formattedTime": time.strftime("%Y-%m-%d %H:%M:%S")}
            (target / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            _update_job(job_id, {"status": "succeeded", "step": "Animasi Lottie selesai", "progress": 100, "video": {"slug": target.name, "title": job["topic"], "htmlUrl": f"/api/videos/{target.name}/index.html", "lottieUrl": f"/api/videos/{target.name}/lottie.json", "voiceUrl":f"/api/videos/{target.name}/final-audio.wav" if (target/"final-audio.wav").is_file() else None, "duration": plan["duration"], "engine": "lottie"}})
            return
        engine_label = ENGINES[job['engine']]['name']
        _update_job(job_id, {"status": "rendering", "step": "Membuat musik/foley lokal tanpa dubbing" if plan.get('audioMode')=='music' or plan.get("motionDesign",{}).get("voiceMode")=="music" else "Membuat dubbing, musik, foley, dan subtitle sebelum render visual", "progress": 55})
        final_audio = _build_audio(target, plan)
        _update_job(job_id, {"step": f"Merender visual dinamis {engine_label}", "progress": 72})
        renderer = HYPERFRAMES_APP_DIR / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
        silent = target / "silent.mp4"
        motion_report=None
        remotion_report=None
        if job['engine']=='continuous':
            silent,motion_report=continuous_motion.render(target,plan,ASPECT_RATIOS[job['aspect']],
                progress=lambda fraction:_update_job(job_id,{'progress':72+round(fraction*16),'step':f'Render kontinu {round(fraction*100)}%'}))
        elif job['engine']=='remotion':
            silent,remotion_report=remotion_adapter.render(target,plan,ASPECT_RATIOS[job['aspect']])
        else:
            subprocess.run(["node", str(renderer), "render", "-o", str(silent), "--fps", str(frame_rate.get(plan)), "--workers", "1"], cwd=target, check=True, timeout=600,env=render_environment())
        _update_job(job_id, {"step": "Melakukan mux audio dan video", "progress": 90})
        output = _mux_video(target, silent, final_audio, plan["duration"])
        from video_review import review
        review_result = review(output, plan["duration"], plan)
        if remotion_report:
            review_result['remotion']=remotion_report
        if motion_report:
            motion_report['rendered_pixel_motion']=continuous_motion.pixel_motion(output)
            review_result['motion_review']=motion_report
            if motion_report['issues']:
                review_result['status']='needs_attention'
                review_result['issues'].append('Continuous motion layout needs review')
        with output.open('rb') as source:
            review_result['artifact_sha256']=hashlib.file_digest(source,'sha256').hexdigest()
        (target / "review.json").write_text(json.dumps(review_result), encoding="utf-8")
        _update_job(job_id, {"review": review_result})
        silent.unlink(missing_ok=True)
        chosen_style = STYLES.get(job.get("style")) or STYLES["threejs_3d" if job["engine"] == "threejs" else "opuscar_cinematic"]
        meta = {"slug": target.name, "topic": job["topic"], "engine": job["engine"], "model": job["model"], "style": chosen_style, "aspect": ASPECT_RATIOS[job["aspect"]], "duration": plan["duration"], "fps": frame_rate.get(plan), "sceneCount": len(plan["scenes"]), "scenePlan": plan, "research": job["research"], "audioManifest": audio_manifest(plan), "videoBytes": output.stat().st_size, "createdAt": time.time(), "formattedTime": time.strftime("%Y-%m-%d %H:%M:%S")}
        (target / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _update_job(job_id, {"status": "succeeded", "step": f"Video {engine_label} selesai", "progress": 100, "video": {"slug": target.name, "title": job["topic"], "videoUrl": f"/api/videos/{target.name}/video.mp4", "htmlUrl": f"/api/videos/{target.name}/index.html", "duration": plan["duration"], "engine": job["engine"]}})
    except Exception as exc:
        _update_job(job_id, {"status": "failed", "step": f"Gagal: {exc}", "progress": 100, "error": str(exc)})


def generate_lottie(plan: dict, aspect_info: dict) -> dict:
    from lottie_adapter import build
    return build(plan, aspect_info)
