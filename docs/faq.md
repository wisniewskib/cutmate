# FAQ

## General

**What kind of videos does cutmate edit?**
Talking-head videos: one person speaking to the camera, recorded in several takes. It makes 9:16 shorts (Reels, Shorts, TikTok) and 16:9 long-form YouTube videos. It is not a general-purpose editor for vlogs with lots of b-roll, music videos or multi-camera interviews.

**Which languages are supported?**
Polish (`pl`) and English (`en`) for the video: transcription, alignment and built-in labels. Change it with `cutmate config set language=en`. The skills talk to you in your language either way.

**Do I need a GPU?**
No. Without one, choose an API backend (Groq is fast and cheap) and everything else runs on the CPU. Local Whisper large-v3 needs an NVIDIA GPU or Apple Silicon to be practical. Rendering uses headless Chrome and the CPU.

**Does it work on Windows?**
Yes. Windows, macOS and Linux are all supported. On Windows, Claude Code runs commands through Git Bash; `setup.ps1` and `detect.ps1` are the PowerShell counterparts of the install scripts. See [installation.md](installation.md).

**How long does an edit take?**
It depends on your machine and the video. As a rough guide, a 9:16 short renders in about 1–2 minutes, and a 16:9 video in about 45–60 minutes per 15 minutes of footage. Transcription and Claude's review steps come on top of that. `bg` effects (speaker cut-outs) cost about 17× their duration on a CPU.

**Does cutmate touch my original recordings?**
Never. Everything it makes goes to `<folder>/out/`.

## Privacy and keys

**Where do my API keys go?**
Only into environment variables you set yourself (`GROQ_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`). cutmate never writes them to a file, `cutmate config set` rejects them, and `cutmate doctor` shows only whether each one is set. Never paste a key into the chat.

**Does my audio leave my machine?**
With `transcription=local`, no. With an API backend, the clip audio is uploaded to that provider (re-encoded to a small mono MP3). The fact-check step uses web search. Music and AI images through HeyGen happen only when you signed in to HeyGen yourself.

**Does Claude sign in to anything or run `sudo` for me?**
No. You run `sudo` commands and logins (`heygen auth login --oauth`) yourself, for example with `! <command>` in the chat.

## Editing

**Can I tell it what I want without typing?**
Yes. Say it in the recording, addressed to the editor ("here you put a globe", "add a counter"). cutmate turns these lines into requests and cuts them out of the video. See [usage.md](usage.md#requests-in-chat-or-spoken-in-the-recording).

**What is "zrozumiałem tak"?**
Polish for "here's what I understood". It is the checkpoint before the build: a list of every request and surprise mapped to the plan, which you approve or edit. See [usage.md](usage.md#the-zrozumiałem-tak-checkpoint).

**What is "zaskocz mnie"?**
"Surprise me". For themes, it rolls a random bold look. During edits, Claude adds 1–3 surprise effects when you asked for effects. Say "no surprises" ("bez niespodzianek") to turn that off.

**Claude picked the wrong take. How do I fix it?**
Reply with the timestamp and what you want ("1:12 use the other take of this sentence"). The fix is logged in `requests.md`, the EDL is changed, and the graphics move with their words. `takes.md` shows which takes were compared and why one won.

**Why is there no music?**
`music.source` is `none` by default. Set a folder (`cutmate config set music.source=folder music.folder=…`) or use HeyGen after signing in. If HeyGen is chosen but you are not signed in, the edit goes on without music and says so in `EDIT_NOTES.md`.

**The music is too loud or too quiet.**
`cutmate config set music.volume=0.3` (0–2, default 0.45). Install the HyperFrames plugin so the bed ducks under the voice (`cutmate doctor` → `carve: true`).

**Can I get an `.srt` file for a short too?**
Yes: `cutmate config set captions.9:16=both`. See [configuration.md](configuration.md#captions-per-format).

**Can I edit `plan.json` or `edl.json` by hand?**
Yes. They are plain JSON. Run `cutmate build <out>` and `cutmate render <out>` afterwards (after an EDL change, run `cut`, `align` and `track` first). The build validates everything and names the problem if something is wrong. The formats are in [architecture.md](architecture.md#the-contracts-edljson-and-planjson).

## Themes and effects

**Can I use a creator's style?**
`/cutmate:clone-style` builds a theme that *looks like* a source: palette, font character, shapes, captions, motion and layout. It never copies logos, watermarks, text, images or artwork, and it uses only OFL Google Fonts. Respect the source creator's rights when you publish.

**Can I use any font?**
Only fonts from Google Fonts under the SIL Open Font License, and they need Polish letters for text and display roles. `cutmate theme font` checks both.

**Why did the build reject my effect?**
Effects must be deterministic: no wall-clock time, no `Math.random`, no timers or `requestAnimationFrame`, no playback callbacks, and only vendored libraries. The error names the offending token. See [effects.md](effects.md#determinism-rules).

**Why is GSAP not in the repository?**
Its licence does not clearly allow redistribution. `cutmate vendor` downloads it and checks every file against a pinned sha256. See [libraries.md](libraries.md#gsap).

## Troubleshooting

**Something is broken. Where do I start?**
Run `cutmate doctor` and compare each field with the table in [installation.md](installation.md#troubleshooting-with-cutmate-doctor). Running `/cutmate:setup` again is safe: it resumes and only redoes what is missing.

**I updated the plugin and now things fail.**
Run `/cutmate:setup` once. It notices that the venv points at the old plugin folder and reinstalls it.

**`WARN hyperframes check ran out of time`**
A busy or slow machine, not an error. The render goes on.
