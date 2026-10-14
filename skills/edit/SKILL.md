---
name: edit
description: Edit a talking-head short (9:16) from raw phone takes with cutmate — transcribe, pick the best takes like a human editor, fact-check, cut to -14 LUFS, word-aligned captions, theme graphics (SVG/GSAP via HyperFrames), sound effects, optional music, render, QA and a thumbnail. Use when the user asks to edit / cut / make a short or reel from a folder of recordings.
---

# /cutmate:edit <folder>

Talk to the user in their language (config `language`). Never modify source clips. Everything goes to `<folder>/out/`.

Set the CLI once per session: `CM="$(command -v cutmate || echo ~/.cutmate/venv/bin/cutmate)"`; if it doesn't run, tell
the user to run `/cutmate:setup` and stop. Read the config with `cat ~/.cutmate/config.json` (backend, language, theme,
steps.factcheck / qa / thumbnail, music). Read the theme rules: `${CLAUDE_PLUGIN_ROOT}/themes/<theme>/frame.md` (or
`~/.cutmate/themes/<theme>/frame.md`) BEFORE writing plan.json. If the user uses a custom theme and it was never
checked, run `$CM theme-check --theme <theme> --language <lang>` once (renders every component and reports problems).

**Resume:** if `out/` already has files, continue from the first missing one:
`work/*/transcript.json` → `takes.md` → `edl.json` → `aroll.mp4` → `work/aligned_words.json` → `plan.json` →
`composition/index.html` → `final.mp4`.

## 1. Transcribe and look

1. Collect proper names the user mentions (products, people, tools) → `$CM transcribe <folder> --prompt "Claude, Caveman, GitHub"`.
   Results land in `out/work/<clip file name>/` (`transcript.json`, `silences.json`, `<stem>.wav`). Words come with
   times; `SUSPECT long word` lines mark windows that hide a stumble or a retake.
2. For every clip: `$CM sheet <clip> -o <folder>/out/sheets/<clip>.png --step 0.5` and READ the sheet image(s). Note where
   the speaker looks away, reads notes, the framing jumps (stabilisation), or they point at something.

## 2. Pick takes (the most important step — be an editor, not a transcriber)

The transcript lies: whisper drops false starts and merges a stumble + retake into one long word. For EVERY segment you
might use:

- Probe every `SUSPECT` word and every speech region the transcript doesn't explain:
  `$CM probe <folder>/out/work/<clip>/<stem>.wav --start A --end B --prompt "Yyy, eee, hmm."` (≈1 s windows).
- RMS-scan the segment: `$CM rms <wav> --start A --end B --bin 0.05` — two speech blobs inside one "word", a blob
  with no word, or a short spike after a word (mouth click) are retakes / stumbles / smacks.
- Never use a segment where the sheet shows looking away or a framing jump; cut around it.
- For each line said more than once, compare ALL takes. Write `out/takes.md`: every repeated line, every take
  (clip + times), the chosen one marked, and one-line reason (delivery / energy / fluency / no stumble / eye contact).

Write `out/edl.json`:
```json
{"format": "9:16", "fps": 30,
 "segments": [{"id": "S1", "file": "IMG_6048.MOV", "in": 1.83, "out": 12.22, "text": "corrected text, exactly as said"}],
 "spoken": {"Claude": "klod", "75%": "siedemdziesiąt pięć procent"}}
```
- Strongest line first as the hook; end on a closing line.
- Cut on silence bounds (`work/<clip>/silences.json`): `in ≈ speech start − 0.06`, `out ≈ speech end + 0.08`.
  Keep ≥ 0.2 s after the last loud bin of a word ending in a quiet consonant (ć, ś, t, k).
- `text` is the caption source of truth: fix spelling of names, never change what was said.
- `spoken`: how numbers and foreign words are pronounced, for alignment.

## 3. Fact-check (only if `steps.factcheck` is true)

List every checkable claim (numbers, prices, dates, versions, names, "first / only / free"). Verify each with
WebSearch AND by opening the source page (official docs, pricing, changelog, repo; studies for health; law texts for law).
Write `out/factcheck.md`, one line per claim: timestamp, quote, verdict ✅ OK / ⚠️ NIEPEWNE / ❌ BŁĄD, the true version,
link. If anything is ❌ or ⚠️: STOP and ask the user (this is the only pause): another take that says it right / cut
the line / re-record / keep it with an on-screen correction. If all ✅: say it in one line and continue.
(`build` warns about any counter / non-illustrative bars number that no ✅ line confirms.)

## 4. Cut and align

`$CM cut <folder>/out/edl.json` then `$CM align <folder>/out/edl.json`. Read `work/aligned_words.json`; any
`(estimated)` words mean a segment's text doesn't match its audio — fix the EDL text.

## 5. Plan the graphics

Follow `frame.md`. Write `out/plan.json`:
```json
{"captions": {"key": ["CLAUDE", "CAVEMAN"]},
 "graphics": [
   {"type": "counter", "at": "S2:75", "to": 75, "prefix": "-", "suffix": "%", "label": "TOKENÓW", "hit": true},
   {"type": "split", "from": "S5:Po", "to": "S5:zwięźle.", "media": "broll/caveman-repo.png"}],
 "music": {"volume": 0.45}}
```
- Anchors: `"S2:word"` (first occurrence in segment S2), `"S2:word#2"` (second), or seconds into the video. `"S2:75"`
  also matches the spoken `75%`. Optional on any graphic: `until` (anchor or seconds), `hit`, `sfx`.
- Components: `title` (at, text, kicker?, logo?), `counter` (at, to, prefix?, suffix?, label), `list` (items[{text, at}],
  head?), `chip` (at, text, logo?/icon?), `stamp` (at, one-word text), `bars` (at, head, rows[{label, value}],
  illustrative), `point` (at, image, corner tl/tr/bl/br), `split` (from, to, media).
- Limits enforced by the planner: a `list` has at most 4 items, `bars` at most 3 rows, `stamp` is exactly one word,
  `counter.to` is a number. Budgets (warnings): at most 2 graphics with `hit`, 1 `title`, no overlapping graphics.
- B-roll: files in `<folder>/broll/`; for a web page the speaker talks about: `$CM shot <url> -o <folder>/broll/<name>.png`
  and READ the PNG (cookie banners, login walls → pick another page or crop).
- Music: config `music.source` = `folder` → automatic (first audio file in the folder); `heygen` →
  `npx hyperframes media-use resolve --type bgm --intent "<mood>" --project <folder>/out/composition`
  only if the user is signed in (never sign in for them), then put the file path in `plan.music.src`; `none` → no music.

## 6. Build and look

`$CM build <folder>/out` — fix every `cutmate:` error (it names the bad anchor and lists the segment's words) and think
about every `WARN`. The last line prints `checkpoints: t1,t2,...`. Then, from the project dir (no path argument):
`cd <folder>/out/composition && npx --yes hyperframes@0.8.157 snapshot --at <checkpoints> --no-end --describe false -o ../snapshots`
and READ every frame: overlaps, text wrapping, safe zones, captions readable, split panel shows the media. Fix
`plan.json` and rebuild until clean. Stop any running `hyperframes preview` before rebuilding.

## 7. Render and QA

`$CM render <folder>/out` (check → render → finalize; ~1–2 min; writes `out/final.mp4`). READ every `check_*.png` it
writes and describe each in one line. If `steps.qa`: `$CM qa <folder>/out` and handle every hit: listen/probe, fix the
EDL (then cut → align → build → render; graphics move with their words automatically) or explain why it's fine.

## 8. Thumbnail (if `steps.thumbnail`)

Pick a frame with a strong expression from a sheet of `out/final.mp4` (`$CM sheet <folder>/out/final.mp4 -o <folder>/out/sheets/final.png`);
`--at` is seconds into `final.mp4`. Title = the PROMISE of the short (not the product name), hook = the short's hook
question. Keep the title short (it wraps to at most 3 lines) and the hook to 2 lines:
`$CM thumb <folder>/out --at <t> --title "SAME KONKRETY" --hook "Czy Caveman dalej działa?"`
(writes `out/thumbnail.png` and `.jpg`). READ the PNG; redo with another frame if the face is covered.

## 9. Notes and hand-off

Write `out/EDIT_NOTES.md`: final structure (segments in order with times), which graphic is where and why, music,
commands used. Send the user `final.mp4` (and the thumbnail). When they reply with timestamps, batch all changes into
one rebuild + one render.
