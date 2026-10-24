# Contributing to cutmate

Thanks for helping. This guide gets you from a fresh clone to a passing test run, and explains the rules that keep cutmate working on Windows, macOS and Linux.

## Dev setup

Prerequisites: Python 3.10+, Node.js 22+ (with `npx`), ffmpeg, git. Google Chrome is optional (the `shot` command).

**Linux / macOS**

```bash
git clone https://github.com/wisniewskib/cutmate.git
cd cutmate
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip install -e ".[dev,align,track,faster]"   # optional: the full set, for -m slow / hf tests
.venv/bin/cutmate vendor                                         # GSAP, needed by build tests
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/wisniewskib/cutmate.git
cd cutmate
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\cutmate.exe vendor
```

To try your working copy inside Claude Code, without touching your real cutmate home:

```bash
CUTMATE_HOME=/tmp/cm-dev claude --plugin-dir .
```

```powershell
$env:CUTMATE_HOME = "$env:TEMP\cm-dev"; claude --plugin-dir .
```

Then run `/cutmate:setup` in that session.

## Tests

The suite lives in `tests/`. By default `pytest` skips the heavy markers (`addopts = -m 'not slow and not hf and not net'` in `pyproject.toml`).

| Command | What runs | Needs |
|---|---|---|
| `.venv/bin/python -m pytest` | The fast suite (hundreds of tests; a few minutes) | `dev` extra, ffmpeg |
| `.venv/bin/python -m pytest -m hf` | Tests that build and render with `npx hyperframes` (themes, components, WOW effects, render budgets) | Node.js 22+, network on first run, Chrome downloaded by HyperFrames |
| `.venv/bin/python -m pytest -m net` | Tests that download fonts from Google Fonts | Network |
| `.venv/bin/python -m pytest -m slow` | Tests that need downloaded models or recorded samples | `align` / `track` / `faster` extras, models |
| `.venv/bin/python -m pytest tests/test_plan.py -k density` | One file / one test | |

On Windows use `.venv\Scripts\python.exe -m pytest …`.

Always run the fast suite before a PR. Run `-m hf` when you touch `build.py`, theme components, effects, `web/*.js` or anything that changes rendered output. Some builds are pinned by **byte-identical golden** outputs, so an intended visual change needs its golden updated in the same PR, with a note explaining why.

Write the failing test first, then the fix.

## Conventions

- **One concern per change.** Fixes stay small. Commit messages are short and imperative, and use the existing prefixes (`feat:`, `fix:`, `docs:`, `test:`).
- **Errors are one line with the fix.** Raise `CutmateError` (or a subclass) with the cause and the command that fixes it. The CLI prints `cutmate: …` and exits 2. Never show a stack trace for an expected failure.
- **Never handle secrets.** API keys come from environment variables only. Never echo user input that might be a key (see `config.set_values`).
- **Determinism.** Anything that renders must be a pure function of time: one paused timeline or `U.clock`, randomness only from `U.seed`. Add new forbidden tokens to the lint in `effects.py` with a test.
- **Offline renders.** A new JS library goes through `tools/vendor_libs.py` with a pinned version, sha256 hashes and its licence in `assets/vendor/LICENSES/`. If its licence does not allow redistribution, mark it `"redistribute": false` so `cutmate vendor` fetches it instead.
- **Licences.** Fonts must be OFL (Google Fonts) and sound effects CC0 or similar, with a licence file next to them. Never commit a recording of a real person.
- **Skills are the product.** If you change CLI output, flags or file names, update every `skills/*/SKILL.md` that mentions them and the docs in `docs/`. Skill commands use `"$CM"` (the venv CLI) and must run in Claude Code's Git Bash on Windows.
- **Docs ship with the change.** A new command, flag, config key or effect param needs its entry in `docs/cli.md`, `docs/configuration.md` or `docs/effects.md`, and in `index.json` for effects.

## Windows rules

Most cutmate users are on Windows, so every change must work there as well as on Linux and macOS:

- **`pathlib` only.** No `/`-joined path strings and no hard-coded `/tmp`. Use `tempfile` or the cutmate home.
- **`encoding="utf-8"`** on every `open`, `read_text` and `write_text`. The Windows default (cp1250 / cp1252) breaks Polish text.
- **No symlinks.** Copy instead.
- **Subprocesses:** list arguments, never `shell=True`, no bash-only commands from Python. Resolve executables with `shutil.which` (so `npx.cmd` and `ffmpeg.exe` are found).
- **ASCII-safe file names** for anything cutmate writes.
- **ffmpeg filters:** avoid `drawtext` with font paths, because Windows drive letters break the filter syntax. Draw text with Pillow, as `preview.py` does.
- **Skill text:** commands must work in Claude Code's Git Bash on Windows: quote every path (spaces in user folders), use the `CM=…` line that also finds `venv/Scripts/cutmate.exe`, and give PowerShell variants (`setx`, `setup.ps1`) where a user runs something in their own terminal.
- **Install scripts:** keep `setup.sh` / `setup.ps1` and `detect.sh` / `detect.ps1` in step with each other. `setup.ps1` must stay compatible with Windows PowerShell 5.1.

If something is Linux-only, say so in the PR. Before a release, the setup and an edit are run from scratch on a real Windows machine.

## Pull requests

1. Branch from `main`.
2. Make the change, with tests and docs.
3. Run the fast suite (and `-m hf` if rendering is affected).
4. Open the PR with what changed, why, how you tested it, and on which OS.

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE).
