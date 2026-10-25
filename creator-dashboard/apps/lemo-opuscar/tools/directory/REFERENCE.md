# Opuscar High-Quality Production Reference

## Production contract

- Product, engine, workflow, and UI identity remain Opuscar-only.
- HyperFrames CLI may be used only as deterministic frame renderer.
- Preserve user narration, facts, numbers, spelling, and ordering verbatim.
- For Indonesian narration, use Microsoft Edge TTS only after explicit consent.
- Standard output: 1080x1920, 30 fps, 60 seconds, H.264/AAC, subtitles burned in and exported as SRT.
- Target integrated loudness: about -14 LUFS with true peak no higher than -1.5 dBTP.

## Six-scene cybersecurity preset

| Scene | Timecode | Visual grammar | Foley |
|---|---:|---|---|
| Threat | 0-10 | Video-call face fragments into red code | emergency notification |
| Opportunity | 10-25 | Rising blue chart, shield protects office | keyboard, shield clang |
| Detect | 25-35 | AI security dashboard blocks red node | scan beep |
| Zero Trust | 35-45 | Phone lock, face and fingerprint scan | unlock click |
| PDP | 45-53 | Workers and data-protection certificate | paper |
| Action | 53-60 | Presenter silhouette and follow action | music peak, firm stop |

## Direction models

Call each model through the local OpenAI-compatible endpoint `http://localhost:20128/v1`:

- `ms/GPT-5.6-Think-Deeper`
- `cc/claude-opus-5-5`
- `cc/claude-sonnet-5-5`

Models may vary palette, camera movement, composition, and pacing. They must not rewrite narration or alter user facts.

## Audio pipeline

1. Generate one Edge TTS file per scene using `id-ID-ArdiNeural` or another `id-ID` neural voice.
2. Fit each voice clip within its scene without truncating words.
3. Generate original electronic music and procedural foley locally.
4. Duck music under voice with FFmpeg `sidechaincompress` or equivalent automation.
5. Mix voice, music, and foley, then normalize with `loudnorm` near -14 LUFS.
6. Mux rendered frames and final audio into H.264/AAC MP4.

## Validation

- Run `py -m unittest test_video_drafter.py`.
- Confirm exact duration and audio/video streams using `ffprobe`.
- Reject empty or implausibly small MP4 files.
- Extract frames around 2, 12, 27, 37, 47, and 55 seconds.
- Build a contact sheet and inspect text legibility, scene uniqueness, subtitle safety, and black frames.
- Keep `direction.json`, `index.html`, `subtitles.srt`, `metadata.json`, contact sheet, and final MP4 in each model output folder.
