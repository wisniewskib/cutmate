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
- **Pick components by what is said:**
  - `title` — a name reveal (product, model, person) or the topic in the first seconds.
  - `counter` — THE number of the short (percent, price, count). Only numbers confirmed by the fact-check.
  - `list` — a spoken list; each item on its own word.
  - `chip` — a small label for a name / tool / brand mention (with `logo` when there is one).
  - `stamp` — one-word punchline („NIE.”, „STOP.”). Pair with `"hit": true` when it is the punchline.
  - `bars` — a comparison. Mark `"illustrative": true` unless the values were spoken and fact-checked.
  - `point` — the speaker points at something: a card with a screenshot near the finger (`corner`; the bottom corners sit at y 340–712, still inside the graphics band).
  - `split` — tutorial / "look at this" beats: b-roll panel on top, face slides down. Use a page screenshot (`cutmate shot`) or a file from `broll/`.
- **Rhythm:** something should change every 3–6 s (cut punch-ins already help). Do not let a graphic wait empty for more than 1.5 s.
- **SFX** come automatically per component; set `"sfx": false` to mute one, or a name (`whoosh`, `pop`, `click`, `impact`, `swell`, `ping`) to replace it.

## 16:9 (long-form, 1920×1080)

- **The speaker owns the frame.** Graphics are small and live in the top-right corner (x 1340–1860, y 60–420).
  Burned captions (only when the config says `burn`/`both`) sit at y 880–1000. Lower-third: bottom-left x 80–900, y 820–980.
- **`split` does not exist in 16:9 — use `pip`:** the b-roll fills the screen and the speaker's face sits in a circle in a
  bottom corner (`corner` `br` default / `bl`). Use it for "look at this page / tool / recording" beats, `fit: cover` for
  page screenshots.
- **`lower-third`** once, when the speaker introduces themselves (`name`, `role?`), ~4 s.
- **Chapters** (`plan.chapters`): one per topic change; plates appear for chapters 2+ (1.5 s full-screen, the voice
  continues). Don't start other graphics during a plate. YouTube wants ≥ 3 chapters, each ≥ 10 s, the first at 00:00.
- **`face`**: for every segment write where the face is (fractions of the frame, read from the contact sheet) — punch-ins
  (1.25×) and the pip circle centre on it.
- **Rhythm** is calmer than a short: something should change every 10–20 s (cuts, a graphic, a pip); no hits on chapter plates.
