---
name: edit
description: Edit a talking-head short (9:16) or a YouTube long-form video (16:9) from raw takes with cutmate — transcribe, pick the best takes like a human editor, fact-check, cut to -14 LUFS, word-aligned captions, theme graphics (SVG/GSAP via HyperFrames), sound effects, optional music, render, QA and a thumbnail. Use when the user asks to edit / cut / make a short, reel or long-form video from a folder of recordings.
---

# /cutmate:edit <folder>

Talk to the user in their language (config `language`). Never modify source clips. Everything goes to `<folder>/out/`.

Set the CLI once per session: `CM="$(command -v cutmate || ls ~/.cutmate/venv/bin/cutmate ~/.cutmate/venv/Scripts/cutmate.exe 2>/dev/null | head -1)"`; if it doesn't run, tell
the user to run `/cutmate:setup` and stop. Read the config with `cat ~/.cutmate/config.json` (backend, language, theme,
steps.factcheck / qa / thumbnail, music). Read the theme rules: `${CLAUDE_PLUGIN_ROOT}/themes/<theme>/frame.md` (or
`~/.cutmate/themes/<theme>/frame.md`) BEFORE writing plan.json. If the user uses a custom theme and it was never
checked, run `$CM theme-check --theme <theme> --language <lang>` once (renders every component and reports problems).

**Resume:** if `out/` already has files, continue from the first missing one:
`work/*/transcript.json` → `sheets/*.png` → `outline.md` (16:9) → `takes.md` → `edl.json` → `aroll.mp4` →
`work/aligned_words.json` → `plan.json` → `preview.mp4` (16:9) → `composition/index.html` → `final.mp4` → `thumbnail.png` (if `steps.thumbnail`) → `EDIT_NOTES.md`.
Resuming at `takes.md` means (re)making and READING the sheets first.

## 1. Transcribe and look

1. Collect proper names the user mentions (products, people, tools) → `$CM transcribe <folder> --prompt "Claude, Caveman, GitHub"`.
   Results land in `out/work/<clip file name>/` (`transcript.json`, `silences.json`, `<stem>.wav`). Words come with
   times; `SUSPECT long word` lines mark windows that hide a stumble or a retake.
2. For every clip: `$CM sheet <clip> -o <folder>/out/sheets/<clip>.png --step 0.5` and READ the sheet image(s). Note where
   the speaker looks away, reads notes, the framing jumps (stabilisation), or they point at something.
3. Run `$CM formats <folder>` (`cutmate formats` is rotation-aware; last line `format: 9:16 | 16:9 | mixed`). All `16:9` →
   long-form branch (section 1b); all `9:16` → short; `mixed` → ask the user once which format to make. Put the format
   in `edl.json` (`"format": "16:9"`).

## 1b. 16:9 long-form — what changes

Everything else in this skill applies; these are the differences.

- **Outline first:** write `out/outline.md`: the chapters (title ≤ 40 chars, what is said, which clips and time ranges).
- **Takes per chapter in parallel:** dispatch one subagent per chapter (Agent tool, all in one message) with: the folder,
  the CLI path, that chapter's clips and ranges, the sheet notes, and the whole of section 2 of this skill verbatim. Each
  returns its part of `takes.md` (repeated lines + Checks) and its segment list. Merge into one `takes.md` and one
  `edl.json` (ids S1… in video order). Never skip the Checks — same rule as shorts. Cut mid-sentence only on a pause
  ≥ 0.25 s. Keep the intro in place (no hook reshuffle unless one line is clearly the strongest opener).
- **plan.json:** follow the `## 16:9` section of `frame.md`. Add `"chapters": [{"at": "S1:word", "title": "…"}]` (plates
  for chapters 2+) and `"face": {"S1": [x, y], …}` for EVERY segment (face position from the sheets, fractions 0–1).
  Components: `pip` (instead of `split`; `from`, `to`, `media`, `corner?` br|bl, `fit?` cover|contain), `lower-third`
  (`at`, `name`, `role?`) once at the self-introduction, corner graphics as usual. `split` is an error in 16:9.
- **Checkpoint before the full render (always):** `$CM preview <folder>/out` → send the user `out/preview.mp4` and the
  `chapters.txt` lines; wait for OK. Changes → EDL / plan → new preview. Only then build, snapshot, render (a 15-minute
  video renders for ~45–60 min; tell the user).
- **Outputs:** `final.mp4`, `chapters.txt` (paste into the YouTube description), `captions.srt` when the config's caption
  mode for 16:9 is `srt`/`both` (upload in YouTube Studio), thumbnail.
- **Thumbnail:** 1280×720; pick a frame where the face is on one side and put the text on the other:
  `$CM thumb <folder>/out --at <t> --title "…" --hook "…" --side left|right`.
- Custom theme: `$CM theme-check --theme <theme> --language <lang> --format 16:9`.

## 2. Pick takes (the most important step — be an editor, not a transcriber)

The transcript lies: whisper drops false starts and merges a stumble + retake into one long word. For EVERY segment you
might use:

- Probe every `SUSPECT` word and every unexplained speech region. Unexplained speech = a non-silent span (a gap
  between entries in `silences.json`) longer than ~0.3 s with no words in the transcript. Probe in ≈1 s windows:
  `$CM probe <folder>/out/work/<clip>/<stem>.wav --start A --end B --prompt "Yyy, eee, hmm."`
  (language `en`: `--prompt "Um, uh, er, hmm."`).
- RMS-scan the segment: `$CM rms <wav> --start A --end B --bin 0.05` — two speech blobs inside one "word", a blob
  with no word, or a short spike after a word (mouth click) are retakes / stumbles / smacks.
- Never use a segment where the sheet shows looking away or a framing jump; cut around it. Framing jumps can last
  < 0.5 s: before finalising each segment make a dense sheet of it
  (`$CM sheet <clip> --start A --end B --step 0.1 -o <folder>/out/sheets/<clip>-<A>.png`) and READ it.
- For each line said more than once, compare ALL takes.

Write `out/takes.md` with two parts:
1. Repeated lines: every take (clip + times), the chosen one marked, and a one-line reason (delivery / energy /
   fluency / no stumble / eye contact).
2. **Checks — one entry for EVERY segment used in the EDL (repeated or not):** each SUSPECT window probed and what
   came back; the RMS range scanned and the findings; the look-away / framing-jump time ranges excluded (from the sheets).

Do not write `edl.json` until every planned segment has a checks entry.

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
Write `out/factcheck.md`, one line per claim: timestamp, quote, verdict (✅ / ⚠️ / ❌ plus the word in the user's
language, e.g. OK / NIEPEWNE / BŁĄD), the true version, link. If anything is ❌ or ⚠️: STOP and ask the user (this is the only pause): another take that says it right / cut
the line / re-record / keep it with an on-screen correction. If all ✅: say it in one line and continue.
(`build` warns about any counter / non-illustrative bars number that no ✅ line confirms.)

## 4. Cut and align

`$CM cut <folder>/out/edl.json`, then sheet `out/aroll.mp4` around every cut point (±0.5 s, `--step 0.1`) and READ
it — a framing jump or half-cut word at a join means fix the EDL and cut again. Then `$CM align <folder>/out/edl.json`. Read `work/aligned_words.json`; any
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
- Music: config `music.source` = `folder` → automatic (first audio file in config `music.folder`); `heygen` → check
  sign-in with `npx --yes hyperframes@0.8.157 media-use resolve --doctor`; if not signed in, use no music and note it
  in EDIT_NOTES (never sign in for them, no extra pause); if signed in:
  `npx --yes hyperframes@0.8.157 media-use resolve --type bgm --intent "<mood>" --project <folder>/out/composition`
  and put the file's ABSOLUTE path in `plan.music.src`; `none` → no music.

## 6. Build and look

`$CM build <folder>/out` — fix every `cutmate:` error (it names the bad anchor and lists the segment's words) and think
about every `WARN`. The last line prints `checkpoints: t1,t2,...`. Then, from the project dir (no path argument):
`( cd <folder>/out/composition && rm -rf ../snapshots && npx --yes hyperframes@0.8.157 snapshot --at <checkpoints> --no-end --describe false -o ../snapshots )`
(skip the snapshot when build printed no checkpoints) and READ every frame: overlaps, text wrapping, safe zones, captions readable, split panel shows the media. Fix
`plan.json` and rebuild until clean.

## 7. Render and QA

`$CM render <folder>/out` (check → render → finalize; ~1–2 min; writes `out/final.mp4`). READ every `check_*.png` it
writes and describe each in one line. If `steps.qa`: `$CM qa <folder>/out` and handle every hit: probe/rms, fix the
EDL (then cut → align → build → render; graphics move with their words automatically) or explain why it's fine.

## 8. Thumbnail (if `steps.thumbnail`)

Pick a frame with a strong expression from a sheet of `out/final.mp4` (`$CM sheet <folder>/out/final.mp4 -o <folder>/out/sheets/final.png`);
`--at` is seconds into `final.mp4`. Title = the PROMISE of the short (not the product name), hook = the short's hook
question. Keep the title short (it wraps to at most 3 lines) and the hook to 2 lines:
`$CM thumb <folder>/out --at <t> --title "SAME KONKRETY" --hook "Czy Caveman dalej działa?"`
(writes `out/thumbnail.png` and `.jpg`). READ the PNG; redo with another frame if the face is covered.

## 9. Notes and hand-off

Write `out/EDIT_NOTES.md`: final structure (segments in order with times), which graphic is where and why, music,
commands used. Send the user `final.mp4` (and the thumbnail). For 16:9 also hand over `chapters.txt` and, if it was written, `captions.srt`. When they reply with timestamps, batch all changes into
one rebuild + one render.
