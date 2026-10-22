---
name: theme
description: Create, pick or preview a cutmate theme — own colours and fonts, 🎲 zaskocz mnie (a random bold look), a contact sheet of every component, then save it and make it the default. Use when the user runs /cutmate:theme or wants a different look for their videos.
---

# /cutmate:theme

Rules:
- Talk to the user in their language (config `language`). Replies short: the action first, a few lines.
- Ask EVERY question with **AskUserQuestion** (≤ 4 options per question, the recommended option first and marked
  "(polecane)"), never as an A/B/C text list. The labels below are Polish; translate them to the user's language, keep
  the mapping.
- Set the CLI once per session (setup venv first, so a dev `cutmate` on PATH never shadows it):
  `CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`;
  if it doesn't run, tell the user to run `/cutmate:setup` and stop.
- Long-running: `$CM theme check` renders every component in both formats (minutes) → prefer Bash
  run_in_background: true (else Bash timeout 600000); never two checks at once. `WARN hyperframes check ran out of time` = a busy machine, not an error (it goes on).
- New themes are drafts in `${CUTMATE_HOME:-$HOME/.cutmate}/themes/.drafts/<name>/` until `$CM theme save`; the
  user's videos never change before that.
- Any failing command: one line with the cause + the fix.

## 1. Menu

AskUserQuestion "Co robimy z wyglądem?":
- **🎲 Zaskocz mnie (polecane)** → §2
- **Własne kolory i fonty** → §3
- **Sklonuj styl** (z filmu / screenów, które lubisz) → run the `cutmate:clone-style` skill and stop here
- **Zmień aktywny theme** → §5

## 2. 🎲 Zaskocz mnie

1. `$CM theme new --mode random` → it prints JSON: `name` (the draft), `path`, `direction` (palette with accent, text,
   ink, card, muted, on_accent; fonts display/text; shapes; motion; captions; `hints` explaining each).
2. Tell the user in 1–2 lines what was rolled (e.g. "noir + Anton, brutal shapes, slam motion — robię…").
3. Follow `${CLAUDE_PLUGIN_ROOT}/skills/theme/generate.md` with this draft and its direction. Then §4.

The roll never picks a layout (a layout is a format choice, not a look): the draft stays classic (no `layout` key).
Only when the user asked for the panel ("panel u góry", "explainery cały czas", "jak w tej rolce z panelem") write
`"layout": {"mode": "split-panel"}` into the draft's `theme.json` and `--panel-bg` into its `tokens.css` before
`generate.md` (its step 2b).

Keep the list of every draft made in this session (for `--avoid`).

## 3. Własne kolory i fonty

1. Colours — AskUserQuestion with two questions:
   - "Kolor akcentu?" — Czerwony `#c1121f` / Żółty `#ffd400` / Limonka `#8dff3a` / Fiolet `#6d28d9`; mark
     "(polecane)" on the one closest to what the user described (put it first); any other answer (a name or hex) →
     turn it into hex.
   - "Karty i tło grafik?" — Ciemne (polecane) / Jasne / Podam kolor (name or hex → hex).
   Derive the rest of the palette: `text` (caption colour, usually `#ffffff`), `ink` (text on cards, contrast ≥ 4.5 on
   `card`), `muted` (labels on cards), `on_accent` (text on accent fills, contrast ≥ 4.5 on `accent`; usually
   `#000000` or `#ffffff`). The lint checks contrast — fix and re-run when `$CM theme check` names a ratio.
2. Fonts — AskUserQuestion "Fonty?": Dobierz do stylu (polecane) / Gruby, krzykliwy (Anton, Archivo Black) /
   Elegancki szeryf (DM Serif Display, Fraunces) / Techniczny (Space Grotesk, Space Mono). Any other answer: a Google
   font name or a description → pick the closest OFL Google family that has Polish letters (ą ę ł ń ó ś ź ż). Pick a
   display family (titles, stamps, numbers) and a text family (captions, labels). Not Inter for display. When the
   display font's digits read as letters (pixel / decorative: a 5 like an S), also a digit font — generate.md §1 Digits.
3. Shapes, motion and layout — ONE AskUserQuestion with three questions (the names are the direction values; AskUserQuestion
   takes 4 options, the fifth name is reachable through the free-text answer; put first and mark "(polecane)" the
   option that fits what the user described, else brutal and slam):
   - "Kształty?" — brutal (gruba ramka + twardy cień) / pill (pastylki, miękki cień) / tape (krzywo naklejone paski) /
     outline (przezroczyste karty, gruba ramka) — fifth: sharp (ostre, płaskie).
   - "Ruch?" — slam (wbija się z dużej skali) / glitch (szarpnięcia) / snappy (szybkie wjazdy) / typewriter (litera po
     literze) — fifth: smooth (płynne).
   - "Układ?" — **Klasyczny (polecane)** (grafiki pojawiają się na chwilę nad twarzą) / **Panel u góry (explainery
     cały czas)** (górna połowa to stały panel z explainerami, mockupami i screenami, zmiana co 1–3 s; ty w dolnej
     połowie, napisy na szwie). Mark "(polecane)" on Panel u góry instead when the user described that look.
   Pick `captions` yourself to fit (`boxed` for brutal/sharp, `highlight` for pill/tape, `outline` or `shadow`
   otherwise) and say it in the summary.
4. Name — AskUserQuestion with a suggested name (`<colour>-<shapes>`, letters, digits, `_`, `-`) and free text.
   `$CM theme new <name> --mode custom` — it replaces an existing draft of that name (after an earlier Anuluj pick a
   fresh name, or say the old draft is dropped). It prints `WARN theme <name> exists` when a saved theme has that name → ask
   now (§4 overwrite question); "Nowa nazwa" → run `$CM theme new` again with the new name.
5. Write the direction into the draft's `theme.json` → `"direction": {"mode": "custom", "palette": {name, accent,
   on_accent, text, ink, card, muted}, "fonts": {"display": …, "text": …}, "shapes": …, "motion": …, "captions": …}`.
   **Panel u góry** → also the top-level `"layout": {"mode": "split-panel"}` (defaults: panel top, ratio 0.5, cadence
   [1.0, 3.0], captions on the seam, cut transition, ≤ 3 full-screen scenes per minute) and `--panel-bg: <hex>;` in the
   draft's `tokens.css` colour block (the panel colour: the card colour from "Karty i tło grafik?" or a shade of it;
   lint requires it). **Klasyczny** → no `layout` key.
6. Follow `${CLAUDE_PLUGIN_ROOT}/skills/theme/generate.md`. Then §4.

## 4. Decision

After `generate.md` passed its quality bar: READ `check/contact.png` of the draft and send the user its path, with 2–3
lines on what to look at — top row: entrances (the motion), middle row: settled 9:16 graphics (shapes, fonts,
readability), bottom row: 16:9 corner graphics. Mention anything you could not make perfect.

AskUserQuestion "Jak ci się podoba?":
- **Biorę (polecane)**
- **Losuj jeszcze raz** (only after 🎲; for custom and clone: **Popraw coś** → ask what, change it in the
  `generate.md` step it belongs to, re-run steps 6–7, back here)
- **Anuluj** → the draft stays in `.drafts` (nothing else changes); stop.

**Losuj jeszcze raz:** `$CM theme new --mode random --avoid <current draft>` plus one `--avoid <draft>` per earlier
draft of this session (one theme per flag, e.g. `$CM theme new --mode random --avoid noir-brutal --avoid ocean-tape`)
→ `generate.md` again → this section again.

**Biorę:** `$CM theme save <name>`.
- "already exists" → AskUserQuestion "Nadpisać theme <name>? (stara wersja zostaje w kopii)": Nadpisz / Nowa nazwa.
  - Nadpisz → `$CM theme save <name> --force` (only on this answer; the old one goes to `themes/.backup`).
  - Nowa nazwa → ask the name, `$CM theme new <new> --from <name> --mode custom`, copy the whole `direction` object
    from the old draft's `theme.json` into the new one, `$CM theme check <new>` (same `--clip` as before), then
    `$CM theme save <new>`.
- "changed since its last check" → `$CM theme check <name>` again, then save.

Then AskUserQuestion "Ustawić jako domyślny?": Tak (polecane) / Nie → Tak: `$CM theme use <name>`. One line: the next
`/cutmate:edit` uses it (or `--theme <name>` for one video).

## 5. Zmień aktywny theme

`$CM theme list` → one tab-separated line per theme: `marker\tname\tkind\tchecked\tpath` (marker `*` = current
default, `-` = not; kind bundled / user / draft; checked `checked` / `unchecked` / `-`). Always split on tabs: name = 2nd column, path = 5th
(paths may contain spaces on Windows).
AskUserQuestion with the bundled and saved themes — current theme first (≤ 4; more themes → the free-text answer
takes a name). A draft → offer to finish it instead: `generate.md` steps 6–7, then §4.
- `unchecked` → `$CM theme check <name>` first. Lint errors → one line each; fix them in a draft copy
  (`$CM theme new <name>-2 --from <name> --mode custom`, then `generate.md`) or pick another theme.
- `$CM theme use <name>` → one line confirming.
