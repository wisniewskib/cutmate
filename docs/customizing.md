# Customizing cutmate

cutmate is built to be extended without forking it. There are three layers you can make your own:

1. **Your own skill** on top of cutmate: your house rules, applied to every edit.
2. **Your own themes**: the look.
3. **Saved effects**: effects Claude wrote for one video, reused in every later one.

## 1. Your own skill on top of `/cutmate:edit`

A Claude Code skill is a folder with a `SKILL.md` file. Put a personal skill in your user skills folder:

| OS | Path |
|---|---|
| Linux / macOS | `~/.claude/skills/<name>/SKILL.md` |
| Windows | `%USERPROFILE%\.claude\skills\<name>\SKILL.md` |

The pattern: your skill **sets the rules first** (theme, language, what to always or never do, your CTA, your naming), then **runs the `cutmate:edit` skill** on the folder. cutmate does the editing, and your rules decide the choices it leaves open to Claude.

### Full example: a weekly tech short

Save this as `~/.claude/skills/tech-short/SKILL.md`:

```markdown
---
name: tech-short
description: Edit my weekly AI-tools short with cutmate using my house rules — neon-pill theme, English, a fixed CTA, no surprises, a stat card for every number. Use when I say "tech short", "weekly short" or "/tech-short <folder>".
---

# /tech-short <folder>

My house rules for every weekly short. Apply them, then edit with cutmate.

## 0. CLI

Set the cutmate CLI once (works on Linux, macOS and Windows Git Bash):
`CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`
If it does not run, tell me to run /cutmate:setup and stop.

## 1. Settings for this video

- Check `"$CM" config show`. If `language` is not `en`, run `"$CM" config set language=en`.
- Theme: always `neon-pill` (pass it to cutmate:edit as "use the neon-pill theme"). If `"$CM" theme list`
  has no `neon-pill`, say so and use the config theme.
- Captions: burned for 9:16 (the config default). Never change other config keys.

## 2. House rules (tell cutmate:edit all of them up front)

- Transcription prompt names: Claude Code, Anthropic, GitHub, MCP, plus every product named in the folder name.
- **No surprises** ("bez niespodzianek"): only the effects I ask for and the stock components.
- Explainers: yes. Every spoken number gets a `stat-card`, and every named product gets its real page via
  `"$CM" shot "<url>" -o "<folder>/broll/<name>.png" --light`.
- WOW effects: at most one per short, `kinetic-word` on THE number of the video. Never `burst-out`.
- Hook: the strongest line first, at most 3 s. End on my CTA line ("Comment TOOLS and I'll send you the list.").
  If no take says the CTA, tell me before cutting — do not invent it.
- Thumbnail: the title is the promise of the video in at most 4 words, all caps; the hook is the question I ask.
- Never keep a take where I look at my notes.

## 3. Edit

Run the `cutmate:edit` skill with `<folder>` and all of section 2 as the request. Follow every cutmate checkpoint
as usual (fact-check stops, "zrozumiałem tak").

## 4. After the render

- Copy `<folder>/out/final.mp4` to `<folder>/<folder name>-final.mp4` (never overwrite a source clip).
- Write `<folder>/out/POST.md`: a title (≤ 60 chars), a 2-line description and 5 hashtags, from the transcript only.
- Tell me the path of the video, the thumbnail and POST.md in three lines.
```

Then, in Claude Code:

```text
/tech-short ~/Videos/2026-10-24-mcp-servers
```

**Why this works:**

- cutmate's skills read your requests the same way, whether they come from chat or from another skill. Everything in section 2 lands in `requests.md` and the "zrozumiałem tak" checkpoint, so you can still see and strike it.
- Your rules only narrow choices that cutmate leaves to Claude: which effects, how many, the hook, the theme. cutmate's own guarantees still apply, including fact-checking, never touching source clips, the WOW caps and the density rules.
- The CLI line is the same one cutmate's skills use, so it works on all three OSes.

### Tips for your own skill

- **Use config keys for durable settings** (`cutmate config set …`) and the skill text for per-video rules.
- **Prefer cutmate's own words** for its features: "explainers", "bez niespodzianek" (no surprises), WOW effect names, component names (`stat-card`, `stamp`, `chip`). These are the terms its skill maps.
- **Do not reimplement steps.** Let `cutmate:edit` transcribe, pick takes and render. Add steps before (folder checks, names) or after (copying, posting notes).
- **Keep commands portable**: quote paths, use `"$CM"`, and avoid Linux-only tools in steps that must also work on Windows Git Bash.

## 2. Your own themes

The easiest way is `/cutmate:theme` or `/cutmate:clone-style` (see [themes.md](themes.md)). To build or tweak one by hand, work on a **draft** and let the check gate approve it:

```bash
cutmate theme new my-look --from clean --mode custom       # draft in ~/.cutmate/themes/.drafts/my-look/
cutmate theme font my-look "Space Grotesk" --role display
cutmate theme font my-look "Manrope" --role text
# edit tokens.css (colours, --radius, --shadow), theme.css (captions), components/*.html, theme.json (sfx), frame.md
cutmate theme check my-look --clip ~/Videos/take1.mp4      # lint + render both formats → check/contact.png
cutmate theme save my-look
cutmate theme use my-look
```

What to change, from the safest to the most involved:

| Change | Where | Notes |
|---|---|---|
| Colours, corners, shadows | `tokens.css` | Restyles every component, explainer and WOW effect at once. Keep the required tokens and the contrast (≥ 4.5). |
| Fonts | `cutmate theme font` | OFL Google Fonts with Polish letters only; never edit the `cutmate:font` blocks by hand |
| Caption style | `theme.css` → `.cw`, `.cw.key`, `.cw.num` | Keep `opacity: 0` on `.cw` and the safe-zone rules |
| Sound per component | `theme.json` → `sfx` | Cue names: `whoosh`, `pop`, `click`, `impact`, `swell`, `ping` |
| Component look | `components/<type>.html` | Keep the structure and parameters of clean's version: the edit skill relies on the component contract |
| Rules Claude follows | `frame.md` | Zones, budgets, density and components; keep the rule sections |
| Layout | `theme.json` → `layout` | `split-panel` needs `--panel-bg` (see [themes.md](themes.md#layouts)) |

Leave the stock explainers and WOW effects (`components/custom/*`) alone: they take your look through tokens only.

**Sharing a theme:** a theme is a plain folder. Copy `~/.cutmate/themes/<name>/` to someone else's `~/.cutmate/themes/`, then run `cutmate theme check <name> --saved` once before using it. Only share fonts that are OFL (their `OFL-*.txt` files are in `fonts/`).

## 3. Saved effects

When Claude writes an effect for one video (`out/custom/<name>.html`) and you like it, save it into your theme:

```bash
cutmate save-effect ~/Videos/short/out space-bg --description "starfield behind the speaker"
cutmate save-effect ~/Videos/short/out space-bg --theme my-look --force
```

| What happens | Where |
|---|---|
| The effect is linted (the [determinism rules](effects.md#determinism-rules)) | |
| The HTML and its asset folder are copied | `~/.cutmate/themes/<theme>/components/custom/<name>.html` and `<name>/` |
| An entry is written with your description, the params it was used with and its `follow` mode | `~/.cutmate/themes/<theme>/components/custom/index.json` |

In later edits, Claude reads both the bundled `index.json` and yours before writing anything new. Asking for "the space background again" reuses your effect. You can also write an effect yourself in `<folder>/out/custom/<name>.html` and use it in a plan as `{"type": "custom", "name": "<name>", …}`. The API and rules are in [effects.md](effects.md#custom-effects-written-by-claude).

> `--theme` defaults to the config theme. Effects are always saved under `~/.cutmate/themes/<theme>/components/custom/`, even for the bundled `clean`, and cutmate looks there before the plugin's own effects. The plugin folder itself is never modified. Lookup order for an effect name: `out/custom/`, then your theme folder, then the plugin's theme, then the stock effects in `clean`.
