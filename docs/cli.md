# CLI reference

The `cutmate` command-line tool is the engine behind the skills. You normally never type it, because Claude runs it for you. It is still useful for scripting, debugging and building your own skills.

**Where it is:** `~/.cutmate/venv/bin/cutmate` (Linux / macOS) or `~/.cutmate/venv/Scripts/cutmate.exe` (Windows); see [installation.md](installation.md#3-the-python-environment). The skills locate it with this line, which works in bash, zsh and Claude Code's Git Bash on Windows:

```bash
CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"
"$CM" doctor
```

**Conventions**

- `<rec>` is a recording folder; `<out>` is its `out/` folder (for example `~/Videos/short/out`).
- Commands that take `--language` or `--backend` fall back to the config (`cutmate config show`). Commands that take `--theme` fall back to the config `theme`.
- Errors print one line, `cutmate: <cause and fix>`, to stderr and exit with code **2**. `render`, `finalize` and `smoke` exit with **1** when the output fails its spec check.
- Output is UTF-8 on every OS. Quote paths that contain spaces.

## Summary

| Command | Purpose |
|---|---|
| [`transcribe`](#transcribe) | Transcribe every clip in a recording folder |
| [`formats`](#formats) | Aspect ratio of each clip (rotation-aware) |
| [`sheet`](#sheet) | Contact sheet of frames |
| [`probe`](#probe) | Re-transcribe one short window (hidden retakes) |
| [`rms`](#rms) | Loudness scan in short bins (speech blobs) |
| [`cut`](#cut) | Cut the A-roll from an EDL |
| [`align`](#align) | Word timings for the A-roll |
| [`track`](#track) | Face and hand positions over time |
| [`build`](#build) | `plan.json` → HyperFrames project |
| [`preview`](#preview) | Fast 480p preview + `chapters.txt` (long-form checkpoint) |
| [`render`](#render) | Check, render and finalize the built project |
| [`finalize`](#finalize) | Loudness fix and spec check of a render |
| [`qa`](#qa) | QA of a finished video |
| [`requests`](#requests) | Match `requests.md` against the plan |
| [`shot`](#shot) | Screenshot a web page for b-roll |
| [`thumb`](#thumb) | Thumbnail from a frame + title |
| [`save-effect`](#save-effect) | Keep a custom effect in a theme |
| [`theme …`](#theme) | Theme drafts: new, list, use, save, check, font, digits, colors |
| [`theme-check`](#theme-check) | Render every component of a theme (without the lint / stamp of `theme check`) |
| [`config show` / `config set`](#config) | Show or change the config |
| [`doctor`](#doctor) | Health report (JSON) |
| [`models`](#models) | Download the local models |
| [`vendor`](#vendor) | Fetch GSAP (sha-checked) |
| [`selftest`](#selftest) | Transcription test on your own clip |
| [`smoke`](#smoke) | 5 s smoke render |

## Recording and takes

### transcribe

```bash
cutmate transcribe <rec> [--prompt "Claude, Caveman, GitHub"] [--backend local|groq|openai|elevenlabs] [--language pl|en] [--force]
```

Transcribes every video file in `<rec>` with word timestamps. Results go to `<rec>/out/work/<clip file name>/`: `transcript.json`, `silences.json` and `<stem>.wav`. Lines starting `SUSPECT long word` mark windows that probably hide a stumble or a retake.

| Flag | Meaning |
|---|---|
| `--prompt` | Proper names and spelling hints for the model |
| `--backend` | Override the config backend |
| `--language` | Override the config language |
| `--force` | Re-transcribe clips that already have a transcript |

### formats

```bash
cutmate formats <rec>
```

Prints `<clip>: <width>x<height> <9:16|16:9>` per clip (rotation-aware), then `format: 9:16`, `format: 16:9` or `format: mixed`.

### sheet

```bash
cutmate sheet <video> -o <png> [--start 0] [--end <s>] [--step 0.5] [--cols 6]
```

Writes a contact sheet of frames with time labels and prints the path(s). More than 48 frames are split into `name_01.png`, `name_02.png`, …

| Flag | Default | Meaning |
|---|---|---|
| `-o`, `--out` | required | Output PNG |
| `--start` / `--end` | 0 / end of video | Time range in seconds |
| `--step` | 0.5 | Seconds between frames (> 0) |
| `--cols` | 6 | Columns (≥ 1) |

### probe

```bash
cutmate probe <wav> --start <s> --end <s> [--prompt "Um, uh, er, hmm."] [--backend …] [--language …]
```

Re-transcribes one short window (about 1 s) of a clip's WAV and prints `word@start-end` for each word, with times global to the WAV. Use it to expose false starts that Whisper merged into one long word.

### rms

```bash
cutmate rms <wav> --start <s> --end <s> [--bin 0.05]
```

Prints the RMS level (dB) per bin with a bar, then `blobs: [a-b] …`, the speech blobs. Two blobs inside one "word", or a short spike after a word, point to a retake, a stumble or a mouth click.

## Cut, align, track

### cut

```bash
cutmate cut <out>/edl.json
```

Cuts `out/aroll.mp4` from the EDL. Segments are encoded one by one (memory-safe for 4K), cuts snap to the frame grid, every segment is levelled to the median segment loudness, and short audio fades go on every cut. It also writes `out/work/edl_timed.json`.

### align

```bash
cutmate align <out>/edl.json [--language pl|en]
```

Forced-aligns the EDL text against `aroll.mp4` with wav2vec2 and writes `out/work/aligned_words.json`. Words marked `(estimated)` mean a segment's text does not match its audio. Run `cut` first.

### track

```bash
cutmate track <out> [--force]
```

Tracks the face, hands, fingertips and pointing over time with MediaPipe and writes `out/work/tracks.json`. It prints the path and the sample count per track. The work is skipped when `tracks.json` is newer than `aroll.mp4`; `--force` redoes it (needed once for projects tracked before fingertip tracks existed).

## Build and render

### build

```bash
cutmate build <out> [--theme <name>] [--language pl|en]
```

Turns `plan.json` (plus `edl.json`, the aligned words and the tracks) into a HyperFrames project in `out/composition/`. It also writes `captions.srt` and `chapters.txt` when they apply. It prints the warnings (`WARN density`, `WARN wow …`, `WARN panel gap` …), `layout: classic|split-panel`, one `panel:` line per panel item, `project: <path>` and `checkpoints: t1,t2,…` (times worth snapshotting). Bad anchors fail with the segment's word list.

### preview

```bash
cutmate preview <out> [--theme <name>] [--language pl|en]
```

Writes a fast 480p `out/preview.mp4` (the cut plus chapter plates) and `out/chapters.txt`, then prints the chapters. It is the long-form checkpoint before the slow full render.

### render

```bash
cutmate render <out>
```

Runs `hyperframes check`, then `hyperframes render` (progress streamed to the terminal and to `out/work/render.log`), then `finalize`. It writes `out/final.mp4` and `check_*.png` frames at the build's checkpoints. A 9:16 short takes about 1–2 minutes; 16:9 takes about 45–60 minutes per 15 minutes of video.

### finalize

```bash
cutmate finalize <src.mp4> <dst.mp4> [--format 9:16|16:9] [--check 1.5,4.0]
```

Brings the full mix to −14 LUFS and checks the spec: 1080×1920 or 1920×1080, 30 fps, H.264 + AAC. It prints `<file>: WxH fps codecs, duration, LUFS — OK` or `SPEC MISMATCH`, and writes a `check_<t>.png` frame for every `--check` time.

### qa

```bash
cutmate qa <out> [--no-asr] [--backend …] [--language …]
```

Re-transcribes the cut A-roll and flags repeated words and trailing "…" (missed false starts). It also compares the mix with the voice: `LOUD` means SFX or music more than 3 dB over the voice, and `QUIET` means a segment more than 4 dB under the voice median. `--no-asr` runs only the mix check.

## Requests, b-roll, thumbnails, effects

### requests

```bash
cutmate requests <out>
```

Matches every line of `out/requests.md` against the plan and prints `OK`, `MISSING`, `BAD` or `NOTE` per request (surprises are prefixed `SURPRISE`), then `requests: N ok, M missing, K bad`. Needs `work/aligned_words.json`, `work/edl_timed.json` and `plan.json`. The line format is in [usage.md](usage.md#requests-in-chat-or-spoken-in-the-recording).

### shot

```bash
cutmate shot "<url>" -o <png> [--width 1000] [--height 700] [--light]
```

Screenshots a web page (or a local HTML file) with headless Chrome / Chromium / Edge. The page renders in dark mode unless you pass `--light`.

### thumb

```bash
cutmate thumb <out> --at <s> --title "SAME KONKRETY" [--hook "Does it still work?"] [--theme <name>] [--side left|right]
```

Builds `out/thumbnail.png` and `out/thumbnail.jpg` from the frame at `--at` seconds of the cut (taken from `aroll.mp4`, so there are no burned captions). Shorts get 1080×1920, 16:9 videos get 1280×720. The title wraps to at most 3 lines and the hook to 2. In 16:9, `--side` (default `right`) puts the text box on that side, so pick a frame with the face on the other side.

### save-effect

```bash
cutmate save-effect <out> <name> [--theme <name>] [--description "…"] [--force]
```

Lints `out/custom/<name>.html` and copies it (plus its `out/custom/<name>/` asset folder) into `~/.cutmate/themes/<theme>/components/custom/`, recording it in that folder's `index.json`. `--force` replaces an effect of the same name. Effect names are lowercase letters, digits and dashes.

## Themes

### theme

```bash
cutmate theme new [<name>] [--from clean] [--mode custom|random|clone] [--seed N] [--avoid THEME ...]
cutmate theme list
cutmate theme use <name>
cutmate theme save <name> [--force]
cutmate theme check <name> [--clip <video>] [--language pl|en] [--saved]
cutmate theme font <name> "<Google font family>" --role text|display|num
cutmate theme digits <name>
cutmate theme colors <image> [<image> ...] [--n 8]
```

| Subcommand | What it does |
|---|---|
| `new` | Starts a draft in `~/.cutmate/themes/.drafts/<name>/`, a copy of `--from` (default `clean`). It prints JSON with `name`, `path` and the `direction`. `--mode random` rolls a direction (and can suggest a name); `--seed` makes the roll repeatable; `--avoid` (repeatable) steers away from earlier drafts. It warns when a saved theme already has that name. |
| `list` | One tab-separated line per theme: `marker`, `name`, `kind` (bundled / user / draft), `checked`, `path` |
| `use` | Makes a saved theme the default (the config `theme`) |
| `save` | Moves a checked draft into `~/.cutmate/themes/`. `--force` overwrites, keeping the old version in `themes/.backup/` |
| `check` | Lints the theme, renders every component in both formats, writes `check/contact.png` and the sheets, and stamps it as checked. This is the gate before `save`. `--clip` uses your footage as the A-roll instead of the test pattern (`--language` defaults to `pl` here); `--saved` checks the saved theme even when a draft has the same name. |
| `font` | Downloads an OFL Google Font into a **draft** (`text`, `display` or `num` for a digit font), with its licence |
| `digits` | Renders the theme's numbers in its display / digit font next to look-alike letters (5 vs S, 0 vs O) and prints the PNG path |
| `colors` | Prints the dominant colours of images as `#hex  NN%` (`--n` colours, default 8) |

### theme-check

```bash
cutmate theme-check [--theme <name>] [--language pl|en] [--format 9:16|16:9|all]
```

Renders every component of a theme and prints a contact sheet path per format (`check passed (9:16) — contact sheet: …`). Unlike `theme check`, it does not lint, write `contact.png` or stamp the theme.

## Config and environment

### config

```bash
cutmate config show
cutmate config set KEY=VALUE [KEY=VALUE ...]
```

`show` prints the effective config as JSON. `set` validates and saves, then prints the file path and the new config. All keys are listed in [configuration.md](configuration.md).

### doctor

```bash
cutmate doctor
```

Prints a JSON health report: Python, venv, ffmpeg, Node.js, packages, CUDA, models, API keys (present or not, never the values), carve, config, vendor and plugin root. It never fails. See [installation.md](installation.md#troubleshooting-with-cutmate-doctor).

### models

```bash
cutmate models [--language pl|en] [--backend local|groq|openai|elevenlabs]
```

Downloads the wav2vec2 alignment model for the language, Whisper large-v3 when the backend is `local`, and the MediaPipe pose and hand models. Downloads resume when you run it again.

### vendor

```bash
cutmate vendor
```

Downloads the libraries cutmate may not redistribute (GSAP) from jsDelivr into `~/.cutmate/vendor/`, checks each file against the sha256 in `assets/vendor/MANIFEST.json`, and writes nothing that fails the check. It is idempotent, and prints `gsap@3.14.2: ok` or `fetched …`.

### selftest

```bash
cutmate selftest --clip <video> [--backend …] [--language …]
```

Transcribes the first 30 s of your clip and prints `backend: … · device: … · compute: …`, the word count and timing, and the first words with timestamps. `--clip` is required unless a bundled sample for the language exists.

### smoke

```bash
cutmate smoke [--clip <video>] [--music <audio>] [--format 9:16|16:9] [--workdir <dir>]
```

Runs a 5-second end-to-end render (a title plus captions, and an optional music bed) in `~/.cutmate/smoke/` or `--workdir`. It prints `final:` and `frame:` (a PNG at 1.5 s). Without `--clip` it uses a plain coloured background. The clip must be at least 2 s long.
