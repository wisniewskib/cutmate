---
name: clean
description: Neutral starter theme — Inter, white captions with a soft shadow, white rounded cards, one accent colour.
unit: 1080×1920 (9:16), 30 fps
---

# clean — rules for writing plan.json

- **The face is the hero.** Graphics live in the band y 230–720; captions in y 1250–1500. Nothing in the top 192 px or below y 1536.
- **Accent (`--accent`, default #7dd3fc) marks key words and numbers only.** Put product / person / key-term words in `captions.key`.
- **Key words match inflected forms** (key CAVEMAN also marks "Cavemana", "Cavemanem"; key CLAUDE marks "Claude’a"), but anchors (`"S2:word"`) must still use the transcript's exact word (case- and punctuation-insensitive).
- **Budget:** at most 2 graphics with `"hit": true` (the punchline and the key number), at most 1 `title`, never two graphics at once.
- **Density — never an empty short.** A visual layer (any graphic, b-roll / `split`, an explainer, an effect, a `chip` /
  `stamp` on a key word) is on screen **≥ 50 %** of the video time. Bare face (captions only) never lasts longer than
  **4 s**, except the first hook second and the CTA (the last segment). Every key word, number and name gets a `chip`,
  `stamp`, `counter` or b-roll. Reach it with many short visuals one after another (1.5–3 s each, a gap of ≥ 0.3 s), not
  by stacking — the budget above still holds. `cutmate build` prints `WARN density` for every stretch that breaks this.
- **Pick components by what is said:**
  - `title` — a name reveal (product, model, person) or the topic in the first seconds.
  - `counter` — THE number of the short (percent, price, count). Only numbers confirmed by the fact-check.
  - `list` — a spoken list; each item on its own word.
  - `chip` — a small label for a name / tool / brand mention (with `logo` when there is one).
  - `stamp` — one-word punchline („NIE.”, „STOP.”). Pair with `"hit": true` when it is the punchline.
  - `bars` — a comparison. Mark `"illustrative": true` unless the values were spoken and fact-checked.
  - `point` — the speaker points at something: a card with a screenshot near the finger (`corner`; the bottom corners sit at y 340–712, still inside the graphics band).
  - `split` — tutorial / "look at this" beats: b-roll panel on top, face slides down. Use a page screenshot (`cutmate shot`) or a file from `broll/`.
- **Rhythm:** a new visual every 2–4 s (cuts and punch-ins alone are not enough — they are still bare face). Do not let a graphic wait empty for more than 1.5 s.
- **SFX** come automatically per component; set `"sfx": false` to mute one, or a name (`whoosh`, `pop`, `click`, `impact`, `swell`, `ping`) to replace it.

## 16:9 (long-form, 1920×1080)

- **The speaker owns the frame.** Graphics are small and live in the top-right corner (x 1340–1860, y 60–420).
  Burned captions (only when the config says `burn`/`both`) sit at y 880–1000. Lower-third: bottom-left x 80–900, y 820–980.
  Burned captions share that bottom band with the lower-third and the pip circle — avoid long burned captions under them / prefer `srt`.
- **`split` does not exist in 16:9 — use `pip`:** the b-roll fills the screen and the speaker's face sits in a circle in a
  bottom corner (`corner` `br` default / `bl`). Use it for "look at this page / tool / recording" beats, `fit: cover` for
  page screenshots.
- **`lower-third`** once, when the speaker introduces themselves (`name`, `role?`), ~4 s.
- **Chapters** (`plan.chapters`): one per topic change; plates appear for chapters 2+ (1.5 s full-screen, the voice
  continues). Don't start other graphics during a plate. YouTube wants ≥ 3 chapters, each ≥ 10 s, the first at 00:00.
- **`face`**: for every segment write where the face is (fractions of the frame, read from the contact sheet) — punch-ins
  (1.25×) and the pip circle centre on it.
- **Rhythm** is calmer than a short, but bare face never lasts longer than **20 s** (`WARN density`): a `pip` / b-roll on
  every concrete thing named (a page, a tool, a product, a result), corner graphics for names and numbers; no hits on chapter plates.

## Effects on request

- **Built-in first.** Use a component above when it says the thing; write a `custom` effect only for what none of them
  can show (an object on the hand, a drawn diagram, a formula). Custom effects live in `out/custom/<name>.html`, then
  the user theme, then the bundled `components/custom/`.
- **`follow`** (`face`, `hand`, `hand_left`, `hand_right`) needs `out/work/tracks.json` — run `cutmate track` first.
- **`bg`** replaces the background behind the speaker (`media` or `effect`). Keep all `bg` ranges ≤ 30 s in total —
  background removal is slow on CPU (~17 min per minute of video).
- **`side`** exists only in 16:9: a half-screen panel (`media` or `effect`) with the speaker shifted to the other half
  (`speaker` `right` default / `left`). In 9:16 use `split`.
- **Stock `energy-ball`** — a Rasengan-style orb (swirling core, spiral bands, wind rings, spiralling sparks; flash in, implodes out), ≈ P.h × 0.037 px above the tracked hand point (40 px at 1080 p):
  `{"type": "custom", "name": "energy-ball", "from": …, "to": …, "follow": "hand",
  "params": {"radius": 0.45, "colors": ["#e0f7ff", "#38bdf8"]}}` (`radius` in 3D units, ~170 px each at 1080 p;
  `colors` = core, rim). Without hand samples (no tracks, or the hand out of view) it stays hidden; only without `follow` does it sit at `place` / `x`,`y` / the centre.
- **Gestures:** every moment the speaker shows with the hands where something goes gets a visible effect on the hands (`"place": "gesture"`): open palm → the effect rests on it and follows it; index point → the pointed spot near the fingertip. Stock `burst` (flash, shockwaves, sparks, ~1 s), `hand-sparks` (`stream` / `sparks`, `link` arc between the hands), `showcase-3d` on a palm. Big enough for a phone, never over the face.
