# Themes

A theme decides how your videos look: caption style, fonts, colours, the shape and motion of every graphic, sound effects, and the layout. cutmate ships one neutral theme, `clean`. You can make as many of your own as you like.

## Ways to get a theme

| Way | Skill | What you get |
|---|---|---|
| Clean | none | The neutral starter look: Inter, white captions with a soft shadow, white rounded cards, one sky-blue accent (`#7dd3fc`) |
| 🎲 "Zaskocz mnie" (surprise me) | `/cutmate:theme` | A random bold look: palette, font pair, shapes, motion, captions. You can re-roll it until you like it. |
| Your own colours and fonts | `/cutmate:theme` | You pick the accent, the card colour, the fonts, shapes, motion and layout |
| Clone a style | `/cutmate:clone-style` | A theme that looks like a reel, a video, screenshots or a folder you like |
| Switch the active theme | `/cutmate:theme` | Makes a saved theme the default |

`/cutmate:setup` also asks how your videos should look, and runs one of these for you.

## Where themes live

| Kind | Location | Notes |
|---|---|---|
| Bundled | `<plugin>/themes/clean/` | Never edited |
| Yours (saved) | `~/.cutmate/themes/<name>/` | Used by your videos |
| Drafts | `~/.cutmate/themes/.drafts/<name>/` | Work in progress. Your videos never change until you save. |
| Backups | `~/.cutmate/themes/.backup/<name>-<timestamp>/` | The old version, when you overwrite a saved theme |

```bash
cutmate theme list
```

prints one tab-separated line per theme: `marker  name  kind  checked  path`. The marker `*` is the current default, kind is `bundled`, `user` or `draft`, and checked is `checked`, `unchecked` or `-`.

## Using a theme

- **As the default:** `cutmate theme use <name>`, or `cutmate config set theme=<name>`.
- **For one video:** name it when you start the edit ("use the neon-pill theme"). Claude passes `--theme <name>` to `build`, `preview` and `thumb`.

## 🎲 "Zaskocz mnie": the random roll

`cutmate theme new --mode random` rolls a direction from:

| Ingredient | Options |
|---|---|
| Palette | 12 palettes (6 light-card, 6 dark-card), accents spread around the colour wheel: paper-red, bubblegum, arctic, mint, sand, violet, noir, lime, ocean, magenta, coral, periwinkle |
| Font pair (display / text) | Anton / Inter, Oswald / Lato, Archivo Black / Archivo, Space Grotesk / Manrope, Syne / Rubik, Unbounded / Manrope, Bricolage Grotesque / DM Sans, DM Serif Display / DM Sans, Playfair Display / Source Sans 3, Fraunces / Work Sans, Space Mono / Space Grotesk, Caveat / Lato, Titan One / Rubik, Bangers / Manrope |
| Shapes | `sharp`, `pill`, `outline`, `brutal`, `tape` |
| Motion | `snappy`, `smooth`, `glitch`, `typewriter`, `slam` |
| Captions | `shadow`, `boxed`, `outline`, `highlight` |

Claude then restyles the draft (fonts, tokens, captions, and every look component: title, counter, list, chip, stamp, bars, lower-third, chapter, point), renders it, and shows you a contact sheet. Pick **Losuj jeszcze raz** (roll again) to get another one. `--avoid <draft>` keeps a new roll away from earlier ones, and `--seed N` makes a roll repeatable.

The roll never picks a layout. A random theme stays classic unless you ask for the panel.

## Your own colours and fonts

`/cutmate:theme` → **Własne kolory i fonty** (your own colours and fonts) asks for:

1. **Accent** (red, yellow, lime, violet, or any name / hex) and **cards** (dark, light, or a colour).
2. **Fonts**: matched to the style, loud (Anton, Archivo Black), elegant serif (DM Serif Display, Fraunces), technical (Space Grotesk, Space Mono), or any Google font you name.
3. **Shapes, motion and layout**: classic, or **panel on top** (see [Layouts](#layouts)).
4. **A name** (letters, digits, `_`, `-`).

Claude derives the rest of the palette and checks contrast.

## Cloning a style

`/cutmate:clone-style <source>` takes:

- a **link** to a reel or video. With your yes, it downloads one public video with `yt-dlp`, only to analyse the style. It never uses cookies or logins. You install `yt-dlp` yourself (`pipx install yt-dlp`, `winget install yt-dlp`, `brew install yt-dlp`).
- a **local video**, **screenshots**, or a **folder** of them.

Claude reads contact sheets of the source (at most 2 videos and 4 sheets), close-ups of graphic entrances (motion), and full-size stills. It runs `cutmate theme colors` to get exact hex values, then tells you what it sees: palette, fonts, shapes, captions, motion, density and layout. After your OK it builds the theme and compares it **side by side** with the source (one composite image per comparison) for up to 3 rounds.

**What is never copied:** logos, watermarks, handles, the source's text, its images and its artwork. Fonts come only from OFL Google Fonts. The theme *looks like* the source, but it is your own work. Work files go to `~/.cutmate/clone/<name>/`, which you can delete afterwards.

### Layout capture

A clone captures the **layout** as well as the look. If a panel stays on screen in most frames of the source, the clone becomes a `split-panel` theme, using the panel's position and share of the frame, how often its content changes, where the captions sit, how many full-screen scenes appear per minute, and the panel colour.

## Layouts

| Layout | Format | What it looks like |
|---|---|---|
| `classic` (default) | 9:16 and 16:9 | Graphics come and go over the face. Explainers appear in a split panel only when you ask for them. |
| `split-panel` | 9:16 only (a 16:9 video ignores it) | The top part of the frame is **one persistent panel** for the whole video, showing explainers, app / browser mockups, status tables, big numbers and page screenshots, changing every 1–3 s. You sit in the bottom part, and captions sit on the seam. Occasional full-screen scenes. |

A split-panel theme declares its layout in `theme.json`:

```json
"layout": {"mode": "split-panel", "ratio": 0.5, "cadence": [1.0, 3.0], "captions": "seam", "transition": "cut", "fullscreen": {"max_per_min": 3}}
```

| Key | Values | Default |
|---|---|---|
| `mode` | `classic`, `split-panel` | `classic` |
| `panel` | `top` | `top` |
| `ratio` | Share of the frame height for the panel, 0.40–0.60 | 0.5 |
| `cadence` | `[min, max]` seconds per panel item, 0.5 ≤ min < max ≤ 6 | `[1.0, 3.0]` |
| `captions` | `seam`, `bottom` | `seam` |
| `transition` | `cut`, `fade` | `cut` |
| `fullscreen.max_per_min` | Full-screen scenes per minute, 0–6 | 3 |

A split-panel theme also needs `--panel-bg` in `tokens.css` (the lint checks for it). With this layout, explainers are on without a request: Claude plans one panel item per clause.

## Anatomy of a theme folder

```text
<name>/
├── theme.json        # name, accent, fonts, sfx per component, hit sfx, direction, optional layout
├── tokens.css        # colour / shape tokens + @font-face blocks (written by `cutmate theme font`)
├── theme.css         # caption styles (.cw, .cw.key, .cw.num) and safe zones
├── frame.md          # the rules Claude reads before writing plan.json (zones, budget, density, components)
├── fonts/            # TTF files + their OFL licence text
├── components/       # title, counter, list, chip, stamp, bars, point, split, pip, lower-third, chapter,
│                     # bg, side, panel, panel-media, scene (.html)
│   └── custom/       # effects: explainers, WOW pack, VFX + index.json
└── check/            # contact.png, sheet-9x16.png, sheet-16x9.png (written by `cutmate theme check`)
```

### Tokens

Every component, explainer and WOW effect reads the theme **only through CSS custom properties**, so changing tokens restyles everything at once.

| Token | Role | Required |
|---|---|---|
| `--accent` | Key words, numbers, highlights, the panel seam edge | Yes |
| `--on-accent` | Text on accent fills (contrast ≥ 4.5 with `--accent`) | Recommended |
| `--text` | Caption colour | Yes |
| `--ink` | Text on cards (contrast ≥ 4.5 with `--card`) | Yes |
| `--card` | Card / graphic background | Yes |
| `--muted` | Labels on cards | Yes |
| `--shadow` | Card shadow (hard offset for brutal, `none` for sharp, soft blur for pill) | Yes |
| `--radius` | Corner radius of cards and panel items | Recommended |
| `--panel-bg` | The split-panel colour | Yes for split-panel |
| `--font`, `--font-display` | Text font, display font | Yes |
| `--font-num` | Digit font, when the display font's digits read as letters | Optional |
| `--spark`, `--spark-glow` | Spark colours for `hand-control` | Optional |
| `--glitch-a`, `--glitch-b` | RGB ghost colours for `topic-change` | Optional |

`theme.json` → `accent` must equal `--accent` exactly.

The clean theme's tokens:

```css
:root {
  --accent: #7dd3fc;
  --text: #ffffff;
  --ink: #0f172a;
  --muted: #475569;
  --card: rgba(255, 255, 255, 0.94);
  --panel-bg: #0b0b0f;
  --radius: 28px;
  --shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}
```

### Fonts (OFL only)

Fonts are added only with `cutmate theme font`. It downloads the static weights (400–900) of a **Google Fonts family under the SIL Open Font License**, saves its `OFL-<family>.txt` licence next to the TTFs, checks that the family has Polish letters (ą ę ł ń ó ś ź ż), and rewrites the `cutmate:font` blocks in `tokens.css`.

```bash
cutmate theme font my-theme "Anton" --role display
cutmate theme font my-theme "Manrope" --role text
cutmate theme font my-theme "VT323" --role num      # digits only, when the display 5 looks like an S
cutmate theme digits my-theme                        # renders "-75% 0123456789" next to look-alike letters
```

A family that is not OFL or not on Google Fonts is refused. Fonts go into a **draft**, never straight into a saved theme. Clean ships Inter (OFL 1.1, `themes/clean/fonts/OFL-inter.txt`).

### Sound effects

`theme.json` → `sfx` maps each component to cues from the bundled set (`whoosh`, `pop`, `click`, `impact`, `swell`, `ping`, all CC0 from Kenney.nl). In `plan.json` you can mute one graphic with `"sfx": false`, or swap its cue with `"sfx": "impact"`.

## The check gate

A theme is saved only after it passes `cutmate theme check`:

```bash
cutmate theme check my-theme                       # lint + render every component in 9:16 and 16:9
cutmate theme check my-theme --clip take1.mp4      # use your own footage instead of the test pattern
cutmate theme save my-theme                        # move the checked draft into ~/.cutmate/themes/
cutmate theme save my-theme --force                # overwrite a saved theme (the old one goes to .backup)
cutmate theme use my-theme
```

The check lints the theme (required tokens, contrast, layout, and that random / clone themes are not just clean in new colours), renders every component in both formats, and writes `check/contact.png` (for the bundled `clean`: `~/.cutmate/checks/clean/contact.png`). That contact sheet has three rows: entrances (the motion), settled 9:16 graphics, and 16:9 corner graphics. A draft changed after its last check must be checked again before `save`.

## Next

- Effects that take your theme's tokens: [effects.md](effects.md)
- Building a theme by hand and saving effects into it: [customizing.md](customizing.md)
