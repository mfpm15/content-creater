---
name: lemo-opuscar
description: Produces high-quality code-directed Opuscar films with procedural visuals, narration, subtitles, original sound design, mixing, rendering, and validation. Use when a user requests an Opuscar video, explainer, animation, or model-directed short film; not for trimming or converting existing video.
---

# Lemo-Opuscar Production

## Quick start

1. Read the user brief and preserve supplied facts, numbers, and narration verbatim.
2. Run `sh "<skill base directory>/scripts/setup.sh" deps`; add voice or music tiers only when needed.
3. Read the working library's `AGENTS.md`, `DIRECTOR.md`, and relevant `STYLE.md`.
4. Write treatment before inspecting demo material.
5. Produce and validate the film. HyperFrames may render frames, but product and workflow remain Opuscar.

## Workflow

- Confirm style, duration, aspect, language, assets, and online TTS consent in one round.
- Use Microsoft Edge TTS only after explicit consent because narration text is sent to Microsoft.
- Keep narration and subtitle source text unchanged unless user explicitly requests editing.
- Build layered procedural scenes with clear foreground, midground, background, camera intent, and informative typography.
- Add burned-in subtitles plus SRT, original score, action-linked foley, voice ducking, and loudness normalization.
- Review sampled frames/contact sheet and full audio before delivery.
- Validate duration, audio/video streams, file size, black frames, subtitle safety, and about -14 LUFS.

## Cybersecurity 60-second preset

Use six fixed scenes: `0-10`, `10-25`, `25-35`, `35-45`, `45-53`, `53-60`. Include emergency notification, keyboard, shield clang, scan beep, unlock click, and paper foley when requested.

## Resources

See [REFERENCE.md](REFERENCE.md) for model routing, scene grammar, audio pipeline, output contract, and validation commands.
