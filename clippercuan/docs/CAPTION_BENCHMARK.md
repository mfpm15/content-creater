# Caption and Transcription Benchmark

## Scope and evidence levels

This document separates externally verifiable facts from product heuristics and proposed experiments. It does not claim that a diagnostic quality score measures word error rate because no ground-truth transcript is available during normal processing.

### Verified external facts

- YouTube supports creator-provided subtitle files and automatic captions. Automatic captions can misrepresent speech because of accents, dialects, mispronunciations, or background noise, so creators should review them.
- W3C distinguishes captions from subtitles and recommends synchronized text equivalents for spoken content and relevant non-speech audio.
- BBC subtitle guidance emphasizes readable line breaking, synchronization, adequate display time, and avoiding obscuring important visual information.
- faster-whisper exposes segment and word timestamps. Word timestamps are optional and should not be inferred from phrase timing.
- FFmpeg provides subtitle rendering, loudness, scaling, cropping, and related media filters used by the final renderer.
- Social Visuals Pro publicly markets link-to-clip automation, viral hooks, reusable dashboard workflows, and one-time pricing. Marketing claims are treated as competitor positioning, not independently measured quality.

Sources re-audited on 27 October 2026:

- https://support.google.com/youtube/answer/2734796
- https://www.w3.org/WAI/media/av/captions/
- https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/
- https://github.com/SYSTRAN/faster-whisper
- https://ffmpeg.org/ffmpeg-filters.html
- https://socialvisuals.pro/

## Diagnosis record: caption scale and template provenance

Observed facts for `validation_enhanced_v2.mp4` (27 October 2026):

- The artifact was 1080x1920 and its ASS declared `PlayResX: 1080`, `PlayResY: 1920`, Barlow Condensed ExtraBold at size 66, outline 3, and a centered position at 76 percent frame height.
- The validation script called the production `render.render_clip` function but injected an ad-hoc `enhanced_v2` dictionary. It did not resolve a named production recipe.
- The browser preview scaled the nominal caption size from preview height while ASS sizing is derived from output width. Equal nominal values at 1080x1920 therefore did not establish CSS/libass glyph parity.
- The old manifest did not identify the rendered template or expose an effective-height estimate.

Ranked hypotheses before implementation:

1. Size 66 was too small for the selected condensed face in phone playback.
2. The ad-hoc validator obscured template provenance.
3. CSS and libass font metrics made preview confidence unreliable.
4. Four-word lines and thin outline reduced perceived prominence.
5. Placement at 76 percent competed with scene and platform UI.

Implemented response:

- Animated production templates: Viral Pop (default), Box Punch, and Neon Karaoke.
- Deterministic size levels: Small 64, Medium 72, Large 84, Extra Large 96 ASS units at a 1080-wide output.
- Every render result now records template ID/name, font, nominal and effective ASS size, estimated caption height, placement, line budget, emphasis mode, source, and layer count.
- Studio preview now scales from width, matching the renderer's 1080-wide coordinate basis.
- The validation harness resolves production recipes and labels its caption-free output as a measurement reference, not an A/B candidate.

Rendered-frame validation on 27 October 2026 used twelve timestamps from the same 20.47-second source interval and a caption-free render as the pixel-difference reference. Eleven timestamps contained visible captions. Viral Pop measured a median 79 pixels (4.11 percent of 1920-pixel frame height), Box Punch measured 104 pixels (5.42 percent), and Neon Karaoke measured 77 pixels (4.01 percent). Minimum bottom clearance was 24.06 percent across all animated variants. The comparison sheet and representative full-resolution frames showed active-word emphasis, no clipping, no third line, no duplicate transcript layer, and stable placement. Viral Pop was selected as the production default after direct video review because its yellow active word, restrained glow, and pop transition supplied visual energy without the larger box footprint of Box Punch.

These measurements describe this font, source, and sample interval. They are product validation evidence, not a universal accessibility threshold. Final acceptance still requires rendered-frame inspection because glyph shape, language, and scene content vary.

## Implemented product heuristics

These thresholds are editable product rules, not universal accessibility standards:

- Diagnostic transcription score: 0 to 100 based on source type, speech coverage, available confidence, suspicious gaps, repetitions, unknown tokens, timing provenance, and implausible word rate.
- Timing provenance: `word` only when timestamps are directly available per word; synthesized phrase distribution is marked `phrase-estimated`.
- Readability warning: greater than 20 characters per second or 4.5 words per second.
- Cue duration warning: shorter than 0.5 seconds or longer than 7 seconds.
- Safe-area working default: 15 percent on every edge.
- Phrase segmentation: punctuation and pauses first, then word and character budgets, with final orphan prevention.
- Karaoke fallback: word-active styling falls back to clean phrase captions when timing is estimated.
- Contrast fallback: caption templates include an opaque or translucent background plus outline or shadow rather than relying on image content alone.
- Motion restraint: active-word scaling is capped at approximately 104 percent and transitions over 120 to 220 milliseconds.

## Reusable templates

1. Viral Pop (default)
2. Box Punch
3. Neon Karaoke
4. Bold Viral
5. Karaoke Focus
6. Podcast Quote
7. Tech Review
8. Gaming Energy
9. Minimal Lower Third

Each template stores font, size, weight, line height, foreground, background, highlight, stroke, shadow, placement, animation, safe area, line budget, and compatible content profiles.

## Quality gates

A caption workspace is blocked from a clean validation result when it contains overlapping cues, cues below the minimum duration, or more than two text lines. Other conditions produce review warnings. Auto Fix Safe Issues may change overlap boundaries, but it must not rewrite transcript text or invent word timing.

## Proposed A/B tests

These are hypotheses, not established facts:

- Clean Pro versus Bold Viral for podcast completion rate.
- Karaoke Focus versus Clean Pro when true word timing exists.
- Bottom versus middle placement for talking-head content.
- Five-word versus seven-word phrase budgets for comprehension and retention.
- Restrained 104 percent active-word motion versus static highlight.
- Domain glossary enabled versus disabled for technical terms and Mobile Legends terminology.

Primary metrics should include three-second retention, average percentage viewed, completion rate, caption correction count, export rework rate, and viewer-reported readability. Tests should use the same source clips, balanced ordering, and enough observations to avoid declaring a winner from noise.

## Known limitations

- The current score is diagnostic and cannot replace WER/CER evaluation against human-labeled ground truth.
- Browser preview approximates ASS rendering. Final acceptance must use rendered frame samples.
- Safe areas differ by platform UI, device, and placement. The 15 percent guide is conservative but not a platform guarantee.
- Automatic language detection and mixed-language warnings are script-level heuristics.
- Re-align and retranscribe actions remain explicit operations because they may be computationally expensive or download models.
