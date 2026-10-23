# Generate a theme from a direction

Shared by `/cutmate:theme` and `/cutmate:clone-style`. Input: a draft `<name>` (made by `$CM theme new`, a copy of
clean in `${CUTMATE_HOME:-$HOME/.cutmate}/themes/.drafts/<name>/`) and its `direction` in `theme.json`: `palette`
(accent, text, ink, card, muted, on_accent), `fonts` (display, text), `shapes`, `motion`, `captions`, maybe `hints`.

The goal is a look people remember — bold, "wow", never polite or empty. Strong shapes, real motion, big confident
type; a theme that is clean with new colours is a failure.
The lint gate (looks like clean) applies to random and clone themes; custom themes must meet the same bar by eye. Bold never beats the rules: safe zones,
readable text, every component still works with every parameter.

Work only inside the draft folder. Never touch the bundled themes or saved themes.

## 1. Fonts

`$CM theme font <name> "<display>" --role display`, then `$CM theme font <name> "<text>" --role text` (the family names
from `direction.fonts`). Each prints the family and the downloaded weight files. Fonts have only their available
weights: set an explicit `font-weight` to a weight that exists (e.g. Anton 400) instead of 800 / 900, or the browser
fakes a bold.
A refusal (no Polish letters, not OFL, not on Google Fonts) → pick another family of the same character (condensed
grotesk → condensed grotesk, serif → serif), tell the user in one line, and update `direction.fonts`.
Never edit the `cutmate:font` blocks in `tokens.css` by hand — only `$CM theme font` writes them. Inter as the display
font fails lint for random / clone themes.

**Digits.** Numbers (stat-card, checklist summary, counter) use `var(--font-num, var(--font-display))`. Run
`$CM theme digits <name>` and READ the PNG it prints: "-75% 0123456789" next to look-alike letters (5 S, 0 O, 1 l I,
2 Z, 8 B). When a digit in the display font reads as a letter (pixel and decorative fonts: Pixelify Sans's 5 is an S)
pick a digit font of the same character with clear digits — pixel → Press Start 2P / VT323, condensed → Oswald,
rounded → Nunito — `$CM theme font <name> "<family>" --role num` (digits only: no Polish letters needed), add it to
`direction.fonts.num`, run `$CM theme digits <name>` again and READ it. Clear digits in the display font → no num font.

## 2. tokens.css

Put the palette into the colour tokens below the `cutmate:font` blocks: `--accent`, `--text`, `--ink`, `--card`,
`--muted`, `--shadow` (fits the shapes: a hard offset `8px 8px 0 var(--ink)` for brutal, `none` for sharp, a soft blur
for pill). Add `--on-accent: <on_accent>;` for text on accent fills. Keep every required token (`--accent`, `--text`,
`--ink`, `--muted`, `--card`, `--shadow`, `--font`, `--font-display`).
The stock WOW effects (`exploded-view`, `globe`, `burst-out`, `hand-control`, `topic-change`, `kinetic-word`) take the theme only through tokens (`--accent`, `--on-accent`, `--text`, `--ink`, `--muted`, `--card`, `--panel-bg`, `--radius`, `--shadow`, `--font`, `--font-display`, `--font-num`; optional `--spark` / `--spark-glow` for hand-control's sparks, `--glitch-a` / `--glitch-b` for topic-change's RGB ghosts) — keep the tokens complete and never restyle those files.
Contrast (lint): `--ink` on `--card` ≥ 4.5; `on_accent` on `--accent` ≥ 4.5.
`theme.json` `accent` = the `--accent` value, exactly.

## 2b. Layout

Read the top-level `layout` in the draft's `theme.json` (missing = classic).
- **classic** (no `layout`, or `"mode": "classic"`) → nothing changes; skip to step 3.
- **split-panel** → the persistent panel is built from `components/panel.html` (the frame), `panel-media.html` (a page
  screenshot / video inside the panel) and `scene.html` (a full-frame scene). Keep their structure — the markup, the
  `{{panel_h}}` / `{{media_tag}}` placeholders, class names, the `P.open_at_zero` / `P.stays` / `P.at` / `P.end` / `P.fade` timing
  and the `fit-contain` / `fit-cover` classes; restyle them ONLY through tokens and their `<style>`:
  - `tokens.css`: `--panel-bg` (the panel colour; lint requires it for split-panel), `--radius` (corners of panel
    items: 0 for sharp, 999px is too round for a panel — use 28–48px for pill), `--shadow`; `--accent` is the seam edge
    (`.panel-edge`, 6–8 px; restyle it in `panel.html`'s `<style>`: a solid strip, a dashed / pixel strip, a double
    line — whatever the direction's shapes say).
  - The stock explainers (`stat-card`, `checklist`, `ui-mock`, `flow`, `iso-machine`, `headline`) read the same tokens
    (`--panel-bg`, `--card`, `--ink`, `--muted`, `--accent`, `--on-accent`, `--font`, `--font-display`, `--radius`,
    `--shadow`), so a light panel with a pixel font shows up in every panel item without touching them.
  - Captions sit ON the seam (`captions: "seam"`, y = ratio × 1920): set the 9:16 caption size for a seam in step 3 —
    small pills read better on a seam than big words (`.cw` 44–60px, a box / pill behind each word or page, 2–4 words
    per page), so they never cover the panel item's content or the speaker's mouth.
- §5 adds the `## Layout: split-panel` section to `frame.md` (text below).

## 3. theme.css — captions only

Restyle only `.cw`, `.cw.key`, `.cw.num` (and their `html.f169 .cw…` size rules) per `direction.captions`:
- `shadow` — white words, soft drop shadow (clean's way; make the weight / case / size your own).
- `boxed` — each word on an accent box, `color: var(--on-accent)`; key / number words inverted (card box, accent text).
- `outline` — `-webkit-text-stroke` in ink or black, no box, `paint-order: stroke fill`.
- `highlight` — plain words with a strong shadow; key / number words in an accent pill with `var(--on-accent)` text.
Use `var(--font)` (or `var(--font-display)` for a loud look). Keep `opacity: 0` on `.cw` (the captions animate it) and
keep every other rule verbatim — `#captions`, `.cap-page`, `.band` and their `html.f169` positions are the safe zones.

## 4. Look components

Files: `components/<type>.html` in the draft; clean's originals are the reference for what each must keep. Rewrite
title, counter, list, chip, stamp, bars, lower-third, chapter and point. At least 5 of the 6 LOOK components (title,
counter, list, chip, stamp, bars) must be substantially rewritten — similarity to clean < 0.85 after comments and
whitespace are stripped; tweaking a radius and a colour does not pass. Structural components (split, pip, bg, side)
stay as they are; the token colours restyle them.

**Style:** `<style>` rules are scoped `ROOT …`. 16:9 overrides only as `html.f169 ROOT …` (the build rewrites exactly
that form; any other f169 form is dead inside a component). Every component needs 16:9 sizes (graphics are small
there). Use `var(--font-display)` for the title and the stamp, `var(--font-num, var(--font-display))` for the counter number;
`var(--font)` for the rest.

**Shapes** (`direction.shapes`, see `hints`): sharp = radius 0, flat fills, no shadows · pill = 999px radii, soft
shadow · outline = transparent cards, 4–6px accent borders · brutal = thick ink border + hard offset shadow
8px 8px 0 · tape = rotated label strips (−2…3°). Go further than the minimum: accent bars, stacked strips, cut corners,
inline SVG marks (inline SVG namespaces are fine).

**Motion** (`direction.motion`): snappy = expo.out 0.18–0.25 s, short slides · smooth = sine.inOut 0.5–0.7 s, fade +
scale 0.96→1 · glitch = steps(4) + seeded x / clip jitter · typewriter = per-character stagger 0.03 s · slam = scale
3→1, power4.in, rotation settle. The entrance must read in one frame of the contact sheet — clearly not clean's pop.

**Rule — change the structure, not only the property values:** stacked or rotated lines, oversized numerals, cut corners, a
different card layout (label above vs. beside the number, a split two-colour block, a strip instead of a card).

**Recipes** — 1–2 worked examples per direction value, applied to title / counter / stamp:
- sharp — title: display text on a full-width flat accent slab, kicker as a black bar above it, radius 0, no shadow.
  counter: number on a flat card with a thick accent rule under it; label set small beside the number.
- pill — chip/title: 999px pills with a soft shadow; title split into two stacked pills (kicker pill small, text pill
  big). stamp: one giant pill, text in `var(--on-accent)` on accent.
- outline — title: transparent box with a 6px accent border and display text with `-webkit-text-stroke`; counter:
  oversized outlined numerals, label in a solid accent tag sitting on the border.
- brutal — title = accent block + `border: 6px solid var(--ink)` + hard offset shadow `8px 8px 0 var(--ink)` +
  uppercase display font. counter: card with the same border/shadow, number overflowing the card top. stamp: ink block,
  accent text, rotated −3°.
- tape — stamp = a rotated strip (−2…3°) with notched ends (`clip-path: polygon(…)` zig-zag or triangular notches);
  title: two strips of tape at different angles, kicker on the smaller one. list items as separate taped strips.
- snappy — expo.out 0.18–0.25 s slides of 40–80 px, items staggered 0.06 s; title words slide in from alternating sides.
- smooth — sine.inOut 0.5–0.7 s fade + scale 0.96→1, the card first, its text 0.1 s later; counter counts over 0.9 s.
- glitch — steps(4) entrance: 3–4 `tl.set` frames of x offsets and `clip-path: inset(…)` slices from
  `const rnd = U.seed(n)`, then the clean frame; a second jitter burst on the stamp at P.at + 0.4.
- typewriter — title / stamp split into per-character spans (after the font load), stagger 0.03 s, a blinking caret
  block made with a few `tl.set` opacity steps (no loops).
- slam — counter = digits scale 3→1 with power4.in and an overshoot (scale 0.94 → 1 settle) plus rotation −8° → 0;
  stamp: scale 3→1 with a 0.05 s shake of the band; title lands word by word.

**Keep in every component:** its `P` params (table below), `<markup>` placeholders (`{{name}}` …), class names other
components or the build use, and an exit before `P.end` — `U.out(el, P.end - 0.2)` or an explicit
`tl.to(…, {…, immediateRender: false}, …)` that ends by `P.end`. Animate only on `tl` (the paused timeline).
Also keep:
- point — the corner table (`POS` / `ORIGIN` objects and their use on the card) and the
  `html.f169 ROOT .point { … top: 60px !important; right: 60px !important; left: auto !important; }` override (16:9
  moves every corner to the top-right box).
- lower-third and chapter — their `position: absolute` placement (lower-third bottom-left at left 80px / top 820px,
  chapter `inset: 0`) and their `<markup>` with the `{{name}}` / `{{role}}` and `{{label}}` / `{{title}}` placeholders.
- chip — the `place` / `safe` positioning code (gesture placement inside the safe zone).

| component | params |
|---|---|
| title | text, kicker?, logo? |
| counter | to, prefix?, suffix?, label, lang (keep clean's number formatting and `U.counter`) |
| list | head?, items[{text, at}] (each item enters at its own `at`) |
| chip | text, logo? / icon?, place?, safe? (keep the `place` / `safe` positioning code) |
| stamp | text |
| bars | head, rows[{label, value}], note (bar lengths proportional to value) |
| point | image, corner |
| lower-third | name, role? |
| chapter | label, title |

**Script rules:**
- FORBIDDEN (lint): `Date.now`, `Math.random`, `performance.now`, `requestAnimationFrame`, `setTimeout`,
  `setInterval`, `onUpdate`, `setAnimationLoop`, `anime.utils.random`, `d3.transition`, `AfterimagePass`,
  `THREE.Clock`, `new Date`, `crypto.getRandomValues`, `gsap.ticker`, `.play(`, `GlitchEffect`, `ScrambleTextPlugin`,
  library randomness `gsap.utils.random`, `utils.random`, `utils.randomPick`, `utils.shuffle`, `"random`, `'random`
  (anime.js v4 / GSAP utils, `"random(…)"` values, `from: "random"` staggers),
  and the crossing callbacks `onComplete`, `onRepeat`, `onRender`, `onBegin`, `onLoop`, `onStart`, `onReverseComplete`,
  `onBeforeUpdate`, `onPause`, `onInterrupt`, `onSwapped`, `.restart(` (a render worker seeking straight to a frame skips them).
- Randomness only `U.seed(n)`: `const rnd = U.seed(7); … rnd()` (fixed n, e.g. `direction.seed`).
- No fetchable `http(s)` refs anywhere (themes work offline; lint rejects them).
- Measure text (`offsetWidth`, fitting, per-character splits that need widths) only after
  `document.fonts.load("<weight> 10px " + getComputedStyle(el).fontFamily)` resolves, registered in
  `window.__hf.buildReady[root.id]` — chip's `place` code is the pattern.
- Helpers: `U.el(tag, cls, text, parent)`, `U.counter(el, fmt)`, `U.out(target, t)`, `U.seed(n)`.

## 5. theme.json sfx and frame.md

- `sfx`: you may swap names to fit the motion (e.g. slam → `impact` on title / stamp; glitch → `click`; smooth →
  `swell`), only among `whoosh`, `pop`, `click`, `impact`, `swell`, `ping`. Keep the keys and the timing format.
- `frame.md`: frontmatter `name` (the draft name) and `description` describe the new look in one line; the accent line
  in the rules gives the new `--accent` hex. Every rule section stays verbatim (zones, budget, components, 16:9).
- split-panel layout only: append this section to `frame.md` verbatim (put the layout's `cadence[1]` and
  `fullscreen.max_per_min` values — defaults 3.0 and 3 — in place of `<cadence max>` and `<max per min>`):

```markdown
## Layout: split-panel

- **The panel is always open** (9:16): the top part of the frame is one panel for the whole video; the speaker sits
  in the bottom part. 16:9 ignores the layout (classic rules above).
- **One panel item per clause / key phrase, NOT per sentence** — 1–2 s each (never over <cadence max> s), ~12–18
  per 20 s, in plan.json `"panel"` (explainer effect or a `media` page screenshot from `broll/`), contiguous from
  the first word (or after a ≤ 1.5 s face-only hook) to the CTA — the panel is never empty. No `split`, `pip`,
  `side` or `bg` graphics: the panel replaces split.
- **Band graphics ≤ 2** (title / counter / stamp / chip) — only on punch moments; they hide the panel item under them.
- **Scenes ≤ <max per min> per minute** in `"scenes"` (full-frame image or explainer, 1–6 s) on punch moments.
- **Captions on the seam** between panel and face — small pills, never over the mouth.
- Every number in the panel is confirmed by a ✅ line of factcheck.md.
```

## 6. Check

`$CM theme check <name> --clip <recording>` — `--clip` when a recording of the user is known (the clip setup's
selftest used, or a clip from a folder they edited); without it the busy test pattern is the background.
It takes minutes: prefer Bash run_in_background: true (else Bash timeout 600000); never two checks at once (they flake on render
deadlines). Lint error → fix what it names → re-run. Output: `check/contact.png`, `check/sheet-9x16.png`,
`check/sheet-16x9.png` in the draft.

## 7. Quality bar

Once per session run `$CM theme check clean` (minutes, same timeout rule) and READ
`${CUTMATE_HOME:-$HOME/.cutmate}/checks/clean/contact.png` side by side with the new `contact.png`; if a LOOK tile
could pass for clean's, rewrite it.

READ `contact.png` and both sheets. Fix and re-check until all of this holds:
- Every text whole and inside its zone. 9:16: graphics y 230–720, captions y 1250–1500, nothing in the top 192 px or
  below y 1536. 16:9: graphics x 1340–1860 y 60–420, captions y 880–1000, lower-third bottom-left.
- "Tytuł ąę" and "Drugi rozdział ąę" render in the theme font (no fallback glyphs for ą ę).
- Readable over the busy test pattern — cards, shadow, outline or box behind every text.
- "-75%" reads as a number (no 5 that looks like an S — see **Digits** in §1) and all 4 list items visible; bars
  proportional.
- The entrance row shows the motion (random: clearly not clean's pop).
- Random / clone: title, stamp and chip differ from clean in font, shape and motion — not just colour.
- split-panel: READ `check/sheet-9x16.png` (and the panel-item snapshots) — every panel item in the theme's colours
  and fonts (the `--panel-bg` fill, not clean's dark panel), the face in the bottom half, the captions on the seam
  not covering the mouth, the scene full-frame.
