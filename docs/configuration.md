# Configuration

cutmate keeps its settings in one JSON file:

| OS | Path |
|---|---|
| Linux / macOS | `~/.cutmate/config.json` |
| Windows | `%USERPROFILE%\.cutmate\config.json` |

Set the `CUTMATE_HOME` environment variable to move the whole cutmate home: config, venv, models, themes, smoke test and vendored GSAP.

There are two ways to change settings: run `/cutmate:setup` again (it asks which section to change), or use the CLI:

```bash
cutmate config show                                   # print the effective config as JSON
cutmate config set language=en music.volume=0.3       # set one or more KEY=VALUE pairs
```

`config set` validates every value and saves only when all of them pass. It refuses unknown keys and **never echoes a rejected value**, because it might be a pasted API key. API keys belong in environment variables (see [installation.md](installation.md#5-api-keys-environment-variables-only)).

## All settable keys

| Key | Values | Default | What it does |
|---|---|---|---|
| `transcription` | `local`, `groq`, `openai`, `elevenlabs` | `local` | Transcription backend for `transcribe`, `probe`, `qa`, `selftest` |
| `language` | `pl`, `en` | `pl` | Video language: transcription, alignment model, built-in labels |
| `theme` | A theme name (letters, digits, `_`, `-`) | `clean` | Default theme; it must exist in `~/.cutmate/themes/` or be bundled |
| `steps.factcheck` | `true`, `false` | `true` | Check every claim before cutting; the build warns about unconfirmed numbers |
| `steps.qa` | `true`, `false` | `true` | Run `cutmate qa` after the render |
| `steps.thumbnail` | `true`, `false` | `true` | Make `thumbnail.png` / `.jpg` |
| `music.source` | `heygen`, `folder`, `none` | `none` | Where the music bed comes from |
| `music.folder` | A folder path (or `""` / `null` to clear) | `null` | Used when `music.source=folder`; the path is stored absolute |
| `music.volume` | A number from 0 to 2 | `0.45` | Bed level relative to the voice |
| `captions.9:16` | `burn`, `srt`, `both`, `none` | `burn` | Caption mode for shorts |
| `captions.16:9` | `burn`, `srt`, `both`, `none` | `srt` | Caption mode for long-form |

The default config looks like this:

```json
{
  "transcription": "local",
  "language": "pl",
  "theme": "clean",
  "steps": {"factcheck": true, "qa": true, "thumbnail": true},
  "music": {"source": "none", "folder": null, "volume": 0.45},
  "captions": {"9:16": "burn", "16:9": "srt"}
}
```

Most command-line flags override the config for a single run: `--language`, `--backend`, `--theme`. See [cli.md](cli.md).

## Captions per format

| Mode | Burned into the video | `out/captions.srt` |
|---|---|---|
| `burn` | Yes | No |
| `srt` | No | Yes |
| `both` | Yes | Yes |
| `none` | No | No |

Why the defaults differ:

- **9:16 → `burn`.** Shorts are watched muted, and Shorts / Reels / TikTok have no proper caption upload. Burned word-by-word captions are the style.
- **16:9 → `srt`.** YouTube shows uploaded captions natively (upload `captions.srt` in YouTube Studio). Burned captions in 16:9 share the bottom band with the lower-third and the picture-in-picture circle.

The `.srt` uses exactly the same caption pages as the burned version.

```bash
cutmate config set captions.9:16=both captions.16:9=burn
```

Captions are always word-aligned (wav2vec2 forced alignment of the corrected EDL text). Key words listed in `plan.json` → `captions.key` get the theme's accent, and they also match inflected forms of the word.

## Music

| `music.source` | Where the bed comes from |
|---|---|
| `none` | No music |
| `folder` | The **first audio file** (sorted by name) in `music.folder`: `.mp3 .m4a .wav .ogg .flac .aac` |
| `heygen` | A lo-fi track resolved per video through HyperFrames `media-use` (needs the HeyGen CLI ≥ 0.3.0, and you signed in with `heygen auth login --oauth`) |

```bash
cutmate config set music.source=folder music.folder=~/Music/beds
cutmate config set music.source=heygen
cutmate config set music.source=none
```

`music.source=folder` is refused unless the folder exists and holds at least one audio file.

**How the bed is mixed:**

- It is looped or trimmed to the video length, brought to −14 LUFS (the same as the voice), and given a 0.8 s fade-in and a fade-out of up to 1.8 s.
- It is placed at `music.volume` (default 0.45) under the voice.
- When the HyperFrames plugin's audio skill is installed, the bed is **carved** so it ducks under speech. `cutmate doctor` shows `"carve": true`. Without it, the bed stays at a flat level and the build prints a `WARN music:` line.
- After the render, the full mix is brought to −14 LUFS again by `finalize`.

For a single video, Claude can set a specific file in `plan.json`: `"music": {"src": "/abs/path/bed.mp3"}`, optionally with `"volume"` to override the config. With HeyGen and no sign-in, the edit goes ahead without music and says so in `EDIT_NOTES.md`; Claude never signs in for you.

## Optional steps

```bash
cutmate config set steps.factcheck=false steps.qa=true steps.thumbnail=true
```

| Step | On | Off |
|---|---|---|
| `factcheck` | Claude verifies every claim with a web search and the source page and writes `factcheck.md`. A ❌ or ⚠️ verdict pauses the edit. | No `factcheck.md`; the build skips its number warnings |
| `qa` | `cutmate qa` re-transcribes the cut to find missed repeats, and flags music or SFX that is louder than the voice, or quiet segments | No QA pass |
| `thumbnail` | `thumbnail.png` and `thumbnail.jpg` from a chosen frame plus a title and hook | No thumbnail |

## Environment variables

| Variable | Used for |
|---|---|
| `CUTMATE_HOME` | cutmate's home folder (default `~/.cutmate`) |
| `GROQ_API_KEY` | `transcription=groq` |
| `OPENAI_API_KEY` | `transcription=openai` |
| `ELEVENLABS_API_KEY` | `transcription=elevenlabs` |

## What lives in the cutmate home

| Path | Contents |
|---|---|
| `config.json` | The settings above |
| `venv/` | The Python environment with the `cutmate` CLI |
| `models/` | MediaPipe pose and hand models (Whisper and wav2vec2 live in the Hugging Face cache) |
| `vendor/` | GSAP, fetched by `cutmate vendor` |
| `themes/` | Your saved themes, `.drafts/`, `.backup/` |
| `checks/` | Contact sheets of bundled themes from `cutmate theme check` |
| `clone/` | Work files of `/cutmate:clone-style` (safe to delete) |
| `smoke/` | The 5 s smoke render |
