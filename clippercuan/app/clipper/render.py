"""Render satu klip: potong → framing (crop/blur/split) → caption/judul/watermark → MP4 H.264."""
from __future__ import annotations

from pathlib import Path

from . import captions, effects, facetrack
from .config import FONTS_DIR, SIZES
from .recipes import RECIPES

QUALITY = {"1080": 1.0, "1440": 4 / 3, "2160": 2.0}   # sisi pendek output: 1080p, 1440p (2K), 2160p (4K)


def out_size(layout: str, cfg: dict) -> tuple[int, int]:
    """Ukuran output sesuai pilihan kualitas (portrait 4K = 2160×3840)."""
    k = QUALITY.get(str((cfg.get("quality") or {}).get("output", "1080")), 1.0)
    w, h = SIZES[layout]
    return _even(w * k), _even(h * k)


_TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
from . import media
from .media import Probe, grab_frame, run


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _fpath(p: Path | str) -> str:
    """Path aman untuk argumen filter ffmpeg (Windows: C\\:/...)."""
    return "'" + str(p).replace("\\", "/").replace(":", "\\:").replace("'", r"\'") + "'"


def clip_words(words: list[dict], start: float, end: float) -> list[dict]:
    return [{"w": w["w"], "s": round(w["s"] - start, 3), "e": round(w["e"] - start, 3)}
            for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.3]


def cut_plan(words: list[dict], dur: float, gap: float = 0.55, pad: float = 0.12) -> list[tuple[float, float]]:
    """Rentang yang dipertahankan saat 'potong jeda hening' (berdasar timestamp kata)."""
    if not words:
        return [(0.0, dur)]
    ranges: list[list[float]] = []
    for w in words:
        a, b = max(0.0, w["s"] - pad), min(dur, w["e"] + pad)
        if ranges and a - ranges[-1][1] < gap:
            ranges[-1][1] = max(ranges[-1][1], b)
        else:
            ranges.append([a, b])
    ranges[0][0] = 0.0 if ranges[0][0] < 0.4 else ranges[0][0]
    return [(round(a, 3), round(b, 3)) for a, b in ranges if b - a > 0.05]


def remap(t: float, plan: list[tuple[float, float]]) -> float:
    """Waktu di klip asli → waktu setelah jeda dipotong."""
    acc = 0.0
    for a, b in plan:
        if t < a:
            return acc
        if t <= b:
            return acc + t - a
        acc += b - a
    return acc


def upscale_factor(layout: str, pr: Probe, cfg: dict) -> float:
    """Seberapa besar area sumber diperbesar ke output (>1,3 = mulai terlihat lembek/"burik")."""
    Wt, Ht = out_size(layout, cfg)
    W, H = pr.width, pr.height
    if layout in ("portrait", "square"):
        zoom = max(1.0, min(3.0, float((cfg.get("crop") or {}).get("zoom", 1) or 1)))
        ch = H / zoom if W / H > Wt / Ht else (W / zoom) / (Wt / Ht)
        return Ht / max(ch, 1)
    if layout == "split":
        return Wt / max(W * float((cfg.get("split") or {}).get("game", [0, 0, 1, 1])[2]), 1)
    return min(Wt / W, Ht / H) if layout in ("blur", "landscape") else 1.0


def _quality_warning(up: float, pr: Probe, size: tuple[int, int]) -> list[str]:
    if up <= 1.3:
        return []
    if pr.height >= 2160:  # 16:9 → 9:16: tinggi crop = tinggi sumber, jadi output 4K portrait selalu diperbesar
        return [f"Output {size[1]}p portrait dari sumber {pr.height}p diperbesar {up:.1f}×; 1080p/1440p memberi detail per piksel terbaik"]
    return [f"Sumber {pr.height}p diperbesar {up:.1f}× — pakai sumber 1440p/4K (Pengaturan kualitas) agar lebih tajam"]


def _sharp(factor: float) -> str:
    """Penajaman ringan setelah upscale agar tidak lembek (tanpa artefak halo)."""
    if factor <= 1.15:
        return ""
    amount = min(0.9, 0.35 + (factor - 1.15) * 0.4)
    return f",unsharp=5:5:{amount:.2f}:5:5:0"


def framing_filter(layout: str, pr: Probe, cfg: dict, keys: list | None, inp: str = "0:v") -> str:
    """Filtergraph dari [inp] ke [fr]."""
    Wt, Ht = out_size(layout, cfg)
    W, H = pr.width, pr.height
    sh = _sharp(upscale_factor(layout, pr, cfg)) if (cfg.get("quality") or {}).get("sharpen", True) else ""
    if pr.hdr and media.has_filter("zscale") and media.has_filter("tonemap"):  # sumber HDR (mis. YouTube 4K HDR) → SDR agar warna tidak pucat
        tm = f"[{inp}]{_TONEMAP.rstrip(',')}[sdr];"
        inp = "sdr"
    else:
        tm = ""
    if layout in ("portrait", "square"):
        a = Wt / Ht
        cr = cfg.get("crop") or {}
        zoom = max(1.0, min(3.0, float(cr.get("zoom", 1) or 1)))       # >1 = jendela crop lebih kecil (lewati watermark/bar)
        cy = max(0.0, min(1.0, float(cr.get("y", 0.5) if cr.get("y") is not None else 0.5)))
        hold = bool(cr.get("hold"))
        if W / H > a:  # sumber lebih lebar → crop horizontal (bisa ikut wajah)
            ch = _even(H / zoom)
            cw = _even(ch * a)
            x = facetrack.x_expr(keys, W, cw, hold) if keys else f"{(W - cw) / 2:.1f}"
            y = f"{(H - ch) * cy:.1f}"
            return tm + f"[{inp}]crop=w={cw}:h={ch}:x='{x}':y={y},scale={Wt}:{Ht}:flags=lanczos{sh},setsar=1[fr]"
        cw = _even(W / zoom)
        ch = _even(cw / a)
        return tm + f"[{inp}]crop=w={cw}:h={ch}:x={(W - cw) / 2:.1f}:y={(H - ch) * cy:.1f},scale={Wt}:{Ht}:flags=lanczos{sh},setsar=1[fr]"
    if layout == "blur":
        return tm + (f"[{inp}]split[a][b];[a]scale={Wt // 4}:{Ht // 4}:force_original_aspect_ratio=increase,crop={Wt // 4}:{Ht // 4},"
                f"boxblur=10:2,scale={Wt}:{Ht},eq=brightness=-0.07:saturation=1.2[bg];"
                f"[b]scale={Wt}:{Ht}:force_original_aspect_ratio=decrease:flags=lanczos{sh}[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[fr]")
    if layout == "split":
        sp = cfg["split"]
        hf = _even(Ht * float(sp.get("face_ratio", 0.4)))
        hg = Ht - hf

        def rect(r):
            x, y, w, h = [float(v) for v in r]
            w, h = max(min(w, 1 - x), 0.05), max(min(h, 1 - y), 0.05)
            return f"crop={_even(W * w)}:{_even(H * h)}:{int(W * x)}:{int(H * y)}"

        return tm + (f"[{inp}]split[a][b];[a]{rect(sp['face'])},scale={Wt}:{hf}:force_original_aspect_ratio=increase:flags=lanczos,crop={Wt}:{hf}{sh}[top];"
                f"[b]{rect(sp['game'])},scale={Wt}:{hg}:force_original_aspect_ratio=increase:flags=lanczos,crop={Wt}:{hg}{sh}[bot];"
                f"[top][bot]vstack,setsar=1[fr]")
    # landscape
    return tm + (f"[{inp}]scale={Wt}:{Ht}:force_original_aspect_ratio=decrease:flags=lanczos{sh},"
                 f"pad={Wt}:{Ht}:(ow-iw)/2:(oh-ih)/2,setsar=1[fr]")


def render_clip(work: Path, src: Path, pr: Probe, clip: dict, cfg: dict, words: list[dict]) -> dict:
    """Tulis clip_XX.mp4 + .jpg di `work`; kembalikan field yang diperbarui."""
    cid = clip["id"]
    start, end = float(clip["start"]), float(clip["end"])
    dur = max(end - start, 0.5)
    layout = cfg["layout"]
    size = out_size(layout, cfg)

    keys = clip.get("crop_keys")
    if layout in ("portrait", "square") and cfg.get("smart_crop") and not keys and pr.width / pr.height > SIZES[layout][0] / SIZES[layout][1]:
        keys = facetrack.track(src, start, end, pr.width, pr.height)
    cw = clip_words(words, start, end) if clip.get("words") is None else clip["words"]

    # potong jeda hening: susun ulang waktu kata & keyframe ke timeline baru
    plan = cut_plan(cw, dur, float(cfg.get("silence_gap", 0.55))) if cfg.get("cut_silence") and cw else [(0.0, dur)]
    cut = len(plan) > 1 or plan[0][0] > 0.01 or plan[0][1] < dur - 0.01
    out_dur = sum(b - a for a, b in plan)
    sub_words = [{**w, "s": round(remap(w["s"], plan), 3), "e": round(remap(w["e"], plan), 3)} for w in cw] if cut else cw
    sub_keys = [[round(remap(t, plan), 2), x] for t, x in keys] if (cut and keys) else keys

    ass_name = f"{cid}.ass"
    if cfg.get("source_has_burned_captions") == "yes":
        cfg = {**cfg, "caption": {**cfg["caption"], "enabled": False}}
    # ASS harus berada di work selama FFmpeg berjalan. Ekspor subtitle dipindahkan
    # sesudah render agar player tidak memuat sidecar bernama sama dengan MP4 burned-in.
    ass_path = work / ass_name
    srt_path = work / f"{cid}.srt"
    ass_path.write_text(captions.build_ass(sub_words, clip.get("title", ""), cfg, size, out_dur), "utf-8")
    srt_path.write_text(captions.build_srt(sub_words, int(cfg["caption"].get("words_per_line", 3))), "utf-8")

    wm = cfg["watermark"]
    use_img = wm["enabled"] and wm.get("image") and Path(wm["image"]).is_file()
    if cut:
        n = len(plan)
        vs = "".join(f"[cv{i}]" for i in range(n))
        graph = (f"[0:v]split={n}{vs};" if n > 1 else "[0:v]null[cv0];")
        graph += "".join(f"[cv{i}]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(plan))
        if pr.has_audio:
            as_ = "".join(f"[ca{i}]" for i in range(n))
            graph += (f"[0:a:0]asplit={n}{as_};" if n > 1 else "[0:a:0]anull[ca0];")
            graph += "".join(f"[ca{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}];" for i, (a, b) in enumerate(plan))
            graph += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];"
        else:
            graph += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc];"
        graph += framing_filter(layout, pr, cfg, sub_keys, "vc")
    else:
        graph = framing_filter(layout, pr, cfg, keys)
    fonts = f":fontsdir={_fpath(FONTS_DIR)}" if FONTS_DIR.is_dir() else ""
    graph += f";[fr]ass=filename={ass_name}{fonts}[cap]"
    last = "cap"
    extra_inputs: list[list[str]] = []

    def add_input(opts: list[str]) -> int:
        extra_inputs.append(opts)
        return len(extra_inputs)  # indeks input ffmpeg (0 = video sumber)

    W, H = size
    if use_img:
        idx = add_input(["-i", str(wm["image"])])
        mw = int(W * 0.18 * wm.get("size", 42) / 42)
        m = 40
        pos = {"tl": f"{m}:{m}", "tr": f"W-w-{m}:{m}", "bl": f"{m}:H-h-{m}", "br": f"W-w-{m}:H-h-{m}", "c": "(W-w)/2:(H-h)/2"}[wm.get("position", "br")]
        graph += (f";[{idx}:v]scale={mw}:-1,format=rgba,colorchannelmixer=aa={float(wm.get('opacity', .8)):.2f}[wm];"
                  f"[{last}][wm]overlay={pos}[wmo]")
        last = "wmo"

    # emoji otomatis dari kata kunci (PNG di atas caption, muncul halus)
    emojis = effects.plan_emojis(sub_words, out_dur) if cfg.get("emoji", {}).get("enabled") else []
    if emojis:
        es = int(170 * W / 1080 * float(cfg["emoji"].get("size", 1.0)))
        cap_pos = cfg["caption"].get("position", "bottom")
        if cfg["caption"].get("y_pct") not in (None, ""):   # emoji tepat di atas caption yang diposisikan bebas
            cap_fs = int(float(cfg["caption"].get("size", 82)) * W / 1080)
            ey = max(0, int(H * float(cfg["caption"]["y_pct"]) / 100) - int(cap_fs * 0.9) - es)
        else:
            ey = {"bottom": int(H * 0.60), "middle": int(H * 0.36), "top": int(H * 0.30)}[cap_pos] - es
        for k, em in enumerate(emojis):
            idx = add_input(["-loop", "1", "-framerate", "30", "-t", f"{em['e'] + 0.2:.2f}", "-i", em["file"]])
            d = em["e"] - em["s"]
            graph += (f";[{idx}:v]scale={es}:{es},format=rgba,fade=t=in:st={em['s']:.2f}:d=0.15:alpha=1,"
                      f"fade=t=out:st={em['s'] + d - 0.2:.2f}:d=0.2:alpha=1[em{k}];"
                      f"[{last}][em{k}]overlay=x=(W-w)/2:y={ey}:eof_action=pass:enable='between(t,{em['s']:.2f},{em['e']:.2f})'[e{k}]")
            last = f"e{k}"

    # progress bar tipis yang berjalan sepanjang klip
    pb = cfg.get("progress_bar", {})
    if pb.get("enabled"):
        ph = max(int(pb.get("height", 12) * W / 1080), 4)
        col = "0x" + pb.get("color", "#FFC933").lstrip("#")[:6]
        y = "0" if pb.get("position") == "top" else f"{H - ph}"
        graph += (f";color=c={col}:s={W}x{ph}:r=30:d={out_dur:.3f}[pbar];"
                  f"[{last}][pbar]overlay=x='-w+w*t/{out_dur:.3f}':y={y}:eof_action=pass[pbo]")
        last = "pbo"

    # audio: suara asli (+ potong jeda) dan musik latar dengan ducking otomatis
    mu = cfg.get("music", {})
    music_file = mu.get("file") if mu.get("enabled") else None
    use_music = bool(music_file) and Path(music_file).is_file()
    orig = ("[ac]" if cut else "[0:a:0]") if pr.has_audio else None
    audio_map = None
    if use_music:
        idx = add_input(["-stream_loop", "-1", "-i", str(music_file)])
        vol = float(mu.get("volume", 0.15))
        fade_out = max(out_dur - 1.5, 0)
        graph += (f";[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol:.3f},atrim=0:{out_dur:.3f},"
                  f"afade=t=in:d=0.8,afade=t=out:st={fade_out:.2f}:d=1.5[mus]")
        if orig and mu.get("duck", True):
            graph += (f";{orig}aformat=sample_rates=48000:channel_layouts=stereo,asplit[o1][o2];"
                      f"[mus][o2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[dk];"
                      f"[o1][dk]amix=inputs=2:duration=first:normalize=0[aout]")
        elif orig:
            graph += f";{orig}aformat=sample_rates=48000:channel_layouts=stereo[o1];[o1][mus]amix=inputs=2:duration=first:normalize=0[aout]"
        else:
            graph += ";[mus]anull[aout]"
        audio_map = "[aout]"
    elif orig:
        audio = cfg.get("audio", {})
        if audio.get("normalize", True):
            target = max(-24.0, min(-12.0, float(audio.get("target_lufs", -16))))
            peak = max(-3.0, min(-1.0, float(audio.get("true_peak", -1.5))))
            graph += f";{orig}loudnorm=I={target}:TP={peak}:LRA=11[aout]"
            audio_map = "[aout]"
        else:
            audio_map = "[ac]" if cut else "0:a:0?"

    out = work / f"{cid}.mp4"
    tmp = work / f"{cid}.tmp.mp4"
    args = ["-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
    for opts in extra_inputs:
        args += opts
    args += ["-filter_complex", graph, "-map", f"[{last}]"]
    if audio_map:
        args += ["-map", audio_map, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        args += ["-an"]
    enc, vargs = media.video_codec_args(size[1], str((cfg.get("quality") or {}).get("encoder", "auto")))
    tail = ["-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-r", f"{min(pr.fps, 60):.3f}", "-movflags", "+faststart", "-t", f"{out_dur:.3f}", tmp.name]
    try:
        run(args + vargs + tail, cwd=work)
    except media.FFmpegError:
        if enc == "libx264":
            raise
        media.mark_hw_broken(enc)                       # encoder hardware gagal → ulangi dengan CPU
        enc, vargs = media.video_codec_args(size[1], "cpu")
        run(args + vargs + tail, cwd=work)
    tmp.replace(out)
    subtitle_dir = work / "subtitles"
    subtitle_dir.mkdir(exist_ok=True)
    exported_ass = subtitle_dir / ass_name
    exported_srt = subtitle_dir / f"{cid}.srt"
    if exported_ass.exists():
        exported_ass.unlink()
    if exported_srt.exists():
        exported_srt.unlink()
    ass_path.replace(exported_ass)
    srt_path.replace(exported_srt)
    grab_frame(out, min(1.0, out_dur / 2), work / f"{cid}.jpg", width=540)
    up = upscale_factor(layout, pr, cfg)
    smart = layout in ("portrait", "square") and cfg.get("smart_crop") and pr.width / pr.height > SIZES[layout][0] / SIZES[layout][1]
    cap = cfg["caption"]
    template_id = cap.get("template_id") or cap.get("preset") or ("none/raw" if not cap.get("enabled") else "custom")
    template_name = next((r.get("template_name") or r["label"] for r in RECIPES.values()
                          if r["settings"].get("caption", {}).get("template_id") == template_id),
                         "Tanpa caption" if template_id == "none/raw" else "Konfigurasi kustom")
    effective_units = int(float(cap.get("size", 0)) * size[0] / 1080) if cap.get("enabled") else 0
    estimated_height = effective_units * float(cap.get("line_height", 1.12)) + 2 * int(float(cap.get("outline", 0)) * size[0] / 1080)
    caption_meta = {"template_id": template_id, "template_name": template_name, "font": cap.get("font"),
                    "caption_size_preset": cap.get("size_level", "custom"),
                    "size_level": cap.get("size_level", "custom"), "ass_size": cap.get("size"),
                    "effective_ass_size": effective_units, "effective_caption_height_px_estimate": round(estimated_height, 1),
                    "effective_caption_height_pct": round(estimated_height / size[1] * 100, 2),
                    "position": cap.get("position"), "y_pct": cap.get("y_pct"), "max_lines": cap.get("max_lines", 2),
                    "line_height": cap.get("line_height", 1.12), "style": cap.get("style"),
                    "animation": cap.get("animation", "none"), "effect": cap.get("effect", "none"),
                    "active_word": cap.get("style") in {"karaoke", "box"} or bool(cap.get("box")),
                    "emphasis_mode": "box" if cap.get("style") == "box" or cap.get("box") else "active-word" if cap.get("style") == "karaoke" else cap.get("accent_mode") if cap.get("style") == "keyword" else "none",
                    "caption_source": "transcript", "caption_layers": 1,
                    "burned_in": bool(cap.get("enabled")), "sidecar_autoload_safe": True}
    crop_confidence = (0.0 if not keys else min(1.0, max(.35, len(keys) / max(out_dur / 4, 1)))) if smart else 1.0
    return {"file": out.name, "thumb": f"{cid}.jpg", "srt": f"subtitles/{cid}.srt",
            "ass": f"subtitles/{cid}.ass", "sidecar_autoload_safe": True,
            "crop_keys": keys, "words": cw,
            "duration": round(out_dur, 2), "cut_saved": round(dur - out_dur, 2), "emojis": [e["code"] for e in emojis],
            "caption_cues": len(captions.chunk_words(sub_words, int(cfg["caption"].get("words_per_line", 3)))),
            "caption_layers": 1, "caption_provenance": "ASS:spoken-caption",
            "caption_size_preset": caption_meta["caption_size_preset"],
            "burned_in": caption_meta["burned_in"], "caption_render": caption_meta,
            "template_id": template_id, "template_name": template_name,
            "effective_caption_height_pct": caption_meta["effective_caption_height_pct"],
            "hook_provenance": "ASS:hook" if cfg["title"].get("enabled") else None,
            "source_has_burned_captions": cfg.get("source_has_burned_captions", "unknown"),
            "crop_confidence": round(crop_confidence, 2),
            "resolution": f"{size[0]}x{size[1]}", "encoder": enc, "upscale": round(up, 2),
            "render_warnings": (["Crop confidence rendah — cek framing di Crop studio"] if smart and crop_confidence < .5 else [])
            + (["Potensi subtitle ganda: status caption bawaan sumber belum diketahui"]
               if cfg.get("source_has_burned_captions", "unknown") == "unknown" else [])
            + _quality_warning(up, pr, size)}
