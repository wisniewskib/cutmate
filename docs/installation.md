# Installation

After this guide you will have the cutmate plugin in Claude Code, a Python environment in `~/.cutmate/venv` with the models downloaded, and a 5-second test render that proves everything works.

The short version: install the plugin, then run `/cutmate:setup`. The wizard does the rest and asks before it installs anything. This page explains what it does on each OS, so you can install things yourself or fix them when something fails.

## 1. Install the plugin

cutmate declares a dependency on the HyperFrames plugin (`hyperframes@hyperframes`). Add both marketplaces in Claude Code, then install cutmate:

```text
/plugin marketplace add heygen-com/hyperframes
/plugin marketplace add wisniewskib/cutmate
/plugin install cutmate@cutmate
```

If the HyperFrames plugin did not come along with cutmate, install it as well: `/plugin install hyperframes@hyperframes`. cutmate needs its audio skill to duck the music under the voice (the "carve"). Without it, the music bed simply stays at a flat level.

### From a local clone (development, or no marketplace)

```bash
git clone https://github.com/wisniewskib/cutmate.git
claude --plugin-dir ./cutmate
```

## 2. System dependencies

| Tool | Needed for | Minimum |
|---|---|---|
| Python | The `cutmate` CLI (in its own venv) | 3.10, with `venv` / `ensurepip` |
| Node.js + `npx` | HyperFrames (`npx --yes hyperframes@0.8.157 …`) | 22 |
| ffmpeg | Cutting, loudness, frames | Any recent build |
| Chrome / Chromium / Edge | `cutmate shot` page screenshots only | Any |

The wizard runs a detector that installs nothing and prints JSON: OS, package manager, GPU, tools found, free disk space, and what is missing together with the command to install it. You can run it yourself:

**Linux / macOS / Windows Git Bash**

```bash
bash install/detect.sh
```

**Windows PowerShell**

```powershell
powershell -ExecutionPolicy Bypass -File install\detect.ps1
```

These are the install commands the detector suggests:

| OS | ffmpeg | Python | Node.js 22+ |
|---|---|---|---|
| Ubuntu / Debian (apt) | `sudo apt-get install -y ffmpeg` | `sudo apt-get install -y python3 python3-venv` | `sudo snap install node --classic --channel=22/stable` |
| Fedora (dnf) | `sudo dnf install -y ffmpeg-free` | `sudo dnf install -y python3` | `sudo dnf install -y nodejs22` |
| Arch (pacman) | `sudo pacman -S --needed ffmpeg` | `sudo pacman -S --needed python` | `sudo pacman -S --needed nodejs npm` |
| macOS (Homebrew) | `brew install ffmpeg` | `brew install python@3.12` | `brew install node` |
| Windows (winget) | `winget install -e --id Gyan.FFmpeg` | `winget install -e --id Python.Python.3.12` | `winget install -e --id OpenJS.NodeJS.LTS` |

> **Claude never runs `sudo` and never types a password.** When a command needs `sudo`, you run it yourself, either in the Claude Code chat with a leading `!` (for example `! sudo apt-get install -y ffmpeg`) or in your own terminal. Claude runs `brew` and `winget` commands only after you say yes.

> **Windows:** after a `winget` install, restart Claude Code so its shell sees the new `PATH`, then run `/cutmate:setup` again. It resumes where it stopped.

## 3. The Python environment

The setup script creates `${CUTMATE_HOME:-~/.cutmate}/venv`, installs cutmate into it in editable mode, and then fetches GSAP (see [libraries.md](libraries.md#gsap)). Set `CUTMATE_HOME` to put cutmate's home somewhere else.

**Linux / macOS / Windows Git Bash**

```bash
bash install/setup.sh --gpu nvidia --local     # NVIDIA GPU, local Whisper
bash install/setup.sh --gpu apple --local      # Apple Silicon, local Whisper (mlx-whisper)
bash install/setup.sh --gpu none               # CPU-only machine with an API backend
```

**Windows PowerShell**

```powershell
powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Gpu nvidia -Local
powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Gpu none
```

| Flag (`setup.sh` / `setup.ps1`) | Effect |
|---|---|
| `--gpu nvidia\|apple\|none` / `-Gpu nvidia\|none` | Which GPU to target. `apple` is accepted by `setup.sh` only. |
| `--local` / `-Local` | Also installs local Whisper: `faster-whisper` (NVIDIA / CPU) or `mlx-whisper` (Apple). With NVIDIA it also installs the CUDA 12 libraries `nvidia-cublas-cu12` and `nvidia-cudnn-cu12==9.*` from pip. |
| `--dry-run` / `-DryRun` | Prints the commands without running them |

Every install gets the `align` (PyTorch + transformers) and `track` (MediaPipe) extras. On anything but Apple, PyTorch comes from the CPU wheel index, because alignment runs fine on the CPU. The venv takes about 3–4 GB.

When the script finishes it prints where the CLI is:

| OS | CLI path |
|---|---|
| Linux / macOS | `~/.cutmate/venv/bin/cutmate` |
| Windows | `~/.cutmate/venv/Scripts/cutmate.exe` (`%USERPROFILE%\.cutmate\venv\Scripts\cutmate.exe`) |

The skills find the CLI on their own. To run it by hand:

```bash
# Linux / macOS
~/.cutmate/venv/bin/cutmate doctor
# Windows Git Bash
~/.cutmate/venv/Scripts/cutmate.exe doctor
```

```powershell
# Windows PowerShell
& "$HOME\.cutmate\venv\Scripts\cutmate.exe" doctor
```

The rest of these docs write the command as just `cutmate`.

## 4. Transcription backend, GPU and models

| Backend | Runs on | Model | Needs |
|---|---|---|---|
| `local` | NVIDIA GPU (CUDA), Apple Silicon or CPU | Whisper large-v3 (`faster-whisper`; `mlx-whisper` on Apple) | `--local` at setup, about 3 GB download |
| `groq` | Groq API | `whisper-large-v3` | `GROQ_API_KEY` |
| `openai` | OpenAI API | `whisper-1` | `OPENAI_API_KEY` |
| `elevenlabs` | ElevenLabs API | `scribe_v2` | `ELEVENLABS_API_KEY` |

The wizard recommends `local` when it finds an NVIDIA or Apple GPU, and `groq` when it finds no GPU, because large-v3 on a CPU is slow.

```bash
cutmate config set transcription=local language=en
cutmate models --language en       # alignment model + face/hand tracking models (+ Whisper for local)
cutmate selftest --clip ~/Videos/take1.mp4
```

`selftest` transcribes the first 30 s of your clip and prints, for example, `backend: local · device: cuda · compute: float16`.

### NVIDIA / CUDA

- You need only a working NVIDIA driver (`nvidia-smi` must run). You do **not** need a system CUDA toolkit: cuBLAS and cuDNN come from pip and cutmate loads them itself.
- cutmate tries `float16` first. If that fails, for example when a 6 GB card runs out of memory, it retries with `int8_float16`, and only then falls back to the CPU with a `WARN` line.
- If `selftest` shows `device: cpu` on an NVIDIA machine, look at `cutmate doctor` → `cuda.errors`, then run `setup.sh --gpu nvidia --local` again.

### Apple Silicon

`setup.sh --gpu apple --local` installs `mlx-whisper`, and cutmate picks it automatically (model `mlx-community/whisper-large-v3-mlx`).

## 5. API keys: environment variables only

cutmate reads API keys **only** from environment variables. It never stores them in `config.json`: `cutmate config set` refuses any key it does not know, and it never echoes what you typed. Never paste a key into the chat.

| Backend | Variable | Where to get a key |
|---|---|---|
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| ElevenLabs | `ELEVENLABS_API_KEY` | https://elevenlabs.io/app/settings/api-keys |

Set the variable yourself, then **restart Claude Code** so it inherits the variable.

**Linux / macOS** (add the line to `~/.bashrc`, `~/.zshrc` or your shell's profile):

```bash
export GROQ_API_KEY=your-key-here
```

**Windows** (in your own PowerShell or cmd window; it applies to new processes):

```powershell
setx GROQ_API_KEY "your-key-here"
```

Check that the key is visible without printing it: `cutmate doctor` → `"keys": {"GROQ_API_KEY": true, …}`.

## 6. Music (optional) and HeyGen sign-in

| Source | Setup |
|---|---|
| `none` | Nothing to do |
| `folder` | `cutmate config set music.source=folder music.folder=~/Music/beds`. The folder needs at least one `.mp3 .m4a .wav .ogg .flac .aac` file. |
| `heygen` | A lo-fi catalogue through HyperFrames `media-use`. It needs the [HeyGen CLI](https://developers.heygen.com/cli) 0.3.0 or newer, and **you sign in yourself**. |

To use HeyGen, install the CLI from the official instructions, then sign in from the chat or your own terminal:

```text
! heygen auth login --oauth
```

Then check that you are signed in and switch to it:

```bash
npx --yes hyperframes@0.8.157 media-use resolve --doctor
cutmate config set music.source=heygen
```

Claude never signs in on your behalf. If you are not signed in, an edit simply goes ahead without music. See [configuration.md](configuration.md#music) for volume and carve.

## 7. Smoke test

```bash
cutmate smoke --clip ~/Videos/take1.mp4                  # 5 s render: title + captions
cutmate smoke --clip ~/Videos/take1.mp4 --music bed.mp3  # with a music bed
```

It prints `final:` (the MP4) and `frame:` (a PNG at 1.5 s). A good run ends with a finalize line like `final.mp4: 1080x1920 30/1 h264 + aac, 5.00s, -14.0 LUFS — OK`. `/cutmate:setup` treats `~/.cutmate/smoke/rec/out/final.mp4` as the sign that setup is finished.

## Troubleshooting with `cutmate doctor`

`cutmate doctor` prints a JSON health report and never fails. Read it field by field:

| Field | Healthy value | If not |
|---|---|---|
| `python`, `venv` | 3.10+, the cutmate venv | Run `setup.sh` / `setup.ps1` again |
| `ffmpeg` | `true` | Install ffmpeg (table above) and restart Claude Code |
| `node` | `v22…` or newer | Install Node.js 22+ |
| `packages.faster_whisper` / `mlx_whisper` | `true` for `local` | `setup.sh … --local` |
| `packages.align` / `packages.track` | `true` | `setup.sh` again |
| `cuda.devices`, `cuda.errors` | ≥ 1 device, no errors (NVIDIA) | Update the driver, `setup.sh --gpu nvidia --local` |
| `models.whisper`, `align_pl` / `align_en`, `pose`, `hand` | `true` | `cutmate models --language <pl\|en>` (downloads resume) |
| `keys` | `true` for your API backend | Set the variable and restart Claude Code |
| `carve` | `true` | `/plugin install hyperframes@hyperframes` |
| `config` | `ok` | Run `/cutmate:setup` (it rewrites a broken config) |
| `vendor` | `ok` | `cutmate vendor` (downloads GSAP, sha-checked) |
| `plugin_root` | Your current plugin folder | The plugin moved or was updated: run `/cutmate:setup` again |

### Common problems

| Symptom | Fix |
|---|---|
| `cutmate: npx not found (Node.js ≥ 22 needed)` | Install Node.js 22+, restart Claude Code |
| `vendored library … not found` at build time | `cutmate vendor` |
| `alignment models not installed. Run /cutmate:setup.` | `cutmate models --language <l>` |
| `selftest` shows `device: cpu` on NVIDIA | `cutmate doctor` → `cuda.errors`; `setup.sh --gpu nvidia --local` |
| `WARN hyperframes check ran out of time` | A busy machine, not an error: the render goes on |
| `Chrome not found` from `cutmate shot` | Install Google Chrome, or put a screenshot into `broll/` yourself |
| A download timed out (`cutmate models`, the first `selftest`) | Run the same command again: downloads resume |
| Windows: a tool installed with winget is still "missing" | Restart Claude Code, then run `/cutmate:setup` again |

Still stuck? Open an issue with the output of `cutmate doctor`. It contains no API keys, only `true` / `false` for each key variable.
