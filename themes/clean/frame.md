---
name: clean
description: Neutral starter theme — Inter, white captions with a soft shadow, white rounded cards, one accent colour.
unit: 1080×1920 (9:16), 30 fps
---

# clean — rules for writing plan.json

- **The face is the hero.** Graphics live in the band y 230–720; captions in y 1250–1500. Nothing in the top 192 px or below y 1536.
- **Accent (`--accent`, default #7dd3fc) marks key words and numbers only.** Put product / person / key-term words in `captions.key`.
- **Budget:** at most 2 graphics with `"hit": true` (the punchline and the key number), at most 1 `title`, never two graphics at once.
- **Pick components by what is said:**
  - `title` — a name reveal (product, model, person) or the topic in the first seconds.
  - `counter` — THE number of the short (percent, price, count). Only numbers confirmed by the fact-check.
  - `list` — a spoken list; each item on its own word.
  - `chip` — a small label for a name / tool / brand mention (with `logo` when there is one).
  - `stamp` — one-word punchline („NIE.”, „STOP.”). Pair with `"hit": true` when it is the punchline.
  - `bars` — a comparison. Mark `"illustrative": true` unless the values were spoken and fact-checked.
  - `point` — the speaker points at something: a card with a screenshot near the finger (`corner`).
  - `split` — tutorial / "look at this" beats: b-roll panel on top, face slides down. Use a page screenshot (`cutmate shot`) or a file from `broll/`.
- **Rhythm:** something should change every 3–6 s (cut punch-ins already help). Do not let a graphic wait empty for more than 1.5 s.
- **SFX** come automatically per component; set `"sfx": false` to mute one, or a name (`whoosh`, `pop`, `click`, `impact`, `swell`, `ping`) to replace it.
