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
`work/aligned_words.json` → `work/tracks.json` (if needed) → `plan.json` → checkpoint "zrozumiałem tak" (if `requests.md` exists) → `preview.mp4` (16:9) → `composition/index.html` → `final.mp4` → `thumbnail.png` (if `steps.thumbnail`) → `EDIT_NOTES.md`.
Resuming at `takes.md` means (re)making and READING the sheets first.

## 1. Transcribe and look

1. Collect proper names the user mentions (products, people, tools) → `$CM transcribe <folder> --prompt "Claude, Caveman, GitHub"`.
   Results land in `out/work/<clip file name>/` (`transcript.json`, `silences.json`, `<stem>.wav`). Words come with
   times; `SUSPECT long word` lines mark windows that hide a stumble or a retake.
2. For every clip: `$CM sheet <clip> -o <folder>/out/sheets/<clip>.png --step 0.5` and READ the sheet image(s) (16:9: overview sheets with `--step 2` — dense `--step 0.1` sheets only around candidate cuts, as §2 says; thumbnail sheet of `final.mp4` with `--step 10`). Note where
   the speaker looks away, reads notes, the framing jumps (stabilisation), or they point at something.
3. Run `$CM formats <folder>` (`cutmate formats` is rotation-aware; last line `format: 9:16|16:9|mixed`). All `16:9` →
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
  `point` always sits top-right in 16:9 (its corner is ignored); for pip page screenshots use `$CM shot <url> -o … --width 1600 --height 900`.
  Components: `pip` (instead of `split`; `from`, `to`, `media`, `corner?` br|bl, `fit?` cover|contain), `lower-third`
  (`at`, `name`, `role?`) once at the self-introduction, corner graphics as usual. `split` is an error in 16:9.
- **Checkpoint before the full render (always):** `$CM preview <folder>/out` → send the user `out/preview.mp4` and the
  `chapters.txt` lines; wait for OK. Changes → EDL / plan → new preview. Only then build, snapshot, render (a 15-minute
  video renders for ~45–60 min — tell the user the ETA and run `$CM render` in the background, see §7).
- **Outputs:** `final.mp4`, `chapters.txt` (paste into the YouTube description), `captions.srt` when the config's caption
  mode for 16:9 is `srt`/`both` (upload in YouTube Studio), thumbnail.
- **Thumbnail:** 1280×720; pick a frame where the face is on one side and put the text on the other:
  `$CM thumb <folder>/out --at <t> --title "…" --hook "…" --side left|right`.
- Custom theme: `$CM theme-check --theme <theme> --language <lang> --format 16:9`.

## 1c. Effects on request

The user can ask for things the built-in components don't cover. Collect every request, map it, show it, then build.

**Collect** into `out/requests.md` early, as requests come in (it needs no EDL; `$CM requests` runs later, see Checkpoint), one line each: `- [<source>] <what> → <target> [@ <anchor>]`. Target = component type,
`custom:<name>`, `cut` or `skip`; anchor = segment id (`S5`) or word anchor (`S7:Rasengan`). Sources:
- `[czat]` — the user's message to you.
- `[nagranie <clip> <time>]` — spoken director notes (polecenia) in the transcript: phrases addressed to the editor, second
  person ("tutaj ma być", "dodaj", "przenosisz mnie", "zrób"). These segments never go into the EDL unless they are
  also content. Jokes / filler with no content ("Test.", "Twerk.") are cut like false starts and listed as `→ cut`.
- `[uwagi <mm:ss>]` — feedback after a render.

**Map:** a built-in component when one fits; `bg` for "inne tło / przenieś mnie gdzie indziej"; `side` for "na połowie
ekranu" (16:9 only); otherwise `custom`. Check saved effects first: `~/.cutmate/themes/<theme>/components/custom/index.json`
and the bundled `energy-ball` (params `radius`, `colors`; use with `"follow": "hand"`).

**Plan types** (in `plan.json` graphics):
- `{"type": "custom", "name": "<lowercase-dashes>", "from": …, "to": …}` or `"at"` (+ `until`); `"follow": "face"|"hand_left"|"hand_right"|"hand"`
  (needs tracks.json); `"params": {…}` land at the top level of `P` in the effect.
- `{"type": "bg", "from", "to", "media": "broll/…"}` or `"effect": "<name>"`. Media = a file in `broll/`, or an AI image:
  `npx --yes hyperframes@0.8.157 media-use resolve --type image --intent "<what>" --project <folder>/out/composition` when signed in
  (copy it to `broll/`). `bg` removes the background from the A-roll: ~17× the duration on CPU. Total `bg` > 30 s → build WARN: ask the user before building.
- `{"type": "side", "from", "to", "media"|"effect", "speaker": "right"|"left"}` — speaker on one half, graphic on the other (16:9 only).
- `face` per segment is filled automatically from tracks.json when missing.

**Tracking:** if any graphic uses `"follow"`, or you want face-centred punch-ins without reading sheets, run
`$CM track <folder>/out` after `cut` (cached by A-roll mtime; `--force` redoes it). Needs mediapipe; otherwise tell the user to run `/cutmate:setup`.

**Writing a custom effect** in `out/custom/<name>.html`: the same `<style>` / `<markup>` / `<script>` sections as theme
components; `ROOT` in style is the effect root. Rules:
- `U.clock(fn)` is the only per-frame driver (`fn(t)`, local time) — never `onUpdate`, timers or rAF. `U.seed(n)` is the only randomness.
- `U.trackAt(P.track, t)` → `[x, y]` px or null; `U.follow(el, P.track)` sticks an element to the hand / face.
- `U.three({el, bloom:{strength,radius,threshold}, camera})` → Promise of `{THREE, scene, camera, renderer, composer, toWorld(xPx, yPx, z), render}`;
  `U.glowOrb(S, {radius, colors, swirl})` → `{group, update(t)}`; `U.particles(target, {count, seed, life, speed, spin, size, colors, emitter})`
  → `{update(t), points?}` (canvas: px; inside `U.three`: world units: frame height ÷ 6.3 px per unit, ≈171 at 1080 px tall, ≈305 at 1920); `U.draw(sel, {from, dur, stagger})`;
  `U.rough(svg, shapes, {seed})` (shape = `{kind: "rectangle"|"circle"|"line"|"path"…, args: [...], opts: {...}}`); `U.tex(el, latex)`; `U.anime(timeline)`; `U.lottie(anim)`.
- `P.w`, `P.h`, `P.dur`, `P.at`, `P.end`, `P.track`, plus your own params at the top level of `P`.
- Forbidden (build rejects the file, even in comments or strings): Date.now, Math.random, performance.now, requestAnimationFrame, setTimeout, setInterval, onUpdate,
  setAnimationLoop, anime.utils.random, d3.transition, AfterimagePass. Libraries (GSAP plugins, Three.js, Anime.js, Lottie, KaTeX, Rough.js, D3) load automatically when used.

Pattern (the energy-ball effect, abridged):
```html
<style>ROOT { position: absolute; inset: 0; }</style>
<markup><div class="fx" style="position:absolute;inset:0"></div></markup>
<script>
// root = the effect's root element
U.three({ el: root.querySelector(".fx"), bloom: { strength: 1.2, radius: 0.6, threshold: 0.1 } }).then(S => {
  const orb = U.glowOrb(S, { radius: P.radius || 1, colors: P.colors, swirl: 1 });
  S.scene.add(orb.group);
  U.clock(t => {
    const p = U.trackAt(P.track, t);
    if (p) orb.group.position.copy(S.toWorld(p[0], p[1], 0));
    orb.update(t); S.render();
  });
});
</script>
```

**Checkpoint "zrozumiałem tak":** map every request into `plan.json` in §5 first (a word anchor in requests.md matches a graphic starting within ±1 s of that word). Then, right before build (16:9: together with the preview), when `requests.md` has ≥ 1 line, run `$CM requests <folder>/out` — it needs aligned_words.json, edl_timed.json and plan.json (one line per request: OK / MISSING /
NOTE / BAD, then `requests: N ok, M missing`), fix every `MISSING` and `BAD`, then show the user the list as "zrozumiałem tak: …"
and wait for OK. No requests → no pause.

**After acceptance:** for each `custom` effect used, ask once "Zapisać efekt <name> w theme?" → `$CM save-effect <folder>/out <name> --description "…"`
(`--theme T` to pick the theme, `--force` to overwrite).

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
- Spoken director notes (§1c) are not segments: cut around them, unless they are also content.
- Cut on silence bounds (`work/<clip>/silences.json`): `in ≈ speech start − 0.06`, `out ≈ speech end + 0.08`.
  Keep ≥ 0.2 s after the last loud bin of a word ending in a quiet consonant (ć, ś, t, k).
- `text` is the caption source of truth: fix spelling of names, never change what was said.
- `spoken`: how numbers and foreign words are pronounced, for alignment.

## 3. Fact-check (only if `steps.factcheck` is true)

List every checkable claim (numbers, prices, dates, versions, names, "first / only / free"). Verify each with
WebSearch AND by opening the source page (official docs, pricing, changelog, repo; studies for health; law texts for law).
Write `out/factcheck.md`, one line per claim: timestamp, quote, verdict (✅ / ⚠️ / ❌ plus the word in the user's
language, e.g. OK / NIEPEWNE / BŁĄD), the true version, link. If anything is ❌ or ⚠️: STOP and ask the user (this is the only pause besides the 16:9 preview checkpoint): another take that says it right / cut
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
- Effects on request (`custom`, `bg`, `side`, `"follow"`): §1c.
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
(skip the snapshot when build printed no checkpoints; for every custom effect add at least two checkpoints, start and middle, and READ those frames — effects are new code) and READ every frame: overlaps, text wrapping, safe zones, captions readable, split panel shows the media. Fix
`plan.json` and rebuild until clean.

## 7. Render and QA

`$CM render <folder>/out` (check → render → finalize; writes `out/final.mp4`). 9:16 takes ~1–2 min. 16:9 takes ~45–60 min per 15 min of video: run it in the background (Bash `run_in_background: true`), follow `out/work/render.log`, and tell the user the ETA. READ every `check_*.png` it
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
commands used. Send the user `final.mp4` (and the thumbnail).
16:9: also hand over `chapters.txt` and, if it was written, `captions.srt`.
When they reply with timestamps, log each as `[uwagi <mm:ss>]` in `requests.md` (§1c) and batch all changes into
one rebuild + one render.
