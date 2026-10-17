---
name: setup
description: Install and configure cutmate — detect the system, install dependencies after a yes, pick the transcription backend and test it, download language models, set music, captions and optional steps, then a 5 s smoke render. Use when the user runs /cutmate:setup, installs cutmate, or wants to change the transcription backend, language, music or captions.
---

# /cutmate:setup

Talk to the user in their language (config `language`; first run: the language they write in). Replies short: the
action first, a few lines. Ask EVERY question with **AskUserQuestion** (≤ 4 options per question, the recommended
option first and marked "(polecane)"), never as an A/B/C text list.
Option labels: the labels below are Polish; translate them to the user's language, keep the mapping (e.g. Wypalone →
burn, whatever the label says).

Hard rules:
- Claude never runs `sudo` and never types or handles a password. Commands that need `sudo`: the user runs them himself
  with `! <command>` in this chat.
- Claude never signs in for the user (HeyGen, API dashboards): the user runs the login command himself.
- Never ask for an API key, never write it to a file, never echo it. Only check that the variable is set (`$CM doctor` → `keys`).
- Any failing step: one line with the cause + the fix. Do not continue past missing dependencies.
- Long-running commands (`setup.sh`, `$CM models`, the first `$CM selftest`, `$CM smoke`): Bash timeout 600000 or
  run_in_background: true; on timeout re-run — downloads resume.

Set the CLI (setup venv first, so a dev `cutmate` on PATH never shadows it) — re-run this line after step 4:
`CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`

## 0. Re-run

If `${CUTMATE_HOME:-$HOME/.cutmate}/config.json` exists and the CLI runs:

- **Stale install:** `$CM doctor` → `plugin_root`. It differs from `${CLAUDE_PLUGIN_ROOT}` (the plugin was updated or
  moved, the venv still points at the old copy) → run detect (step 1) and re-run step 4's `setup.sh` with the same
  flags as before (`--gpu <gpu.kind>` from detect, `--local` when config `transcription` is `local`; Windows:
  `setup.ps1 -Gpu … -Local`), then go on.
- **Finished?** Setup is finished ⇔ the smoke render exists: `${CUTMATE_HOME:-$HOME/.cutmate}/smoke/rec/out/final.mp4`
  (only step 10 creates it; config.json alone proves nothing — it already holds defaults after step 5).
  - Marker missing (an earlier run stopped, e.g. paused for an API key): `$CM config show`, then run the pending part
    without asking which section — the API-key check (API backends) and step 6 (selftest), then steps 7–10.
  - Marker present: `$CM config show`, summarise it in ≤ 5 lines, then ask "Którą sekcję zmienić?" (multiSelect:
    Transkrypcja / GPU / język · Muzyka · Napisy · Kroki) and run only those sections (Transkrypcja / GPU / język =
    steps 3, 5, 6 — and step 4 when the package set changes, e.g. an API backend → local; Muzyka = 7; Napisy = 8;
    Kroki = 9). After a transcription change run `$CM selftest` again (step 6); after a music or captions change run
    `$CM smoke` again (step 10).

Otherwise (no config.json) run the whole wizard below.

**Paused for an API key** (the previous run stopped at step 5 because the key was unset; the marker is missing): config
has an API backend (groq / openai / elevenlabs) → `$CM doctor` → `keys`. Key now set → step 6 (selftest), then steps
7–10. Still unset → repeat the step-3 instructions (profile export / setx, restart Claude Code) and stop.

## 1. Detect

`bash "${CLAUDE_PLUGIN_ROOT}/install/detect.sh"` (Windows: `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}\install\detect.ps1"`).
It prints JSON: `os`, `pkg`, `gpu.kind` (nvidia / apple / none), `tools`, `disk_free_gb`, `cutmate.home`, `missing`, `install`.
Summarise in 3 lines (system + GPU, tools found, what's missing). `disk_free_gb < 10` → warn: models + venv take ≈ 8 GB.

## 2. System dependencies

`missing` empty → go on. Otherwise show the `install` commands and ask yes/no.
- Commands with `sudo` (apt, dnf, pacman): the user runs them himself (`! <command>`); Claude never runs sudo. If it
  says it needs a terminal (no TTY for the password prompt): "run it in your own terminal and tell me when done".
- brew / winget: Claude runs them after the yes.
- `pkg` null → manual instructions (where to download each missing tool).

Re-run detect until `missing` is empty — except on Windows after winget installs: Claude Code's shell does not see the
new PATH, so detect would keep reporting them missing. Instead tell the user to
restart Claude Code and run /cutmate:setup again (it resumes here), and stop. Then `npx --yes hyperframes@0.8.157 doctor` and report any problem it shows.

## 3. Transcription

Ask BEFORE installing Python packages (the package set depends on it). Options: local / groq / openai / elevenlabs.
Recommend (first, "(polecane)"): `local` when `gpu.kind` is nvidia (faster-whisper on the GPU) or apple (mlx-whisper);
`groq` when it is none (fast and cheap, CPU-only machines would be slow locally).

API backends need an env var:
- groq → `GROQ_API_KEY` (key: https://console.groq.com/keys)
- openai → `OPENAI_API_KEY` (key: https://platform.openai.com/api-keys)
- elevenlabs → `ELEVENLABS_API_KEY` (key: https://elevenlabs.io/app/settings/api-keys)

Tell the user to add `export NAME=…` to his shell profile himself (Windows: `setx NAME …` in his own terminal) and
restart Claude Code. Never ask for an API key, never write it to a file, never echo it. Do NOT stop here: continue with
steps 4–5 (venv, config, models — none of them need the key). At the end of step 5 check only its presence:
`$CM doctor` → `keys`. Key unset → pause: "zrestartuj Claude Code ze zmienną ustawioną i uruchom /cutmate:setup"
(the re-run lands in step 0 with the marker missing and runs the selftest, then steps 7–10). Key set → go on to step 6.

## 4. Python environment

Ask yes/no: venv at `${CUTMATE_HOME:-$HOME/.cutmate}/venv`, ≈ 3–4 GB (PyTorch, alignment, tracking; + CUDA libraries
for NVIDIA local). On yes:
`bash "${CLAUDE_PLUGIN_ROOT}/install/setup.sh" --gpu <gpu.kind>` plus `--local` when transcription is local
(Windows: `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}\install\setup.ps1" -Gpu <gpu.kind>` plus `-Local`).
It takes minutes: Bash timeout 600000 or run_in_background: true; on timeout re-run — downloads resume. Then set the CLI again (line above) and run
`$CM doctor`. Report problems in one line each. `carve: false` → tell the user to install the HyperFrames plugin
(`/plugin install hyperframes@hyperframes`) — it carves the music under the voice.

## 5. Backend and language

`$CM config set transcription=<backend>`. Ask the language: pl / en → `$CM config set language=<l>`.
Then `$CM models --language <l>` — first say what downloads and roughly how big (local: the whisper model ≈ 3 GB +
the alignment model ≈ 1 GB + the face / pose / hand tracking models (small, tens of MB); API backends: alignment +
tracking only). Long-running: Bash timeout 600000 or run_in_background: true; on timeout re-run — downloads resume.
API backend → now the key check from step 3 (pause if unset).

## 6. Transcription test

Clip: the bundled sample if `${CLAUDE_PLUGIN_ROOT}/samples/<l>.*` exists (then `$CM selftest` with no clip), otherwise
ask the user for the path to one of his recordings where he speaks (the first 30 s are used) →
`$CM selftest --clip <path>`. It prints `backend: … · device: … · compute: …`. The first run loads the model and tries
the CUDA compute types one by one: Bash timeout 600000 or run_in_background: true; on timeout re-run — downloads resume.
NVIDIA + local must show `device: cuda`. If it fell back to CPU: show the WARN reason and `$CM doctor` → `cuda.errors`,
then ask: re-run `setup.sh --gpu nvidia --local` (polecane) or continue on CPU (slower).

## 7. Music

Ask: HeyGen lo-fi catalogue / own folder / none.
- **HeyGen:** `heygen --version` must be ≥ 0.3.0; missing → point to the official install instructions
  https://developers.heygen.com/cli (the user installs it); older than 0.3.0 → the upgrade instructions on the same page
  (the user upgrades it). The user signs in himself: `! heygen auth login --oauth`.
  Verify with `npx --yes hyperframes@0.8.157 media-use resolve --doctor`. Signed in → `$CM config set music.source=heygen`.
  Still not signed in → ask: retry the login (polecane) / no music for now (`$CM config set music.source=none`).
- **Folder:** ask the path → `$CM config set music.source=folder music.folder=<path>`.
- **None:** `$CM config set music.source=none`.

Say that the bed sits at 0.45 under the voice with carve (change only on request: `music.volume`).

## 8. Captions

One AskUserQuestion call with two questions:
- 9:16: Wypalone (polecane) / Plik .srt / Oba / Brak
- 16:9: Plik .srt (polecane) / Wypalone / Oba / Brak

Map Wypalone → burn, Plik .srt → srt, Oba → both, Brak → none:
`$CM config set captions.9:16=<m> captions.16:9=<m>`.

## 9. Steps

multiSelect: Fact-check / QA po renderze / Miniaturka (all recommended) →
`$CM config set steps.factcheck=<true|false> steps.qa=<true|false> steps.thumbnail=<true|false>`.
The theme stays `clean` (the theme wizard comes later).

## 10. Smoke render (5 s)

Music heygen → first resolve a bed:
`npx --yes hyperframes@0.8.157 media-use resolve --type bgm --intent "calm lo-fi" --project "${CUTMATE_HOME:-$HOME/.cutmate}/smoke-bgm" --json`
and pass the local audio file path from that JSON as `--music` (absolute path; check the file exists). Folder music → the first audio file in that folder as `--music`. Then
`$CM smoke --clip <path> --music <file>` (drop `--clip` when there is no recording, drop `--music` for none; the clip
must be ≥ 2 s — the step-6 clip is fine). It renders —
Bash timeout 600000 or run_in_background: true; on timeout re-run — downloads resume. It prints `final:` and `frame:`.
READ the `frame:` PNG (at 1.5 s: title + caption), show it, and report the finalize line printed during the render (`final.mp4: WxH fps … LUFS — OK` or `SPEC MISMATCH`).

Done → summary in ≤ 5 lines: config path (`${CUTMATE_HOME:-$HOME/.cutmate}/config.json`), the CLI path, backend +
device, music, next step: `/cutmate:edit <folder>`.
