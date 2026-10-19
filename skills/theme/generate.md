# Generate a theme from a direction

Shared by `/cutmate:theme` and `/cutmate:clone-style`. Input: a draft `<name>` (made by `$CM theme new`, a copy of
clean in `${CUTMATE_HOME:-$HOME/.cutmate}/themes/.drafts/<name>/`) and its `direction` in `theme.json`: `palette`
(accent, text, ink, card, muted, on_accent), `fonts` (display, text), `shapes`, `motion`, `captions`, maybe `hints`.

The goal is a look people remember — bold, "wow", never polite or empty. Strong shapes, real motion, big confident
type; a theme that is clean with new colours is a failure (lint rejects it). Bold never beats the rules: safe zones,
readable text, every component still works with every parameter.

Work only inside the draft folder. Never touch the bundled themes or saved themes.

## 1. Fonts

`$CM theme font <name> "<display>" --role display`, then `$CM theme font <name> "<text>" --role text` (the family names
from `direction.fonts`). Each prints the family and the downloaded weight files — use only those weights.
A refusal (no Polish letters, not OFL, not on Google Fonts) → pick another family of the same character (condensed
grotesk → condensed grotesk, serif → serif), tell the user in one line, and update `direction.fonts`.
Never edit the `cutmate:font` blocks in `tokens.css` by hand — only `$CM theme font` writes them. Inter as the display
font fails lint for random / clone themes.

## 2. tokens.css

Put the palette into the colour tokens below the `cutmate:font` blocks: `--accent`, `--text`, `--ink`, `--card`,
`--muted`, `--shadow` (fits the shapes: a hard offset `8px 8px 0 var(--ink)` for brutal, `none` for sharp, a soft blur
for pill). Add `--on-accent: <on_accent>;` for text on accent fills. Keep every required token (`--accent`, `--text`,
`--ink`, `--muted`, `--card`, `--shadow`, `--font`, `--font-display`).
Contrast (lint): `--ink` on `--card` ≥ 4.5; `on_accent` on `--accent` ≥ 4.5.
`theme.json` `accent` = the `--accent` value, exactly.

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
there). Use `var(--font-display)` for the title, the stamp and the counter number; `var(--font)` for the rest.

**Shapes** (`direction.shapes`, see `hints`): sharp = radius 0, flat fills, no shadows · pill = 999px radii, soft
shadow · outline = transparent cards, 4–6px accent borders · brutal = thick ink border + hard offset shadow
8px 8px 0 · tape = rotated label strips (−2…3°). Go further than the minimum: accent bars, stacked strips, cut corners,
inline SVG marks (inline SVG namespaces are fine).

**Motion** (`direction.motion`): snappy = expo.out 0.18–0.25 s, short slides · smooth = sine.inOut 0.5–0.7 s, fade +
scale 0.96→1 · glitch = steps(4) + seeded x / clip jitter · typewriter = per-character stagger 0.03 s · slam = scale
3→1, power4.in, rotation settle. The entrance must read in one frame of the contact sheet — clearly not clean's pop.

**Keep in every component:** its `P` params (table below), `<markup>` placeholders (`{{name}}` …), class names other
components or the build use, and an exit before `P.end` — `U.out(el, P.end - 0.2)` or an explicit
`tl.to(…, {…, immediateRender: false}, …)` that ends by `P.end`. Animate only on `tl` (the paused timeline).

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
  `THREE.Clock`, `new Date`, `crypto.getRandomValues`, `gsap.ticker`, `.play(`.
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

## 6. Check

`$CM theme check <name> --clip <recording>` — `--clip` when a recording of the user is known (the clip setup's
selftest used, or a clip from a folder they edited); without it the busy test pattern is the background.
It takes minutes: Bash timeout 600000 or run_in_background: true; never two checks at once (they flake on render
deadlines). Lint error → fix what it names → re-run. Output: `check/contact.png`, `check/sheet-9x16.png`,
`check/sheet-16x9.png` in the draft.

## 7. Quality bar

READ `contact.png` and both sheets. Fix and re-check until all of this holds:
- Every text whole and inside its zone. 9:16: graphics y 230–720, captions y 1250–1500, nothing in the top 192 px or
  below y 1536. 16:9: graphics x 1340–1860 y 60–420, captions y 880–1000, lower-third bottom-left.
- "Tytuł ąę" and "Drugi rozdział ąę" render in the theme font (no fallback glyphs for ą ę).
- Readable over the busy test pattern — cards, shadow, outline or box behind every text.
- "-75%" and all 4 list items visible; bars proportional.
- The entrance row shows the motion (random: clearly not clean's pop).
- Random / clone: title, stamp and chip differ from clean in font, shape and motion — not just colour.
