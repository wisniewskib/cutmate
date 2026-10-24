---
name: edit
description: Edit a talking-head short (9:16) or a YouTube long-form video (16:9) from raw takes with cutmate — transcribe, pick the best takes like a human editor, fact-check, cut to -14 LUFS, word-aligned captions, theme graphics (SVG/GSAP via HyperFrames), sound effects, optional music, render, QA and a thumbnail. Use when the user asks to edit / cut / make a short, reel or long-form video from a folder of recordings.
---

# /cutmate:edit <folder>

Talk to the user in their language (config `language`; a language the user names in the chat for this video wins: pass `--language <lang>` to every `$CM` command that takes it and never run `config set` for it — that is a permanent, global change). Never modify source clips. All generated output goes to `<folder>/out/`; `<folder>/broll/` holds inputs only (the user's files and fetched screenshots / images) — never overwrite an existing file there: pick a new unique name (suffix `-2`, `-3`) first.

Set the CLI once per session: `CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`; if it doesn't run, tell
the user to run `/cutmate:setup` and stop. Read the config with `$CM config show` (transcription, language, theme,
steps.factcheck / qa / thumbnail, music, captions).

**Theme:** the config `theme`. A theme the user names in the chat ("w stylu neon-brutal") wins for this video: pass
`--theme <name>` to every `$CM build`, `$CM preview` and `$CM thumb`. Find it with `$CM theme list` (one tab-separated
line per theme: `marker\tname\tkind\tchecked\tpath`; split on tabs: name = 2nd column, path = 5th; paths may contain
spaces on Windows). Use only rows whose kind is not `draft` (a draft of the same name is unfinished work in
`/cutmate:theme`). READ `<path>/frame.md` BEFORE writing plan.json. Marked `unchecked` → run
`$CM theme check <theme> --saved --language <lang>` once (renders every
component in both formats and reports problems; minutes — prefer Bash run_in_background: true, else Bash timeout
600000; `WARN hyperframes check ran out of time` = a busy machine, not an error (it goes on)); lint
errors → tell the user in one line each and offer `/cutmate:theme` or the config theme.

**Layout:** read `layout` from `<path>/theme.json` (the theme's path from `$CM theme list`; no `layout` key = classic).
`split-panel` (9:16 only; a 16:9 video ignores it) → explainers are on without a request: the top part of the frame is
ONE panel for the whole video and you plan its content for every sentence — §5b. Do not fall back to a few chips over
the bare face: a split-panel theme without a full `"panel"` is a failed edit. Classic (or 16:9) → §1c explainer rules
unchanged.

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
  With the WOW opt-in (effects requested, or surprises on — §1c "When") also add top-level `"chapter_fx": "topic-change"`:
  every chapter 2+ plate becomes the topic-change glitch (not counted in the WOW caps); without it, plain plates.
  `point` always sits top-right in 16:9 (its corner is ignored); for pip page screenshots use `$CM shot "<url>" -o … --width 1600 --height 900`.
  Components: `pip` (instead of `split`; `from`, `to`, `media`, `corner?` br|bl, `fit?` cover|contain), `lower-third`
  (`at`, `name`, `role?`) once at the self-introduction, corner graphics as usual. `split` is an error in 16:9.
- **Checkpoint before the full render (always):** `$CM preview <folder>/out` → send the user `out/preview.mp4` and the
  `chapters.txt` lines; wait for OK. Changes → EDL / plan → new preview. Only then build, snapshot, render (a 15-minute
  video renders for ~45–60 min — tell the user the ETA and run `$CM render` in the background, see §7).
- **Outputs:** `final.mp4`, `chapters.txt` (paste into the YouTube description), `captions.srt` when the config's caption
  mode for 16:9 is `srt`/`both` (upload in YouTube Studio), thumbnail.
- **Thumbnail:** 1280×720; pick a frame where the face is on one side and put the text on the other:
  `$CM thumb <folder>/out --at <t> --title "…" --hook "…" --side left|right`.
- Theme check: `$CM theme check <theme>` already renders 16:9 too (see Theme above).

## 1c. Effects on request

The user can ask for things the built-in components don't cover. Collect every request, map it, show it, then build.

**Collect** into `out/requests.md` early, as requests come in (it needs no EDL; `$CM requests` runs later, see Checkpoint), one line each: `- [<source>] <what> → <target> [@ <anchor>]`. Target = component type,
`custom:<name>`, `cut` or `skip`; anchor = segment id (`S5`), word anchor (`S7:Rasengan`) or a time in the cut video (`41.0` seconds or `0:41`; matches ±1 s). Sources:
- `[czat]` — the user's message to you.
- `[nagranie <clip> <time>]` — spoken director notes (polecenia) in the transcript: phrases addressed to the editor, second
  person ("tutaj ma być", "dodaj", "przenosisz mnie", "zrób"). These segments never go into the EDL unless they are
  also content. Jokes / filler with no content ("Test.", "Twerk.") are cut like false starts and listed as `→ cut`.
- `[uwagi <mm:ss>]` — feedback after a render.
- `[niespodzianka]` — your own surprises (see "Zaskocz mnie" below); `$CM requests` lists them with a `SURPRISE` prefix (`SURPRISE OK|MISSING|BAD|NOTE`; the summary counts them like other lines).

Film-wide request "chcę explainery" → `- [czat] explainery → explainers` (a NOTE; the explainers themselves are `→ explainer @ S3`, matched by a `split`/`side` graphic with an `effect`).

**Map:** a built-in component when one fits; `bg` for "inne tło / przenieś mnie gdzie indziej"; `side` for "na połowie
ekranu" (16:9 only); otherwise `custom`. Check saved effects first: `${CUTMATE_HOME:-$HOME/.cutmate}/themes/<theme>/components/custom/index.json`
and the bundled ones in `${CLAUDE_PLUGIN_ROOT}/themes/<theme>/components/custom/index.json` — read BOTH `index.json` files; their formats differ (bundled: `params` = {name: description}, `follow`/`place` booleans, `kind`; user file from `save-effect`: `params` = list, `follow` = string|null).
Bundled: `energy-ball` (params radius, colors; `"follow": "hand"`; hidden without hand samples), explainers `stat-card`, `flow`, `ui-mock`, `iso-machine`, `checklist`, `headline`, VFX/3D `showcase-3d`, `burst`, `hand-sparks`, and the WOW pack below.

**WOW pack** — six stock show-stoppers (`kind` wow in the bundled index.json): `exploded-view`, `globe`, `burst-out`, `hand-control`, `topic-change`, `kinetic-word`.
They are tested, seek-safe, offline (vendored libraries; a build error `vendored library … not found` → run `"$CM" vendor`) and take the theme's tokens, so a cloned style restyles them. READ their `index.json` entries (`params`, `modes`, `impact`) before the first use. They keep their own text out of the burned captions (`P.caption_band`, `U.safeBox(P)`) and burst-out holds beside the face. In a split-panel video the build itself drops the captions from the seam to the bottom band under a WOW scene (`kinetic-word` / `topic-change` / `globe` / `exploded-view` in `"scenes"`; media and other scenes keep them on the seam) and moves them back after it, so the scene's content takes the top area — never move captions or the speaker yourself.
- **When:** WOW effects replace writing a new effect whenever an effect, a surprise or an explainer fits a moment below — never write an `out/custom/` effect for such a moment. In a classic theme (9:16 or 16:9) they need the same opt-in as effects today: a request (chat or spoken), or surprises on (`[niespodzianka]`, Zaskocz mnie below); requested explainers may be `exploded-view` / `globe`. In a split-panel theme `exploded-view` / `globe` are ordinary panel items (`"panel"`, no request needed, §5b) and `kinetic-word` / `topic-change` are scenes (`"scenes"`, §5b); `hand-control` stays a `custom` over the speaker's half; `burst-out` is never used there (it is a `bg`, and a `bg` next to a panel is a build error).

| What is said / shown | Effect | Setup |
|---|---|---|
| "rozłożę to na części", "z czego to się składa", "w środku jest", "warstwy", a device / engine / system being explained | `exploded-view` | `parts` from what is said, else a `preset` |
| "na całym świecie", "globalnie", countries / cities / "w USA i w Chinach", a worldwide number | `globe` | `from` = the speaker's country (PL) unless said; `to` = the named countries |
| the hero reveal: "to zmienia wszystko", "poznajcie", "przedstawiam", the product's name said with emphasis | `burst-out` | as `"type": "bg"`, `"effect": "burst-out"`, `"hit": "<impact word>"`; classic 9:16 / 16:9 only (never with a panel) |
| an open palm held toward the camera, fingers spread, a "conjuring" gesture, "patrzcie" with the hand up | `hand-control` | `card` = the point being made, ≤ 3 lines; run `$CM track --force "<folder>/out"` when the build says so |
| a chapter change (long-form: every chapter 2+ via `"chapter_fx": "topic-change"`) or "a teraz…", "przejdźmy do", "druga sprawa" in a short | `topic-change` | `title` = the next topic, ≤ 40 chars |
| "wystartowało", "start", "odpalamy", a growth / launch / take-off moment, THE number or key phrase of the video ("+300%", "ZA DARMO") | `kinetic-word` | `text` ≤ 14 chars from the sentence; scene in split-panel, `custom` full-frame in classic |

- **Plan entries** (anchors as in §5; params are the index.json ones, all listed here — `?` = optional):
  - `exploded-view` — 9:16 classic `{"type": "split", "from", "to", "effect": "exploded-view", "params": {…}}`, 16:9 the same as `side`, split-panel a panel item `{"at", "until", "effect": "exploded-view", "params": {…}}` (or a scene). Params: `parts` 2–7 `{"label", "shape": "block"|"cylinder"|"disc"|"ring"|"gear"|"board"|"screen"|"shell", "color"?}` from bottom to top, the labels the speaker's words (≤ 2 words each); no parts said → `preset` `"engine"` | `"phone"` | `"layers"`; `axis` `"y"` (default) | `"x"`; `title?`; `bg` `"panel"` | `"none"`. 3–4.5 s (it turns in, explodes with labels, orbits, slams back).
  - `globe` — the same placements as exploded-view. Params: `from` ISO-2 (`"PL"`), `to` 1–6 ISO-2 codes, `labels` `"auto"` (country names in the video language) or a list, `style` `"dots"` | `"solid"`, `title?`. 3–5 s (arcs draw one by one, labels decode at the end).
  - `burst-out` — `{"type": "bg", "from", "to", "effect": "burst-out", "hit": "S4:Claude", "params": {"shape": "gem"|"cube"|"knot"|"sphere"|"logo", "label"?, "media"?, "rays"?, "color"?}}`: `hit` on the impact word (the object lands there with the shake, flash and hit sound; `"hit": true` lands 1 s after `from`), `from` ≥ 1 s before that word, `to` ≥ 1.5 s after it (3–5 s in all). `"logo"` needs `"media": "broll/<logo>.png"`. It needs the face position of its segment (plan `"face"`, or run `$CM track "<folder>/out"` — face is filled from tracks.json). The `bg` cut-out costs ~17× its duration on CPU.
  - `hand-control` — `{"type": "custom", "name": "hand-control", "from", "to", "params": {"card": {"title": "Kontrola gestem", "lines": ["…"]}}}`, 3–6 s over the clearest open-palm moment (READ the sheets and the palm tracks; a still, raised, spread hand — never a fast swing, its sparks trail across the chin). Needs fingertip tracks: `$CM track "<folder>/out"` first; a project tracked before the pack gets the build error `needs fingertip tracks` → `$CM track --force "<folder>/out"` once. 9:16 classic, split-panel (the speaker's half; the panel item stays) and 16:9 (also beside a `side`); never a panel item or a scene. `card.lines` ≤ 3 short lines, `card.media?` (an image next to the recording; or `media?` at the top level), `hand` `"auto"` | `"left"` | `"right"` (leave it out = `"auto"`: the raised open palm; `left` / `right` are the speaker's own hands, so with an unmirrored camera `"right"` is the hand on the screen's LEFT — set a side only when the snapshots show auto took the wrong hand), `sparks` `"tips"` | `"off"`, `colors?` (spark colours [core, body, glow]; default the theme's `--spark` / `--spark-glow` or warm amber).
  - `topic-change` — long-form: top-level `"chapter_fx": "topic-change"` in plan.json (every chapter 2+ plate becomes it: title = the chapter title, kicker `ROZDZIAŁ 02`); do not add topic-change graphics there as well. Short: `{"type": "custom", "name": "topic-change", "from", "to", "params": {"title": "Druga sprawa: koszty"}}` 1.2–2.0 s starting on the transition word ("a teraz", "przejdźmy do"); split-panel: a scene `{"from", "to", "effect": "topic-change", "params": {"title"}}`. `kicker?`, `style` `"glitch"` | `"wave"`.
  - `kinetic-word` — split-panel: a scene `{"from", "to", "effect": "kinetic-word", "params": {"text": "+300%"}}`; classic: `{"type": "custom", "name": "kinetic-word", "from", "to", "params": {"text": "ZA DARMO"}}` full frame — keep the default `"bg": "panel"` (it covers the speaker like a scene); `"bg": "none"` (the video under it) only when the face is off-centre or b-roll is under it, never with the word over the face. 3–4 s (2.5–6). The word lands 1.0 s after `from`: start it about 1 s before the spoken word, or (custom only — scenes take no `hit`) anchor `"hit": "S3:wystartowało"` (≥ 0.6 s after `from`) and it lands exactly there with the shake and hit sound (not checked by the build: an earlier anchor silently lands early). `kicker?`, `count` 300–900, `shapes` `"mixed"` | `"squares"` | `"dots"` | `"dashes"`.
- **Caps:** shorts (the cut video ≤ 90 s, any format; a longer one gets the long-form caps) ≤ 2 WOW effects, ≥ 12 s apart (start to start), `burst-out` and `kinetic-word` once each. Long-form ≤ 1 per minute and ≤ 8 in total, chapter plates (`"chapter_fx"`) not counted. Panel items and scenes count. Never two WOW effects in a row without plain footage between them; never over the face (burst-out holds beside it). A build `WARN wow …` must be fixed before the checkpoint:
  - `WARN wow effects: <n> in <s> s (cap <k>)` → drop the weakest; keep the hero reveal and THE number, make the rest plain components (`stamp`, `headline`, `stat-card`);
  - `WARN wow <name>: <n> in <s> s (cap 1)` → keep that effect on its strongest moment only;
  - `WARN wow <a> and <b> are <x> s apart (min 12)` → move one to another matching moment ≥ 12 s away, or drop it.
- **Facts:** globe countries, kinetic-word numbers and exploded-view part names come only from what is said (card and title text too); numbers need a ✅ line in `factcheck.md` (§3) — the build does not check them.
- **Snapshot loop:** every WOW effect gets a strip every 0.25 s over its span — the §6 snapshot command with `--at a,a+0.25,…,b` (its times in the cut video) — READ before the checkpoint: it reads on a phone, lands on its word, keeps off the face and the captions. "zrozumiałem tak" lists them as `- [wow] <effect> → <what> @ <anchor>` (shown to the user; in `requests.md` a requested or surprise WOW keeps its own source with the target `custom:<effect>`, e.g. `- [niespodzianka] klejnot na „poznajcie” → custom:burst-out @ S4:poznajcie`, and is shown once, by that line — `[wow]` lines are only for WOW effects with no request / surprise line: split-panel panel items and scenes, `chapter_fx`). No checkpoint → those lines go into EDIT_NOTES.md.

**Plan types** (in `plan.json` graphics):
- `{"type": "custom", "name": "<lowercase-dashes>", "from": …, "to": …}` or `"at"` (+ `until`); `"follow": "face"|"hand_left"|"hand_right"|"hand"`
  (needs tracks.json); `"params": {…}` land at the top level of `P` in the effect.
- `{"type": "bg", "from", "to", "media": "broll/…"}` or `"effect": "<name>"`. Media = a file in `broll/`, or an AI image:
  `npx --yes hyperframes@0.8.157 media-use resolve --type image --intent "<what>" --project <folder>/out/composition` when signed in
  (copy it to `broll/` under a new name, never over an existing file). `bg` removes the background from the A-roll: ~17× the duration on CPU. Total `bg` > 30 s → build WARN: ask the user before building.
- `{"type": "side", "from", "to", "media"|"effect", "speaker": "right"|"left"}` — speaker on one half, graphic on the other (16:9 only).
- `face` per segment is filled automatically from tracks.json when missing.

**Explainers** (animated explanations in the `split` panel; classic themes — a split-panel theme puts them in the panel without a request, §5b): only after an explicit request — chat or spoken ("explainer(y)", "wyjaśnij to animacją"), never on your own. Pick moments:
2–4 per 60 s of video, each ≥ 2 s, ≥ 2 s of plain face between two explainers, never on a sentence that already has a requested effect or a `split` with `media`.
Choose from `index.json` by sentence type: a number → `stat-card`, steps / a process → `flow`, a check / comparison → `checklist`, a tool / a chat / a command → `ui-mock`, a mechanism / "how it works" → `iso-machine`, a thing taken apart / its parts → `exploded-view`, countries / worldwide → `globe` (WOW: caps above). Nothing fits → write a new effect in `out/custom/` starting from the closest template.
Text and numbers come ONLY from the sentence. The build does NOT check explainer numbers beyond stat-card `value` and checklist `summary.value` (a WARN when `steps.factcheck` is on; iso-machine `counter.to`, ui-mock counts and checklist row labels are not checked): verify every number against a ✅ line in `factcheck.md` yourself (§3) before you write it.
9:16: `{"type": "split", "from": …, "to": …, "effect": "<name>", "params": {…}}` (panel 1000×820, params go to the effect); 16:9: the same as `{"type": "side", …, "effect", "params", "speaker": "right"|"left"|"gesture"}`.
Templates (params; `?` = optional):
- `stat-card`: value, prefix?, suffix?, label, note?, media? (a file next to the recording, e.g. `broll/shot.png`; build copies it), accent?, layout? (`card` default | `hero` = the number fills the panel)
- `flow`: nodes (2–6), edges?, style (`clean`|`rough`), title?, seed?, accent?
- `ui-mock`: kind (`chat`|`terminal`|`post`|`browser`|`app`), lines [{who: `user`|`ai`|`cmd`, text}] (chat / terminal / post), title?, accent?, replies? / reposts? / likes? (post only: real counts — a number counts up, text is shown as is; leave them out and the post has no counters, never invent them); browser: url, title?, search?, rows (≤ 8) [{text, sub?, badge?}], highlight? (row index circled); app: title (e.g. `Connectors`), search?, rows [{text, sub?, toggle? true|false, click? true, badge?}] (a cursor clicks the `click` rows and their switch flips)
- `iso-machine`: parts (2–5) [{label, shape: `box`|`cylinder`|`funnel`|`screen`|`gear`, color?}], token?, counter? {to, label}, title?, theme (`light`|`dark`|`panel` — `panel` in split-panel themes, it follows the panel colour), accent?
- `checklist`: title?, rows (2–8) [{text, status `ok`|`bad`|`warn`|`info`, label? (e.g. `200 OK`, `404`, `OUTDATED`)}], strike? (bad rows struck through), summary? {value, suffix?, label?} (a big number beside the table), accent?
- `headline`: text (1–6 words from the sentence), kicker?, mode (`type` default | `pop`), accent?
VFX/3D (all support `"place": "gesture"`): `showcase-3d` (shape `torus-knot`|`icosahedron`|`text`|`glb`, text?, model?, color?, size?, x?, y?; GLB via graphic-level `"media": "broll/x.glb"`; default spot: right third; on an open palm it rests on the palm and follows it), `burst` (colors?, size? — 1.2–1.6 for a hero moment, ~1 for a hand close to the face; x?, y?; ~1–1.4 s flash + shockwaves + sparks; default spot: frame CENTRE, i.e. over the face — always pass place or x/y), `hand-sparks` (mode `stream` = energy flowing out of the hands | `sparks` = hot sparks falling; link? = energy arc between the two hands; colors?, size?; uses BOTH hands when placed by gesture).

**Gesture placement:** when a spoken command says "tutaj / tu / tam / w tym miejscu" without naming a place, write `"place": "gesture"` (custom / chip) or `"speaker": "gesture"` (side: the panel goes to the screen side the speaker points to). A named place ("w prawym dolnym rogu", "po lewej") always wins — then do NOT write gesture. `place` is only for `custom` / `chip` and `"speaker": "gesture"` only for `side` (anything else → plan error). What the hand does decides the spot (from the hand-shape tracks): an **open / presenting palm** → the effect sits just above that palm and follows the hand for its whole span (held at the last seen spot when the hand drops out; the effect also gets both palms as `P.hands`); a **clear index-finger point** → the pointed spot, just past the fingertip (never thrown to the frame edge); neither → the higher visible hand. The effect starts at its anchor and takes its position from the nearest hand sample, so anchor it on the GESTURE, not on the word: when the hand comes up before "tutaj", use the time the hand is up (seconds, read from the sheet / tracks) — it still matches the request within ±1 s. A chip centres on the spot (kept inside the safe zone); positions follow punch-ins and the split / side moves. Run `$CM track "<folder>/out"` first (fresh tracks needed; stale → build error; no hand near the anchor → build WARN and the default position; WARN "no pointing data" or "no hand-shape data" → run `$CM track --force "<folder>/out"`).

**Every gesture gets an effect.** Read the sheets (and `work/tracks.json` palm tracks) for EVERY moment the speaker shows with the hands where something should appear — palms framing a spot, a palm held out, both hands spread, a push toward the camera — even without the word "tutaj", and put a visible effect ON the hands there (`"place": "gesture"`): `burst` for a framed spot or a punch, `showcase-3d` resting on a presenting palm, `energy-ball` on a cupped hand, `hand-sparks` `stream` for spread hands, `sparks` + `link` for a trick or an object held in both hands; the clearest open palm with a point to make → `hand-control` (WOW pack, its caps). Clear physical actions (tricks, stunts, a jump at the camera) get one too, as surprises. Size them to read on a phone (an effect smaller than the hand is invisible). Then make a strip of snapshots every 0.25 s over each effect's span and READ it: the effect must sit on / at the hands as they move, be clearly visible, and never cover the face (shrink it or move the anchor if it does).

**Zaskocz mnie (surprises):** on by default whenever effects or explainers are requested; "bez niespodzianek" turns it off (never add surprises to a plain cut).
1–3 per video, ≤ 1 per 15 s, never over the face, never on a sentence with a requested effect — except effects on gestures and physical actions (above): those go on every such moment, logged as surprises, ≥ 1.5 s apart. Use a WOW effect when its moment is there (WOW pack table, within its caps), else `burst`, `showcase-3d`, a `chip` / `stamp` or a small custom effect on a punchline or key word. Log each as `- [niespodzianka] <what> → <target> @ <anchor>` and flag them in the "zrozumiałem tak" list as surprises so the user can strike any.

**Snapshot loop:** every explainer gets at least two snapshots (start and middle, §6), every gesture-placed / hand effect and every WOW effect a strip every 0.25 s over its span, and you READ them before the checkpoint; fix `plan.json` / the effect and rebuild BEFORE showing the "zrozumiałem tak" list.

**Tracking:** if any graphic uses `"follow"`, or you want face-centred punch-ins without reading sheets, run
`$CM track "<folder>/out"` after `cut` (it skips the work when tracks.json is newer than aroll.mp4; `--force` redoes it). After every re-cut run it again: plan/build ignore a tracks.json older than aroll.mp4, and `follow` then fails. Needs mediapipe; otherwise tell the user to run `/cutmate:setup`.

**Writing a custom effect** in `out/custom/<name>.html`: the same `<style>` / `<markup>` / `<script>` sections as theme
components; `ROOT` in style is the effect root. Rules:
- `U.clock(fn)` is the only per-frame driver (`fn(t)`, local time) — never `onUpdate`, timers or rAF. `U.seed(n)` is the only randomness.
- `U.trackAt(P.track, t)` → `[x, y]` px or null; `U.follow(el, P.track)` sticks an element to the hand / face.
- `U.three({el, bloom:{strength, radius, threshold, alpha}, camera:{fov, z}})` → Promise of `{THREE, scene, camera, renderer, composer, toWorld(xPx, yPx, z), render}`
  (camera defaults: fov 35, z 10). Bloom is for glowing things (orbs, sparks, neon): its default `alpha: "luma"` makes
  dark pixels transparent. For solid 3D objects (logos, cubes) use `alpha: "keep"` or no bloom;
  `U.glowOrb(S, {radius, colors, swirl})` → `{group, update(t)}`; `U.particles(target, {count, seed, life, speed, spin, size, colors, emitter})`
  → `{update(t), points?}` (canvas: px; inside `U.three`: world units: frame height ÷ 6.3 px per unit, ≈171 at 1080 px tall, ≈305 at 1920); `U.draw(sel, {from, dur, stagger})`;
  `U.rough(svg, shapes, {seed})` (shape = `{kind: "rectangle"|"circle"|"line"|"path"…, args: [...], opts: {...}}`); `U.tex(el, latex)`; `U.anime(tl)` (an anime.js timeline, `autoplay: false`) or, with async setup, a promise resolving to
  `{ timeline: tl }` — build `tl` inside the `then`: `U.anime(U.fonts().then(() => ({ timeline: tl })))` (never resolve to the
  bare timeline: anime timelines are thenable and the build errors); `U.lottie(anim)`.
- Measuring text (`offsetWidth`, fit loops): do it after `U.fonts([500, 800, 900])` (Promise: the theme font loaded) and
  register the work with `U.ready(promise)` — the first frame waits for every promise passed to `U.ready` (`U.three` registers itself).
- `P.w`, `P.h`, `P.dur`, `P.at`, `P.end`, `P.track`, plus your own params at the top level of `P` (they cannot override these keys).
  Used as a `side` effect, `root` is the 840×960 panel (build clips it there), `P.w`/`P.h` are the panel size and
  `P.track` is in panel px. Used as `bg`/`side` `"effect"`, build fades `root` in at `P.at` and out by `P.end`; as a
  `split` effect, `root` slides in and out with the panel.
- Files the effect needs (Lottie JSON, textures, SVGs) go in the folder `out/custom/<name>/`; build copies it to the
  project and `P.assets` is its URL prefix (`fetch(P.assets + "anim.json")`, `P.assets + "tex.png"`); `save-effect` keeps the folder.
- Hand-placed `custom` effects get no automatic fade: draw nothing before `P.at` and be gone by `P.end` —
  gate everything with a visibility factor, as energy-ball does:
  `const vis = Math.min(1, Math.max(0, (t - P.at) / 0.25)) * Math.min(1, Math.max(0, (P.end - t) / 0.25));`
- Forbidden (build rejects the file, even in comments or strings): `Date.now`, `new Date`, `Math.random`,
  `crypto.getRandomValues`, `performance.now`, `requestAnimationFrame`, `setTimeout`, `setInterval`, `onUpdate`,
  `setAnimationLoop`, `THREE.Clock`, `gsap.ticker`, `.play(`, `anime.utils.random`, `d3.transition`, `AfterimagePass`,
  `GlitchEffect`, `ScrambleTextPlugin` (random inside the library: use `U.scramble`), library randomness `gsap.utils.random`,
  `utils.random`, `utils.randomPick`, `utils.shuffle` (anime.js v4 / GSAP utils), `"random` and `'random` (GSAP
  `"random(…)"` values, `from: "random"` staggers: use `U.seed`), and the callbacks that fire only when
  playback crosses a point (a render worker seeking straight to a frame skips them): `onComplete`, `onRepeat`, `onRender`,
  `onBegin`, `onLoop`, `onStart`, `onReverseComplete`, `onBeforeUpdate`, `onPause`, `onInterrupt`, `onSwapped`, `.restart(`. Create Anime.js / Lottie objects with
  `autoplay: false` and hand them to `U.anime` / `U.lottie` (the clock seeks them; never push them on `window.__hfAnime`).
  Libraries (GSAP plugins, Three.js, Anime.js, Lottie, KaTeX, Rough.js, D3) are vendored and load automatically when used.
  Three.js addons: only the vendored ones load (`three/addons/` + `environments/RoomEnvironment.js`, `geometries/TextGeometry.js`, `loaders/FontLoader.js`, `loaders/GLTFLoader.js`, `postprocessing/` `EffectComposer` / `RenderPass` / `UnrealBloomPass` / `OutputPass` / `ShaderPass` / `SavePass` / `MaskPass` / `Pass`, `shaders/` `CopyShader` / `LuminosityHighPassShader` / `OutputShader`, `utils/BufferGeometryUtils.js`); build rejects any other addon — build the shape from core `THREE` instead.

Pattern (the energy-ball effect, abridged):
```html
<style>ROOT { position: absolute; inset: 0; }</style>
<markup><div class="fx" style="position:absolute;inset:0"></div></markup>
<script>
// root = the effect's root element
U.three({ el: root.querySelector(".fx"), bloom: { strength: 1.2, radius: 0.6, threshold: 0.1 } }).then(S => {
  const orb = U.glowOrb(S, { radius: P.radius || 1, colors: P.colors, swirl: 1 });   // already in S.scene
  U.clock(t => {
    const p = U.trackAt(P.track, t);
    const vis = p ? Math.min(1, Math.max(0, (t - P.at) / 0.25)) * Math.min(1, Math.max(0, (P.end - t) / 0.25)) : 0;
    if (p) orb.group.position.copy(S.toWorld(p[0], p[1], 0));
    orb.group.scale.setScalar(Math.max(0.001, vis));
    orb.update(t); S.render();
  });
});
</script>
```

**Checkpoint "zrozumiałem tak":** map every request into `plan.json` in §5 first (a word anchor in requests.md matches a graphic starting — or with its `hit` landing — within ±1 s of that word). Then, right before build (16:9: together with the preview), when `requests.md` has ≥ 1 line, run `$CM requests <folder>/out` — it needs aligned_words.json, edl_timed.json and plan.json (one line per request: OK / MISSING /
NOTE / SURPRISE OK|MISSING / BAD, then `requests: N ok, M missing, K bad`), fix every `MISSING` and `BAD` and every `WARN density` (§5 Gęstość), then show the user the list as "zrozumiałem tak: …"
and wait for OK. No requests → no pause. Split-panel layout: the list also shows the panel compactly — the `panel:`
lines from `$CM build`, one line each (`0.00–1.40 stat-card 44%`, `… SCENE globe.png`); without requests there is no
pause and those lines go into EDIT_NOTES.md (§9).

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
 "music": {"src": "/abs/path/bed.mp3"}}
```
- `music`: only for a heygen bed (`src`, see Music below; folder music is automatic — then leave `music` out); omit `volume` to use the config `music.volume` (a `volume` here overrides it).
- Anchors: `"S2:word"` (first occurrence in segment S2), `"S2:word#2"` (second), or seconds into the video. `"S2:75"`
  also matches the spoken `75%`. Optional on any graphic: `until` (anchor or seconds), `hit`, `sfx`.
- Components: `title` (at, text, kicker?, logo?), `counter` (at, to, prefix?, suffix?, label), `list` (items[{text, at}],
  head?), `chip` (at, text, logo?/icon?), `stamp` (at, one-word text), `bars` (at, head, rows[{label, value}],
  illustrative), `point` (at, image, corner tl/tr/bl/br), `split` (from, to, media | effect + params).
- Effects on request (`custom`, `bg`, `side`, `"follow"`): §1c. A moment from the WOW pack table (§1c) gets that stock
  effect — a graphic, a panel item or a `"scenes"` entry as its plan entry says — within the WOW caps (`WARN wow …`).
- Limits enforced by the planner: a `list` has at most 4 items, `bars` at most 3 rows, `stamp` is exactly one word,
  `counter.to` is a number. Budgets (warnings): at most 2 graphics with `hit`, 1 `title`, no overlapping graphics.
- **Gęstość (density) — never a "pusty" video.** Follow the density rule of `frame.md` (9:16: a visual on screen ≥ 50 %
  of the time, bare face — captions only — never longer than 4 s outside the first 1.5 s and the CTA tail — the last segment, at most its final 6 s; 16:9: never longer than
  20 s). After the first plan run `$CM build <folder>/out` and read every `WARN density` line, then fill each named
  stretch: a `chip` / `stamp` / `counter` on its key word, number or name; b-roll (`$CM shot` of the page, a `broll/`
  file, or an image via `media-use resolve` when signed in) in a `split` (9:16) / `pip` (16:9); an explainer only when
  explainers were requested (§1c); an effect on a gesture. Many short visuals in a row, never two at once — the budgets
  below still hold. Rebuild until no `WARN density` is left; one that stays gets a one-line reason. The "zrozumiałem
  tak" list is shown only with zero density warnings, or with each remaining one explained in one line.
  Split-panel layout: the panel itself meets the density rule (panel items and scenes count as cover) — a `WARN
  density` there means a hole in the panel (`WARN panel gap`): fill it with a panel item, not a band graphic (§5b).
- B-roll: files in `<folder>/broll/`; for a web page the speaker talks about: `$CM shot "<url>" -o "<folder>/broll/<name>.png"` (if `<name>.png` already exists in `broll/`, use `<name>-2.png`, `-3` … — never overwrite)
  and READ the PNG (cookie banners, login walls → pick another page or crop).
- Music: config `music.source` = `folder` → automatic (first audio file in config `music.folder`); `heygen` → check
  sign-in with `npx --yes hyperframes@0.8.157 media-use resolve --doctor`; if not signed in, use no music and note it
  in EDIT_NOTES (never sign in for them, no extra pause); if signed in:
  `npx --yes hyperframes@0.8.157 media-use resolve --type bgm --intent "<mood>" --project <folder>/out/composition --json`;
  take the local audio file path from the JSON; check it exists, and put its ABSOLUTE path in `plan.music.src`; `none` → no music.

## 5b. Panel (split-panel layout, 9:16)

Only when the theme's `layout.mode` is `split-panel` and the video is 9:16 (Layout above). `cadence` = the layout's
`[min, max]` seconds (default [1.0, 3.0]), `max_per_min` = its `fullscreen.max_per_min` (default 3).

- **Face first:** run `$CM track "<folder>/out"` before the first build — the panel moves the face into the bottom part
  from its tracked position; without `work/tracks.json` (or a plan `"face"`) the build guesses and prints
  `WARN panel: no face position` (the face may end up too low, chin cut off).

- **`"panel"`** (top-level in plan.json, not in `graphics`): a contiguous timeline from the first word (or after a
  ≤ 1.5 s face-only hook) to the CTA. **Dense, like a reel:** one item per clause / key phrase, NOT per sentence —
  items 1–2 s by default (never under `cadence[0]`, never over `cadence[1]`), so a 20 s short gets ~12–18 items (a
  sentence → 2–3 items: the claim, the proof, the consequence). Mix stock templates with real page screenshots (`$CM
  shot`, below) — every named product / site / repo is its page, not a headline. Items in increasing `at`, each ends at
  the next item's `at` (or its own `until`), so the panel is never empty between them. Item = `{"at": <anchor>, "until"?: <anchor>, "effect": "<name>",
  "params": {…}}` or `{"at", "until"?, "media": "broll/<file>", "fit"?: "contain"|"cover"}` — exactly one of
  `effect` / `media`; `"sfx"` optional on either; no other keys (no `shot` key: screenshots are files). Never `split`, `pip`, `side` or `bg`
  graphics next to a panel (build error "the panel replaces split" — make it a panel item).
- **What goes in the panel — illustrate what is SAID, phrase by phrase** (templates and params in §1c):
  - a number → `stat-card` (`"layout": "hero"` for THE number of the video, `card` for the others) or a `checklist`
    `summary` when the number is a result of a check (e.g. 50 % links broken);
  - a product / site / tool named → its real page: `$CM shot "<url>" -o "<folder>/broll/<name>.png" --width 1000 --height 880 --light` (a new `<name>`, never over an existing file in `broll/`)
    (the panel box is 1000 × (round(1920 × ratio) − 80) px — `--height 880` at ratio 0.5, 688 at 0.40, 1072 at 0.60),
    READ the PNG (cookie banner, login wall, empty page → another URL, or crop) and use it as `"media": "broll/<name>.png"`;
    or a `ui-mock` `browser` (its URL, a typed search, result rows, one circled) / `app` (its screen, a typed filter,
    rows with toggles the cursor clicks) mockup of what is DONE in it;
  - steps / a process → `flow` or `checklist`; a check / comparison (works / broken, before / after) → `checklist`;
  - a chat / an AI answer / a command → `ui-mock` `chat` / `terminal`;
  - a mechanism / "how it works" → `iso-machine` with `"theme": "panel"`;
  - a device / system taken apart, "z czego to się składa" → `exploded-view`; countries / "na całym świecie" → `globe`
    (WOW pack, §1c: 3–4.5 s items, within the WOW caps — a panel item counts);
  - anything else → `headline` with the sentence's key phrase (1–6 words, the speaker's words).
  Vary the kinds — never the same template three items in a row. Every number in the panel (stat-card `value`,
  checklist `summary.value` and number labels, iso-machine `counter.to`) is verified against a ✅ line of
  `factcheck.md` (§3) before you write it; text comes only from what is said.
- **Scenes** (`"scenes": [{"from", "to", "media": "broll/<file>"}]` or `{"from", "to", "effect", "params"?}`): 0–`max_per_min`
  per minute, 1–6 s each, never overlapping, only on punch moments (the hook's payoff, the big reveal) — the whole frame, no speaker.
  Sources, in this order, never blocking and never sign in (never ask for a login, never suggest creating an account):
  (1) a file the user gave in `<folder>/broll/`; (2) only when `npx --yes hyperframes@0.8.157 media-use resolve --doctor`
  already says signed in: `npx --yes hyperframes@0.8.157 media-use resolve --type image --intent "<scene, in the theme's style, e.g. pixel-art globe at night, 9:16>" --project "<folder>/out/composition"`
  → copy the file to `<folder>/broll/` under a name that does not exist yet (`-2`, `-3`; never overwrite); (3) a full-frame stock explainer as the scene (`stat-card` `"layout": "hero"`
  or `headline`), which takes the theme's tokens; (4) no scene. Log the source used per scene in EDIT_NOTES.md.
  A moment from the WOW pack table (§1c) takes its WOW scene before these sources — `kinetic-word` on THE number or
  the launch word, `topic-change` on "przejdźmy do" — within the WOW caps (a scene counts).
- **Band graphics** (title / counter / stamp / chip …) ≤ 2, only on punch moments — each hides the panel item under it
  for its span. The `captions` / `hit` / `sfx` rules stay as in §5.
- **Example:**
```json
{"panel": [
   {"at": "S1:Claude", "effect": "headline", "params": {"text": "Claude sprawdza linki", "mode": "type"}},
   {"at": "S1:połowa", "effect": "checklist", "params": {"title": "Link check", "rows": [
     {"text": "docs.example.com", "status": "ok", "label": "200 OK"}, {"text": "blog.example.com", "status": "bad", "label": "404"}],
     "strike": true, "summary": {"value": 50, "suffix": "%", "label": "nie działa"}}},
   {"at": "S2:Firecrawl", "media": "broll/firecrawl.png", "fit": "cover"},
   {"at": "S2:włączasz", "effect": "ui-mock", "params": {"kind": "app", "title": "Connectors", "search": "fire",
     "rows": [{"text": "Firecrawl", "toggle": true, "click": true}]}}],
 "scenes": [{"from": "S3:cały", "to": "S3:internet.", "media": "broll/globe.png"}],
 "graphics": [{"type": "stamp", "at": "S4:koniec", "text": "STOP.", "hit": true}]}
```
- **After `$CM build`:** it prints `layout: split-panel` and one `panel: <a>–<b> <what>` line per item. READ them
  against the transcript (each sentence covered, nothing stale) and fix every WARN: `panel gap` (an item's `until`
  ends before the next item's `at` → extend or drop that `until`, add an item in the gap, or cover it with a scene), `panel item #n … is X s` (shorter than min(0.6 s, `cadence[0]`) → merge; longer than `cadence[1]` + 1.5 s → split it), `panel pace: N items in X s` (one per sentence — split the items per clause / key phrase up to the range it names), `scenes:`
  / `longer than 6 s` (drop or shorten scenes), an unconfirmed number. `layout: classic` with a split-panel theme → wrong
  `--theme` or a 16:9 video.
- **Snapshots:** add the middle of EVERY panel item (`(a + b) / 2` from its `panel:` line) and of every scene to the
  §6 snapshot checkpoints (the middle is enough for stock panel items; a new `out/custom/` effect used as a panel item
  keeps start + middle as §6 says) and READ them: the item in the theme's colours / fonts, whole inside the panel, the page
  screenshot readable, the face in the bottom half, captions on the seam not covering the item's text or the mouth (under a WOW scene: captions in the bottom band, the scene's text above them).

## 6. Build and look

`$CM build <folder>/out` — fix every `cutmate:` error (it names the bad anchor and lists the segment's words) and think
about every `WARN`. The last line prints `checkpoints: t1,t2,...`. Then, from the project dir (no path argument):
`( cd <folder>/out/composition && rm -rf ../snapshots && npx --yes hyperframes@0.8.157 snapshot --at <checkpoints> --no-end --describe false -o ../snapshots )`
(skip the snapshot when build printed no checkpoints; for every custom effect add at least two checkpoints, start and middle (stock explainers as panel items: the middle, §5b), and READ those frames — effects are new code) and READ every frame: overlaps, text wrapping, safe zones, captions readable, split panel shows the media. Fix
`plan.json` and rebuild until clean.

## 7. Render and QA

`$CM render <folder>/out` (check → render → finalize; writes `out/final.mp4`). 9:16 takes ~1–2 min. 16:9 takes ~45–60 min per 15 min of video. Prefer running it in the background (Bash `run_in_background: true`) for both formats, follow `out/work/render.log`, and tell the user the ETA. `WARN hyperframes check ran out of time` = a busy machine, not an error (it goes on). READ every `check_*.png` it
writes and describe each in one line. If `steps.qa`: `$CM qa <folder>/out` and handle every hit: probe/rms, fix the
EDL (then cut → align → track (if used) → build → render; graphics move with their words automatically) or explain why it's fine.

## 8. Thumbnail (if `steps.thumbnail`)

Pick a frame with a strong expression from a sheet of `out/final.mp4` (`$CM sheet <folder>/out/final.mp4 -o <folder>/out/sheets/final.png`);
`--at` is seconds into `final.mp4`. Title = the PROMISE of the short (not the product name), hook = the short's hook
question. Keep the title short (it wraps to at most 3 lines) and the hook to 2 lines:
`$CM thumb <folder>/out --at <t> --title "SAME KONKRETY" --hook "Czy Caveman dalej działa?"`
(writes `out/thumbnail.png` and `.jpg`). READ the PNG; redo with another frame if the face is covered.

## 9. Notes and hand-off

Write `out/EDIT_NOTES.md`: final structure (segments in order with times), which graphic is where and why, music,
commands used. Split-panel layout: also the `panel:` lines from the last `$CM build` (one per item and scene) and the
source of every scene (user file / media-use image / stock explainer / none). Send the user `final.mp4` (and the thumbnail).
16:9: also hand over `chapters.txt` and, if it was written, `captions.srt`.
When they reply with timestamps, log each as `[uwagi <mm:ss>]` in `requests.md` (§1c) and batch all changes into
one rebuild + one render.
