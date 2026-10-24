# Effects

Beyond captions and the basic components, cutmate has three tiers of animated effects:

1. **Explainers**: animated explanations of what is said (a number, steps, a tool, a mechanism).
2. **The WOW pack**: six tested show-stoppers for the key moments of a video.
3. **Custom effects**: written by Claude when you ask for something nothing else covers, and saved into your theme when you like them.

All of them take your theme's tokens (colours, fonts, radius, shadow), so a cloned style restyles them too. They are seek-safe and deterministic (see [the rules](#determinism-rules)), and they render offline from vendored libraries.

Effects are defined in `themes/clean/components/custom/` (one `.html` file each), and `index.json` describes their parameters. Claude reads `index.json` before using an effect.

## When effects are used

| Theme layout | Explainers | WOW effects | Custom effects |
|---|---|---|---|
| Classic (9:16 or 16:9) | Only when you ask ("add explainers", "explain this with an animation") | When you ask for effects, or when surprises are on | On request |
| Split-panel (9:16) | Always: they fill the panel, one item per clause | `exploded-view` / `globe` as panel items, `kinetic-word` / `topic-change` as scenes, `hand-control` over the speaker's half | On request |

In a classic theme, Claude picks 2–4 explainers per 60 s, each at least 2 s long, with at least 2 s of plain face between them.

## Built-in components (for reference)

These are the basic graphics in every theme (`plan.json` → `graphics`):

| Component | Use | Main fields |
|---|---|---|
| `title` | A name reveal or the topic (at most 1) | `at`, `text`, `kicker?`, `logo?` |
| `counter` | THE number of the video, counting up | `at`, `to`, `prefix?`, `suffix?`, `label` |
| `list` | A spoken list (≤ 4 items) | `items[{text, at}]`, `head?` |
| `chip` | A small label for a name / tool | `at`, `text`, `logo?` / `icon?` |
| `stamp` | A one-word punchline | `at`, `text` |
| `bars` | A comparison (≤ 3 rows) | `at`, `head`, `rows[{label, value}]`, `illustrative` |
| `point` | A card near the finger when you point | `at`, `image`, `corner` |
| `split` | 9:16: b-roll panel on top, face below | `from`, `to`, `media` or `effect` + `params` |
| `pip` | 16:9: b-roll full-screen, face in a circle | `from`, `to`, `media`, `corner?`, `fit?` |
| `lower-third` | 16:9: name and role once at the self-introduction | `at`, `name`, `role?` |
| `side` | 16:9: speaker on one half, graphic on the other | `from`, `to`, `media` or `effect`, `speaker` |
| `bg` | Replaces the background behind the speaker | `from`, `to`, `media` or `effect` |
| `custom` | Any effect by name | `name`, `from`/`to` or `at`/`until`, `params`, `follow?`, `place?` |

Any graphic can also take `until`, `hit` (a hit sound and shake) and `sfx`. Anchors are `"S2:word"`, `"S2:word#2"` or seconds.

## Explainers

| Effect | Picked for | Key params |
|---|---|---|
| `stat-card` | A number | `value` (counts up), `prefix?`, `suffix?`, `label`, `note?`, `media?` (darkened screenshot behind), `accent?`, `layout` `card` \| `hero` |
| `flow` | Steps / a process | `nodes` (2–6), `edges?`, `style` `clean` \| `rough` (hand-drawn), `seed?`, `title?`, `accent?` |
| `ui-mock` | A tool, a chat, a command, a page | `kind` `chat` \| `terminal` \| `post` \| `browser` \| `app`; `lines` (chat / terminal / post); `url`, `search?`, `rows`, `highlight?` (browser); `title`, `search?`, `rows` with `toggle?` / `click?` (app); `replies?` / `reposts?` / `likes?` (post: real counts only) |
| `iso-machine` | A mechanism, "how it works" | `parts` (2–5, shapes `box`, `cylinder`, `funnel`, `screen`, `gear`), `token?` `cube` \| `sphere`, `counter?` `{to, label}`, `title?`, `theme` `light` \| `dark` \| `panel` |
| `checklist` | A check / comparison | `rows` (2–8, status `ok`, `bad`, `warn`, `info`, `label?`), `strike?`, `summary?` `{value, suffix?, label?}`, `title?` |
| `headline` | A key phrase with no number, product or steps | `text` (1–6 words), `kicker?`, `mode` `type` \| `pop` |

In a classic 9:16 video an explainer goes in a `split` (a 1000×820 panel); in 16:9 it goes in a `side`:

```json
{"type": "split", "from": "S3:Claude", "to": "S3:linki.", "effect": "stat-card",
 "params": {"value": 50, "suffix": "%", "label": "links broken"}}
```

**Text and numbers come only from what is said.** A number in an explainer must be confirmed by a ✅ line in `factcheck.md`. The build warns only about `stat-card` `value` and `checklist` `summary.value`; Claude checks the rest itself.

### 3D and VFX

| Effect | What it does | Key params |
|---|---|---|
| `showcase-3d` | A hero 3D object flies in beside the speaker, turns, flies out | `shape` `torus-knot` \| `icosahedron` \| `text` \| `glb`, `text?`, `model?`, `color?`, `size?`, `x?`, `y?` |
| `burst` | A one-shot energy impact (~1–1.4 s): flash, shockwave rings, sparks | `colors?`, `size?` (1.2–1.6 for a hero moment), `x?`, `y?` |
| `hand-sparks` | Energy pouring out of the hands | `mode` `stream` \| `sparks`, `link?` (an arc between the hands), `colors?`, `size?` |
| `energy-ball` | A swirling energy orb on the hand that follows it | `radius?`, `colors?`, `x?`, `y?` |

All four support `"place": "gesture"`. `energy-ball` and `hand-sparks` follow the hand.

## The WOW pack

Six stock show-stoppers (`"kind": "wow"` in `index.json`). Whenever one of them fits a moment, it replaces writing a new effect.

| Effect | Moment | Modes | Length |
|---|---|---|---|
| `exploded-view` | "Let's take it apart", "what's inside", layers, a device or system explained | panel, scene, side, overlay | 3–4.5 s |
| `globe` | "Worldwide", countries, cities, a global number | panel, scene, side | 3–5 s |
| `burst-out` | The hero reveal: "this changes everything", "meet …", the product name said with emphasis | bg (classic only) | 3–5 s |
| `hand-control` | An open palm toward the camera, a "conjuring" gesture | overlay | 3–6 s |
| `topic-change` | A chapter change, "now…", "moving on to", "second thing" | overlay, scene, chapter | 1.2–2.0 s |
| `kinetic-word` | THE word or number of the video: a launch, "+300%", "FREE" | scene, overlay | 2.5–6 s (3–4 reads best) |

### `exploded-view`

A 3D product-render exploded view. The assembled object turns in, its parts slide apart with numbered leader-line labels, it orbits, then slams back together with a click flash.

| Param | Values |
|---|---|
| `parts` | 2–7 items `{"label", "shape", "color"?}` from bottom to top. Shapes: `block`, `cylinder`, `disc`, `ring`, `gear`, `board`, `screen`, `shell` |
| `preset` | When `parts` is missing: `engine` (default), `phone`, `layers`; labels in the video language |
| `axis` | `y` (vertical stack, default) or `x` (horizontal) |
| `title` | Optional heading |
| `bg` | `panel` (the theme's `--panel-bg`, default) or `none` (transparent over the video) |

### `globe`

A light 3D dotted globe. It spins to the origin country, accent arcs shoot out to each destination and land with pulsing pins, and country labels decode at the end.

| Param | Values |
|---|---|
| `from` | Origin, ISO-2 code (for example `"PL"`) |
| `to` | 1–6 destination ISO-2 codes |
| `labels` | `auto` (country names in the video language) or a list of names |
| `style` | `dots` (default) or `solid` |
| `title` | Optional heading |

Country data comes from Natural Earth (public domain), built into `globe/land.json` and `globe/countries.json`.

### `burst-out`

A 3D object bursts from behind the speaker's head with god rays, arcs over them and flies at the camera. On the impact word the canvas jumps in front with an RGB-split pulse, sparks, a shockwave and a frame shake. The object then holds beside the speaker (never over the face, above the captions) and spins out.

```json
{"type": "bg", "from": "S4:to", "to": "S4:wszystko.", "effect": "burst-out", "hit": "S4:Claude",
 "params": {"shape": "gem", "label": "Claude Code"}}
```

| Param | Values |
|---|---|
| `shape` | `gem` (default), `cube`, `knot`, `sphere`, `logo` (`media` image on a rounded extruded card) |
| `color` | Optional (default `--accent`) |
| `rays` | God rays (default `true`) |
| `label` | Optional title that decodes under the object after the impact |
| `media` | The logo image for `shape: "logo"` |

Anchor `hit` on the impact word, start at least 1 s before it, and end at least 1.5 s after it. `burst-out` needs the face position (from tracking or plan `face`). It is a `bg` effect: it cuts the speaker out (HyperFrames `remove-background`), which costs about 17× its duration on a CPU. Classic layouts only, once per short.

### `hand-control`

Hand magic on your real hand. Warm streak sparks stream from each extended fingertip, and while your palm is open toward the camera a themed card unfolds above your fingertips, follows the hand, and folds back into it when the palm closes.

```json
{"type": "custom", "name": "hand-control", "from": "S5:patrzcie", "to": 21.5,
 "params": {"card": {"title": "Gesture control", "lines": ["Sparks from every finger", "Card on an open palm"]}}}
```

| Param | Values |
|---|---|
| `card` | `{"title", "lines" (≤ 3), "media"?}`: the point being made |
| `sparks` | `tips` (default) or `off` |
| `hand` | `auto` (the raised open palm, default), `left`, `right`: the **speaker's own** hand, so with an unmirrored camera `right` is on the screen's left |
| `colors` | Optional `[core, body, glow]` (default `--spark` / `--spark-glow` or warm amber) |
| `media` | Optional card image |

It needs fingertip tracks, so run `cutmate track --force <out>` once when the build asks for it. It works in 9:16 classic, in 9:16 split-panel (in the speaker's half) and in 16:9. It is never a panel item or a scene.

### `topic-change`

The A-roll itself glitches for 0.6 s (RGB split, or a wave), slice bars and scanlines come up, the title decodes out of an RGB-split triple, and the kicker types in. It ends with a hard cut and a 2-frame white flash.

| Param | Values |
|---|---|
| `title` | The next topic, ≤ 40 characters |
| `kicker` | Optional small label (chapter plates: `ROZDZIAŁ 02`) |
| `style` | `glitch` (default) or `wave` |

For long-form videos, `"chapter_fx": "topic-change"` at the top of `plan.json` turns every chapter plate from chapter 2 on into this effect. Chapter plates do not count toward the WOW caps.

### `kinetic-word`

A full-screen anime.js punch. About 600 themed shapes pop in as a grid, ripple out, burst, and fly into the letterforms of your word. It lands with a camera punch, a ring, an underline and a starburst, breathes while it holds, then shatters out.

| Param | Values |
|---|---|
| `text` | ≤ 14 characters from the sentence (`"+300%"`, `"FREE"`) |
| `kicker` | Optional label above the word |
| `count` | Number of shapes, 300–900 (default 600) |
| `shapes` | `mixed` (default), `squares`, `dots`, `dashes` |
| `bg` | `panel` (default, full frame) or `none` (over the video) |

The word lands 1.0 s after `from`. Start the effect about 1 s before the spoken word, or anchor `"hit": "S3:word"` (custom only, at least 0.6 s after `from`).

### WOW caps

| Video | Limit |
|---|---|
| Short (cut video ≤ 90 s) | ≤ 2 WOW effects, ≥ 12 s apart start to start; `burst-out` and `kinetic-word` once each |
| Long-form | ≤ 1 per minute, ≤ 8 in total; chapter plates (`chapter_fx`) not counted |

Panel items and scenes count toward the caps. There is never one WOW effect right after another without plain footage between them, and never one over the face. The build prints `WARN wow …` when a cap is broken, and Claude fixes it before the checkpoint.

## Custom effects written by Claude

When you ask for something nothing above covers ("put a space background behind me", "a Rasengan in my hand"), Claude writes a new effect in `out/custom/<name>.html`. It starts from the closest template, checks it against the build's lint, and reads snapshots of it every 0.25 s before showing you the checkpoint.

An effect file has three sections, like a theme component:

```html
<style>ROOT { position: absolute; inset: 0; }</style>
<markup><div class="fx" style="position:absolute;inset:0"></div></markup>
<script>
U.three({ el: root.querySelector(".fx"), bloom: { strength: 1.2, radius: 0.6, threshold: 0.1 } }).then(S => {
  const orb = U.glowOrb(S, { radius: P.radius || 1, colors: P.colors, swirl: 1 });
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

### The effect API

| Name | What it is |
|---|---|
| `P` | Parameters: `P.w`, `P.h`, `P.dur`, `P.at`, `P.end`, `P.track`, `P.assets`, plus your own `params` at the top level |
| `root` | The effect's root element (`ROOT` in the style) |
| `U.clock(fn)` | **The only per-frame driver**: `fn(t)` with local time |
| `U.seed(n)` | **The only randomness** (seeded) |
| `U.trackAt(P.track, t)`, `U.follow(el, P.track)` | Face / hand position at `t`; stick an element to it |
| `U.three({el, bloom, camera})` | A three.js scene with an optional bloom composer, `toWorld(xPx, yPx, z)` and `render()` |
| `U.glowOrb`, `U.particles` | A glowing orb, a particle system |
| `U.draw`, `U.rough`, `U.tex` | SVG line drawing, Rough.js hand-drawn shapes, KaTeX formulas |
| `U.anime(tl)`, `U.lottie(anim)` | Hand over an anime.js timeline / Lottie animation (`autoplay: false`) for the clock to seek |
| `U.fonts([...])`, `U.ready(promise)` | Wait for the theme font; make the first frame wait for async setup |
| `U.scramble` | Seeded text scramble (instead of GSAP's ScrambleTextPlugin) |

Files the effect needs (Lottie JSON, textures, GLB models) go in `out/custom/<name>/`, and `P.assets` is their URL prefix.

### Determinism rules

HyperFrames renders by **seeking** each frame independently, often in parallel workers. An effect must therefore draw the same pixels for the same `t`, every time, in any order. The build **rejects** a file that contains any of these, even in a comment or a string:

| Forbidden | Use instead |
|---|---|
| `Date.now`, `new Date`, `performance.now`, `THREE.Clock` | `t` from `U.clock` |
| `Math.random`, `crypto.getRandomValues`, `anime.utils.random`, `gsap.utils.random`, `utils.random`, `utils.randomPick`, `utils.shuffle`, `"random(…)"` values, `from: "random"` staggers | `U.seed(n)` |
| `requestAnimationFrame`, `setTimeout`, `setInterval`, `setAnimationLoop`, `gsap.ticker`, `onUpdate`, `.play(` | `U.clock` |
| `onComplete`, `onRepeat`, `onRender`, `onBegin`, `onLoop`, `onStart`, `onReverseComplete`, `onBeforeUpdate`, `onPause`, `onInterrupt`, `onSwapped`, `.restart(` | Compute state from `t` (a seeking renderer skips these callbacks) |
| `d3.transition`, `AfterimagePass`, `GlitchEffect`, `ScrambleTextPlugin` | Library-internal time or randomness; use `U.scramble` for scrambles |

Other rules:

- Create anime.js and Lottie objects with `autoplay: false` and hand them to `U.anime` / `U.lottie`.
- Hand-placed `custom` effects get no automatic fade. Draw nothing before `P.at` and be gone by `P.end` (gate everything with a visibility factor, as above).
- Only the vendored three.js addons load (`RoomEnvironment`, `TextGeometry`, `FontLoader`, `GLTFLoader`, `EffectComposer`, `RenderPass`, `UnrealBloomPass`, `OutputPass`, `ShaderPass`, `SavePass`, `MaskPass`, `Pass`, `CopyShader`, `LuminosityHighPassShader`, `OutputShader`, `BufferGeometryUtils`). The build rejects any other addon.

## Gesture placement

When you say "here" / "there" without naming a place, or simply show it with your hands, Claude writes `"place": "gesture"` (for `custom` and `chip`) or `"speaker": "gesture"` (for `side`). A named place ("bottom right", "on the left") always wins.

The hand decides the spot, using the hand-shape tracks from `cutmate track`:

| What the hand does | Where the effect goes |
|---|---|
| An open / presenting palm | Just above that palm, following the hand for the whole span (`P.hands` holds both palms) |
| A clear index-finger point | The pointed spot, just past the fingertip |
| Neither | The higher visible hand |

The effect takes its position from the hand sample nearest to its start, so Claude anchors it on the **gesture** rather than on the word. Every visible gesture gets an effect sized to read on a phone: `burst` for a framed spot or a punch, `showcase-3d` on a presenting palm, `energy-ball` on a cupped hand, `hand-sparks` for spread hands, and `hand-control` for the clearest open palm.

Effects can also **follow** a tracked part for their whole span with `"follow": "face" | "hand_left" | "hand_right" | "hand"`. This needs a fresh `work/tracks.json`: run `cutmate track <out>` after every re-cut, because the build ignores tracks older than `aroll.mp4`.

## Saving an effect

After you accept a video that used a new custom effect:

```bash
cutmate save-effect <folder>/out <name> --description "what it does"
cutmate save-effect <folder>/out <name> --theme my-theme --force     # pick the theme, overwrite
```

This lints the effect, copies `out/custom/<name>.html` (and its asset folder) to `~/.cutmate/themes/<theme>/components/custom/`, and records it in that folder's `index.json`, together with the params and `follow` it was used with. Every later edit with that theme can then use it. See [customizing.md](customizing.md#3-saved-effects).
