# Usage: editing a video

This guide takes you from a folder of raw takes to a finished video, and shows where you step in along the way.

## Before you start

- `/cutmate:setup` has finished (see [installation.md](installation.md)).
- Put **all takes of one video in one folder**: phone clips (`.mov`, `.mp4`, …) or camera files, in any order. Retakes, false starts and talking to the camera between takes are fine. Removing them is cutmate's job.
- Optional: put b-roll (screenshots, images, logos, clips) in `<folder>/broll/`.

cutmate **never modifies your source clips**. Everything goes to `<folder>/out/`.

## Start an edit

```text
/cutmate:edit ~/Videos/caveman-short
```

You can add context in the same message, for example names that Whisper might misspell, a theme, or requests:

```text
/cutmate:edit ~/Videos/caveman-short — product names: Claude, Caveman, GitHub. Use the neon-pill theme. Add explainers.
```

The format comes from the clips: all portrait means a **9:16 short**, all landscape means a **16:9 long-form** video, and a mix makes Claude ask you once which one to make.

## What happens, step by step

| Step | What Claude does | Written to `out/` |
|---|---|---|
| 1. Transcribe | Transcribes every clip word by word, prompted with your proper names. Flags `SUSPECT long word` windows that hide a stumble. | `work/<clip>/transcript.json`, `silences.json`, `<stem>.wav` |
| 2. Look | Makes contact sheets of frames and **reads them**: looking away, reading notes, framing jumps, pointing | `sheets/*.png` |
| 2b. Outline (16:9) | Chapters with titles, clips and time ranges | `outline.md` |
| 3. Pick takes | Re-transcribes suspicious windows (`probe`), scans loudness (`rms`), compares every take of each repeated line, and writes down a reason for each choice | `takes.md` |
| 4. Fact-check | Checks every number, price, date, version and "first / only / free" claim with a web search and the source page | `factcheck.md` |
| 5. Cut | Cuts on silence boundaries, snaps cuts to the frame grid, levels each segment, adds short audio fades | `edl.json`, `aroll.mp4` |
| 6. Align | Word-level timings for captions (wav2vec2 forced alignment) | `work/aligned_words.json` |
| 7. Track | Face, hand and pointing positions over time, when an effect needs them | `work/tracks.json` |
| 8. Plan | Captions, graphics, explainers, effects, the panel (split-panel themes), music | `plan.json` |
| 9. Checkpoint | **"zrozumiałem tak"**: the list of what Claude will do (see below) | `requests.md` |
| 9b. Preview (16:9) | A fast 480p preview of the cut with chapter plates, for your OK | `preview.mp4`, `chapters.txt` |
| 10. Build | Turns the plan into a HyperFrames project, then snapshots and reads frames | `composition/`, `snapshots/` |
| 11. Render | Check, render, then finalize to −14 LUFS with a spec check | `final.mp4`, `check_*.png` |
| 12. QA | Re-transcribes the cut to catch missed repeats; checks music and SFX levels against the voice | Report in the chat |
| 13. Thumbnail | A frame with a strong expression plus a title and a hook | `thumbnail.png`, `thumbnail.jpg` |
| 14. Notes | The final structure, every graphic and why, music, the commands used | `EDIT_NOTES.md` |

Steps 4 (fact-check), 12 (QA) and 13 (thumbnail) are optional. Turn them on or off with `steps.factcheck`, `steps.qa` and `steps.thumbnail` (see [configuration.md](configuration.md)).

**Resuming:** if you run `/cutmate:edit` again on the same folder, Claude continues from the first missing file in `out/`.

### When Claude stops and asks

Claude pauses in only a few places:

1. **A claim fails the fact-check** (❌ or ⚠️). You choose: use another take that says it right, cut the line, re-record it, or keep it with an on-screen correction.
2. **Mixed formats**: which format to make.
3. **The "zrozumiałem tak" checkpoint**: when you made any requests.
4. **The 16:9 preview**: always for long-form, before the slow full render (a 15-minute video takes about 45–60 minutes to render).

## Requests: in chat or spoken in the recording

You can ask for things in two ways:

- **In chat:** "put a space background behind me at 0:41", "add explainers", "a counter on the 75%".
- **Out loud, while recording:** director notes addressed to the editor, such as "here you put a stat card", "add a globe here", "move me somewhere else". cutmate recognises these lines in the transcript, turns them into requests and **cuts them out of the video**, unless they are also content.

Claude collects every request into `out/requests.md`, one line each:

```text
- [<source>] <what> → <target> [@ <anchor>]
```

| Part | Values |
|---|---|
| source | `[czat]` (chat), `[nagranie <clip> <time>]` (spoken in a recording), `[uwagi <mm:ss>]` (your feedback after a render), `[niespodzianka]` (a surprise Claude added) |
| target | A component (`counter`, `split`, `stamp` …), `custom:<name>`, `explainers`, `cut` or `skip` |
| anchor | A segment (`S5`), a word in a segment (`S7:Rasengan`) or a time in the cut video (`41.0` or `0:41`; matches within ±1 s) |

Example:

```text
- [czat] space background behind me → bg @ 0:41
- [nagranie IMG_6050.MOV 12.3] globe with the countries → custom:globe @ S4:świecie
- [niespodzianka] gem on "meet" → custom:burst-out @ S2:poznajcie
```

Before the checkpoint, Claude runs `cutmate requests <folder>/out`. It matches each line against `plan.json` and prints `OK`, `MISSING`, `BAD` or `NOTE` per request (surprises get a `SURPRISE` prefix), followed by a summary such as `requests: 5 ok, 0 missing, 0 bad`. Claude fixes every `MISSING` and `BAD` before it shows you anything.

### "Zaskocz mnie" (surprises)

When you ask for effects or explainers, Claude may add 1–3 surprises of its own: an effect on a gesture, a WOW effect on the key moment, or a stamp on the punchline. They are logged as `[niespodzianka]` and flagged in the checkpoint list, so you can strike them. Say "bez niespodzianek" (no surprises), or simply "no surprises", to turn them off. A plain cut with no requests never gets surprises.

## The "zrozumiałem tak" checkpoint

"Zrozumiałem tak" means "here's what I understood". Right before the build, Claude shows you a list like this:

```text
zrozumiałem tak:
- [czat] space background → bg @ 0:41                     OK
- [nagranie IMG_6050.MOV 12.3] globe → custom:globe @ S4   OK
- [niespodzianka] burst on the open palm @ 18.2            SURPRISE OK
- [wow] kinetic-word → "+300%" @ S6:wystartowało
```

Reply OK, or strike or change lines ("drop the burst", "move the globe to the next sentence"). Claude maps your changes, runs `cutmate requests` again, and only then builds and renders. With a split-panel theme, the list also shows the panel timeline, one line per item (for example `0.00–1.40 stat-card 44%`).

If you made no requests, there is no pause: the same information goes into `EDIT_NOTES.md`.

## After the render: feedback

Watch `final.mp4` and reply with timestamps:

```text
1:12 the chip covers my mouth; 2:03 cut the "um"; 2:40 make the globe red
```

Each note is logged as `[uwagi <mm:ss>]` in `requests.md`. All changes are batched into one rebuild and one render. When a fix touches the cut (the EDL), graphics move with their words automatically.

## Saving an effect for later

When Claude wrote a new effect for this video (in `out/custom/<name>.html`) and you accepted it, Claude asks once whether to save it into your theme:

```bash
cutmate save-effect ~/Videos/caveman-short/out space-bg --description "starfield behind the speaker"
```

From then on, every video with that theme can use it. See [effects.md](effects.md#saving-an-effect).

## Outputs

Everything lives in `<folder>/out/`:

| File | What it is |
|---|---|
| `final.mp4` | The finished video: 1080×1920 (9:16) or 1920×1080 (16:9), 30 fps, H.264 + AAC, −14 LUFS |
| `thumbnail.png`, `thumbnail.jpg` | The thumbnail: 1080×1920 for shorts, 1280×720 for 16:9 (when `steps.thumbnail` is on) |
| `chapters.txt` | 16:9: chapter timestamps to paste into the YouTube description |
| `captions.srt` | When the caption mode for the format is `srt` or `both` (default for 16:9) |
| `EDIT_NOTES.md` | Final structure, every graphic and why, music, scene sources, commands used |
| `takes.md` | Every take compared, the chosen one and why; the checks for each segment |
| `factcheck.md` | One line per claim: timestamp, quote, verdict, the correct version, a link |
| `requests.md` | Your requests and Claude's surprises |
| `edl.json` | The cut: segments with source file, in / out and the corrected text |
| `plan.json` | Graphics, captions, panel, scenes, music |
| `aroll.mp4` | The cut A-roll (voice levelled, no graphics) |
| `preview.mp4` | 16:9 only: the 480p checkpoint preview |
| `composition/` | The HyperFrames project (HTML, media, vendored libraries) |
| `snapshots/`, `sheets/`, `check_*.png` | Frames Claude read to check its work |
| `work/` | Intermediate files: transcripts, WAVs, aligned words, tracks, `render.log` |

## Tips for better results

- **Say each line until you nail it.** cutmate compares all takes, so extra takes cost you nothing.
- **Say names clearly** and mention them when you start the edit (`product names: …`). They become the transcription prompt.
- **Pause briefly between takes.** Cuts land on silences.
- **Use your hands on purpose.** An open palm toward the camera or a clear point gives effects a place to land.
- **Keep spoken director notes short and addressed to the editor** ("here you put …", "add …"), so they are recognised and cut.
