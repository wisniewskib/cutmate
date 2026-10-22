---
name: clone-style
description: Turn a style source (a reel / video link, a local video, screenshots, a folder) into a cutmate theme that looks like it — palette, fonts, shapes, captions and motion read from the frames, then built, checked side by side with the source and saved. Use when the user runs /cutmate:clone-style or says "zrób theme jak u …" / "chcę styl jak w tej rolce".
---

# /cutmate:clone-style

Rules:
- Talk to the user in their language (config `language`). Replies short: the action first, a few lines.
- Ask EVERY question with **AskUserQuestion** (≤ 4 options per question, the recommended option first and marked
  "(polecane)"), never as an A/B/C text list. The labels below are Polish; translate them to the user's language, keep
  the mapping.
- Set the CLI once per session (setup venv first, so a dev `cutmate` on PATH never shadows it):
  `CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`;
  if it doesn't run, tell the user to run `/cutmate:setup` and stop.
- The theme must LOOK like the source — same palette, font character, corners, caption style and motion — but it is
  our own work: logos, watermarks, handles, the source's text, its images and its artwork are never copied into the
  theme (not as files, not traced into SVG, not as sample text). Fonts only through `$CM theme font` (OFL Google
  Fonts).
- Work files go to the clone dir `${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>/` (`<name>` = the theme name you
  pick in §1). Quote every path (spaces on Windows).
- Any failing command: one line with the cause + the fix.

## 1. Sources

Take them from the arguments; none → AskUserQuestion "Skąd wziąć styl?": Link do rolki / filmu (polecane) / Plik
wideo / Screenshoty / Folder → then the free-text answer gives the link or the path(s).
Pick a working `<name>` now (the look, not the creator's brand: e.g. `neon-pill`; letters, digits, `_`, `-`) and
`mkdir -p "${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>"`.

- **Local files / folders** — read them as they are, nothing is copied: videos (`.mp4 .mov .mkv .webm`) → §2,
  images (`.png .jpg .jpeg .webp`) → READ each one. A folder → list it and take both kinds.
- **A URL** — AskUserQuestion naming the source, e.g. "Pobrać jeden film z <site> (<url>) przez yt-dlp — tylko do
  analizy stylu, ~ kilkadziesiąt MB, zostaje w folderze clone?": **Tak (polecane)** / **Nie, dam screenshoty** (→ ask
  for screenshots or a local file and continue with those). Nothing runs before Tak (not even `yt-dlp --version`);
  download only after Tak:
  1. `yt-dlp --version` (Git Bash on Windows finds `yt-dlp.exe` the same way). Missing → the user installs it himself
     (`pipx install yt-dlp`; Windows also `winget install yt-dlp`; macOS `brew install yt-dlp`) and says when — or
     gives screenshots / a local file instead. Never install it for him.
  2. `yt-dlp --no-playlist --ignore-config -S "vcodec:h264,res:1080" -o "${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>/%(id)s.%(ext)s" "<url>"`,
     then `ls "${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>"` for the file name. `--ignore-config` keeps the user's
     yt-dlp config (which may hold cookies or a login) out; `-S` prefers H.264 up to 1080p (ffmpeg decodes it, the
     file stays small).
  - Never pass `--cookies`, `--cookies-from-browser`, `--username`, `--password` or `--netrc`; never sign in and never
    ask for a login. Public content only.
  - A login / private / age-gate / rate-limit / "unavailable" error → one line with the cause, then ask for screenshots
    (3–6 frames with the graphics and captions on screen) or a local file. Do not retry with other options.

## 2. Look

Let `CL="${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>"`.

Budget: at most 2 source videos and 4 sheets read in total (overview + motion sheets together; the stills and
screenshots don't count). More videos given → AskUserQuestion which 2 to use (the free-text answer names them).

Videos (each source video, max ~60 s per video — use `--end 60` for longer ones):
1. `$CM sheet "<video>" -o "$CL/sheet.png" --step 0.5` → it prints the sheet path(s) (more than 48 frames →
   `sheet_01.png`, `sheet_02.png` …). READ them within the budget (the first 1–2 of a video). Note when graphics enter (the tile labels are seconds).
2. Motion: for 1–2 graphic entrances (a title, a number, a sticker / chip — as many as the budget leaves):
   `$CM sheet "<video>" -o "$CL/motion-<t>.png" --step 0.1 --start <t-0.3> --end <t+0.9>` and READ — how it enters
   (slide / scale / slam / glitch / typewriter / fade), how fast (frames to settle), the ease (overshoot, hard stop).
3. Full-size stills for the font and the side-by-side check (sheets are small): 2–4 frames where graphics or
   captions are on screen, `ffmpeg -nostdin -v error -ss <t> -i "<video>" -frames:v 1 "$CL/frame-<t>.png"`; READ them.

Layout — while reading the overview sheets also note the LAYOUT (how the frame is divided, not only how the graphics
look):
- Does a panel stay on screen (the same box in most tiles, over and around the speaker)? Where (top / bottom) and which
  share of the frame height (e.g. top half → 0.5; the speaker then sits in the other part).
- How often its content changes: count the changes in 10 s of 0.5 s tiles (20 tiles) → a cadence `~<a>–<b> s`
  (e.g. 8 changes in 10 s → every ~0.5–2 s). What it shows: explainers, app / browser mockups, status tables, big
  numbers, real page screenshots, chat answers.
- Where the captions sit relative to it: on the seam between panel and face, or at the bottom.
- Full-screen scenes (the whole frame replaced by an image / illustration, no speaker): how many, how long each.
- The panel's colour (fill) — take its hex from the `$CM theme colors` list below.
A panel on screen in most tiles of the video = `split-panel`; graphics that come and go over the face = `klasyczny`.

Colours: `$CM theme colors "$CL"/frame-*.png "<screenshots…>" --n 12` → hex + share lines. Skin, walls and
the room dominate; take the accent / card / text colours from what you SEE on the graphics and captions and use the
list to get exact hex values.

Screenshots only: READ them, `$CM theme colors` on them, and say that motion is guessed from the look (no video).

## 3. Co widzę

Tell the user what you see — ≤ 9 lines, concrete:
- **Paleta:** accent, card, text, ink, muted as hex (+ which is on accent fills).
- **Fonty:** category (condensed grotesk, rounded sans, serif, mono, handwritten …), weight, case → the closest OFL
  Google family with Polish letters (ą ę ł ń ó ś ź ż) for display and for text. The original font only if it is OFL.
- **Kształty:** corners (sharp / rounded / pill), borders, shadows, strips, tilts.
- **Napisy:** position, case, words per page, box / outline / shadow, key-word colour.
- **Ruch:** entrances, speed, ease.
- **Gęstość grafik:** how often graphics appear and how big they are.
- **Układ:** `klasyczny` | `panel u góry <ratio>, zmiana co ~<a>–<b> s, napisy na szwie|na dole, scen pełnoekranowych: <n>`
  (e.g. `panel u góry 0.5, zmiana co ~0.5–2 s, napisy na szwie, scen pełnoekranowych: 2`) + the panel colour hex.

AskUserQuestion "Zgadza się?": **Zgadza się (polecane)** / **Popraw** (the user says what → change it, show the
lines again only if much changed).

## 4. Build

1. `$CM theme new <name> --mode clone` (prints JSON with `path`). `WARN theme <name> exists` → ask now, as in
   `/cutmate:theme` §3 step 4 (its §4 overwrite question; Nowa nazwa → `$CM theme new` again with the new name).
2. Write the direction into the draft's `theme.json`:
   `"direction": {"mode": "clone", "sources": […], "palette": {name, accent, on_accent, text, ink, card, muted},
   "fonts": {"display": …, "text": …}, "shapes": …, "motion": …, "captions": …, "hints": {…}}`.
   - `sources` = short descriptions only, e.g. `"instagram reel <url>"`, `"local video reel.mp4"`, `"3 screenshots"` —
     never file contents, frames or text from the source.
   - `shapes` (sharp / pill / outline / brutal / tape), `motion` (snappy / smooth / glitch / typewriter / slam),
     `captions` (boxed / highlight / outline / shadow) = the closest values; `hints` = what makes this source itself
     (e.g. `"title": "yellow slab, black kicker bar, tilted 2°"`, `"motion": "fast slide from left, small overshoot"`).
   - Contrast: `ink` on `card` ≥ 4.5, `on_accent` on `accent` ≥ 4.5 — nudge the source colours if needed.
   - **Układ** `panel u góry …` → also write the top-level `"layout"` into the same `theme.json` (keys that equal the
     defaults may be left out — defaults: `panel` `"top"`, `ratio` 0.5, `cadence` [1.0, 3.0], `captions` `"seam"`,
     `transition` `"cut"`, `fullscreen.max_per_min` 3), e.g.
     `"layout": {"mode": "split-panel", "ratio": 0.5, "cadence": [0.5, 2.0], "captions": "seam", "transition": "cut", "fullscreen": {"max_per_min": 3}}`
     (`ratio` 0.40–0.60; `cadence` = the `~<a>–<b> s` you counted, 0.5 ≤ a < b ≤ 6; `captions` `"seam"` or
     `"bottom"`; `fullscreen.max_per_min` = scenes per minute of the source, rounded up, 0–6), and put
     `--panel-bg: <panel hex>;` (the panel colour from the colours list) into the draft's `tokens.css` colour block (the lint
     requires `--panel-bg` for split-panel). `klasyczny` → no `layout` key (classic is the default).
3. Follow `${CLAUDE_PLUGIN_ROOT}/skills/theme/generate.md` with this draft. Build the look from the hints, not just the
   recipe of the closest value. In its step 7 (quality bar) also compare with the source:
   build ONE composite image per comparison and READ that image (two separate images are hard to compare):
   `ffmpeg -nostdin -v error -y -i "<draft path>/check/contact.png" -i "<source still>" -filter_complex "[0:v]scale=-2:1080[a];[1:v]scale=-2:1080[b];[a][b]hstack=inputs=2" "$CL/side-by-side.png"`
   (`<draft path>` = `path` from `$CM theme new`; `<source still>` = a `$CL/frame-<t>.png` or a screenshot).
   For motion, the same command with a motion sheet as the second input → `$CL/side-by-side-motion.png`, and compare
   the entrance row (top row of contact.png) pairwise with the source's entrance frames. Then go through:
   - palette — the same colours in the same roles (what is accent, what is the card);
   - font character — weight, width, case, serif or not;
   - corners and shapes — radius, borders, shadows, tilts, strips;
   - captions — position, case, box / outline, key-word colour;
   - motion — the entrance row matches the source's entrances (direction, speed, overshoot).
   - layout (split-panel only) — `<draft path>/check/sheet-9x16.png` vs. a source overview sheet: the same panel share
     and colour, the face in the other part, captions in the same place, panel items that look like the source's.
   Fix what differs in the `generate.md` step it belongs to and re-check, until a viewer would say "same style". Max 3
   rounds; what still differs goes into the §5 summary.

## 5. Decision and save

Exactly as `${CLAUDE_PLUGIN_ROOT}/skills/theme/SKILL.md` §4 (Decision): send `contact.png` with 2–3 lines (plus one
line on how close it is to the source), then AskUserQuestion "Jak ci się podoba?": **Biorę (polecane)** / **Popraw
coś** (instead of Losuj: ask what, fix it in its `generate.md` step, re-check, compare with the source again, back
here) / **Anuluj**. Biorę → `$CM theme save <name>` with the same overwrite rules, then "Ustawić jako domyślny?" →
`$CM theme use <name>`.

The clone dir `${CUTMATE_HOME:-$HOME/.cutmate}/clone/<name>/` (download, sheets, frames) is never part of the theme;
logos, text and images of the source are never copied into it. At the end tell the user the clone dir path in one
line — they can delete it.
