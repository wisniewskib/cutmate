# Libraries, models and licences

This page lists everything cutmate uses: what it is, which version, its licence, and why cutmate needs it. cutmate itself is [MIT](../LICENSE). Each third-party component keeps its own licence.

Versions are the ones pinned in `pyproject.toml`, `assets/vendor/MANIFEST.json`, `core/cutmate/hf.py` and the model IDs in the code. Python package licences are as declared in each package's metadata.

## JavaScript libraries (vendored, offline)

These files are loaded into the HyperFrames composition. They are pinned with a sha256 per file in [`assets/vendor/MANIFEST.json`](../assets/vendor/MANIFEST.json), and their licence texts are in [`assets/vendor/LICENSES/`](../assets/vendor/LICENSES/). Builds copy only the libraries a project uses, and they never fetch from a CDN.

| Library | Version | Licence | Shipped in repo | Why |
|---|---|---|---|---|
| [GSAP](https://gsap.com) + DrawSVG, MorphSVG, MotionPath, SplitText | 3.14.2 | GSAP Standard "no charge" license | **No** (fetched by `cutmate vendor`) | The timeline that every theme component animates on (one paused, seekable timeline) |
| [three.js](https://threejs.org) + RoomEnvironment, TextGeometry, FontLoader, GLTFLoader, EffectComposer / RenderPass / UnrealBloomPass / OutputPass / ShaderPass / SavePass / MaskPass, Copy / LuminosityHighPass / Output shaders, BufferGeometryUtils, Droid Sans Bold and Helvetiker Bold typefaces | 0.181.2 | MIT | Yes | 3D effects: exploded-view, globe, burst-out, showcase-3d, energy-ball; bloom glow; 3D text (Droid Sans Bold covers Polish letters) |
| [postprocessing](https://github.com/pmndrs/postprocessing) | 6.39.5 | Zlib | Yes | pmndrs post-processing passes, loaded only when an effect imports `postprocessing` (or calls `U.post`) |
| [anime.js](https://animejs.com) | 4.5.0 | MIT | Yes | `kinetic-word` (hundreds of shapes flying into letterforms) and custom effects (`U.anime`) |
| [lottie-web](https://github.com/airbnb/lottie-web) | 5.12.2 | MIT | Yes | Lottie animations in custom effects (`U.lottie`) |
| [KaTeX](https://katex.org) + fonts | 0.19.0 | MIT | Yes | Math formulas in effects (`U.tex`) |
| [Rough.js](https://roughjs.com) | 4.6.6 | MIT | Yes | Hand-drawn style for `flow` (`style: "rough"`) and `U.rough` |
| [D3](https://d3js.org) | 7.9.0 | ISC | Yes | Available to custom effects (data, scales, shapes); loaded only when an effect uses it |

### GSAP

GSAP's standard licence ([gsap.com/standard-license](https://gsap.com/standard-license)) lets you use GSAP for free, but it does not clearly allow redistributing its files in a third-party repository. So cutmate **does not ship GSAP**. `MANIFEST.json` marks it `"redistribute": false` and keeps only the file hashes and the licence text.

`cutmate vendor` (run automatically by `install/setup.sh` and `install/setup.ps1`) downloads the five files from `https://cdn.jsdelivr.net/npm/gsap@3.14.2/` into `~/.cutmate/vendor/gsap@3.14.2/`. It checks each against its sha256 and writes nothing that fails the check. `cutmate doctor` → `vendor` reports whether it is present. `.gitignore` excludes `assets/vendor/gsap@*/`, so a maintainer's local copy is never committed.

## Rendering

| Tool | Version | Licence | Why |
|---|---|---|---|
| [HyperFrames](https://github.com/heygen-com/hyperframes) (npm CLI, run with `npx`) | 0.8.157 (pinned) | Apache-2.0 | Renders the HTML composition to MP4 in headless Chrome; also `check`, `snapshot`, `remove-background` (speaker cut-out for `bg` effects) and `media-use` (music beds and images) |
| HyperFrames Claude Code plugin | From its marketplace | Apache-2.0 | Its audio skill's carve script ducks the music bed under the voice |
| [Node.js](https://nodejs.org) | ≥ 22 | MIT | Runs HyperFrames |
| [ffmpeg](https://ffmpeg.org) | System install | LGPL / GPL (depends on the build) | Decoding, cutting, loudness (`loudnorm`), frames, contact sheets, preview |
| Google Chrome / Chromium / Edge | System install | Vendor licence | `cutmate shot` page screenshots only |

cutmate calls ffmpeg, Node.js and Chrome as external programs. It does not bundle or link them.

## Python packages

Installed into `~/.cutmate/venv` by `install/setup.sh` / `install/setup.ps1`.

| Package | Constraint | Licence | Extra | Why |
|---|---|---|---|---|
| numpy | ≥ 1.24 | BSD-3-Clause (plus bundled permissive licences) | core | Audio arrays: RMS scans, QA, alignment |
| Pillow | ≥ 10.1 | MIT-CMU | core | Contact sheets, thumbnails, preview plates, colour extraction |
| requests | ≥ 2.31 | Apache-2.0 | core | API backends (Groq, OpenAI, ElevenLabs) |
| fontTools | ≥ 4.47 | MIT | core | Font checks: Polish glyph coverage, digit sheets |
| faster-whisper (+ CTranslate2) | ≥ 1.2, < 2 | MIT | `faster` | Local Whisper large-v3 on NVIDIA GPU or CPU, with word timestamps |
| mlx-whisper | ≥ 0.4.3 | MIT | `mlx` | Local Whisper large-v3 on Apple Silicon |
| torch | ≥ 2.2 | BSD-style (see its package metadata) | `align` | Runs the wav2vec2 aligner (CPU wheel on Windows / Linux) |
| transformers (+ huggingface_hub) | ≥ 4.40 | Apache-2.0 | `align` | Loads wav2vec2 and downloads models from the Hugging Face Hub |
| mediapipe | ≥ 0.10.20 | Apache-2.0 | `track` | Face, hand, fingertip and pointing tracking |
| nvidia-cublas-cu12, nvidia-cudnn-cu12 9.x | From pip | NVIDIA software licence | NVIDIA + `--local` | CUDA 12 runtime libraries for faster-whisper, so no system CUDA toolkit is needed |
| pytest, responses | ≥ 8, ≥ 0.25 | MIT, Apache-2.0 | `dev` | Tests |

## Models

| Model | Source | Licence | Used for | Size |
|---|---|---|---|---|
| Whisper large-v3, [`Systran/faster-whisper-large-v3`](https://huggingface.co/Systran/faster-whisper-large-v3) | OpenAI, converted to CTranslate2 | MIT | Local transcription (NVIDIA / CPU) | ≈ 3 GB |
| Whisper large-v3, [`mlx-community/whisper-large-v3-mlx`](https://huggingface.co/mlx-community/whisper-large-v3-mlx) | OpenAI, converted to MLX | MIT | Local transcription (Apple Silicon) | ≈ 3 GB |
| [`jonatasgrosman/wav2vec2-large-xlsr-53-polish`](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-polish) | Hugging Face | Apache-2.0 | Polish word alignment (captions) | ≈ 1 GB |
| [`jonatasgrosman/wav2vec2-large-xlsr-53-english`](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-english) | Hugging Face | Apache-2.0 | English word alignment (captions) | ≈ 1 GB |
| MediaPipe Pose Landmarker Lite (`pose_landmarker_lite.task`, float16) | Google (storage.googleapis.com), sha256-checked | Apache-2.0 | Face position, pointing | Tens of MB |
| MediaPipe Hand Landmarker (`hand_landmarker.task`, float16) | Google, sha256-checked | Apache-2.0 | Palms, fingertips, open-palm detection | Tens of MB |

`cutmate models` downloads them. The Hugging Face models go to the Hugging Face cache, and the MediaPipe models go to `~/.cutmate/models/`.

### API transcription models

| Backend | Model | Terms |
|---|---|---|
| Groq | `whisper-large-v3` | Groq's terms of service; your key, your account |
| OpenAI | `whisper-1` | OpenAI's terms of service |
| ElevenLabs | `scribe_v2` | ElevenLabs' terms of service |

With an API backend, cutmate uploads the clip audio (re-encoded to mono 16 kHz MP3) to that provider. With `local`, audio never leaves your machine.

## Bundled assets

| Asset | Source | Licence |
|---|---|---|
| Inter (Medium, ExtraBold, Black), the `clean` theme font | [rsms/inter](https://github.com/rsms/inter) v4.1 | SIL Open Font License 1.1 ([`themes/clean/fonts/OFL-inter.txt`](../themes/clean/fonts/OFL-inter.txt)) |
| Sound effects: `whoosh`, `pop`, `click`, `impact`, `swell`, `ping` | [Kenney.nl](https://kenney.nl) interface, impact and sci-fi packs | CC0 1.0 ([`assets/sfx/LICENSES.md`](../assets/sfx/LICENSES.md)) |
| Globe land dots and country labels (`globe/land.json`, `countries.json`) | [Natural Earth](https://www.naturalearthdata.com) 1:110m Admin 0, v5.1.2 | Public domain ([`SOURCE.txt`](../themes/clean/components/custom/globe/SOURCE.txt)) |
| README banner art | Generated for this project | MIT, with the repo |

Fonts you add to your own themes come only from Google Fonts under the OFL. `cutmate theme font` refuses anything else and saves the `OFL-<family>.txt` next to the font files.

## Optional tools you install yourself

| Tool | Used by | Notes |
|---|---|---|
| [HeyGen CLI](https://developers.heygen.com/cli) ≥ 0.3.0 | Music beds (`music.source=heygen`), AI images | You install it and sign in yourself (`heygen auth login --oauth`) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | `/cutmate:clone-style` with a link | Downloads one public video for style analysis, only after you say yes; never with cookies or a login |
