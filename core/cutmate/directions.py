"""Theme directions: the seeded "surprise me" style roll, palette extraction from images, WCAG contrast."""
from __future__ import annotations

import random
from pathlib import Path

from .errors import CutmateError

# accent doubles as text/border on card (>= 3:1); on_accent is text on an accent fill (>= 4.5:1); ink is text on card.
# 6 light-card + 6 dark-card palettes, accents spread around the hue wheel.
PALETTES: list[dict] = [
    {"name": "paper-red", "accent": "#c1121f", "on_accent": "#ffffff", "text": "#ffffff", "ink": "#2b0a0d", "card": "#fdebeb", "muted": "#7a3b40"},
    {"name": "bubblegum", "accent": "#d6007a", "on_accent": "#ffffff", "text": "#ffffff", "ink": "#2b0a1c", "card": "#ffe3f1", "muted": "#8a4468"},
    {"name": "arctic", "accent": "#0057ff", "on_accent": "#ffffff", "text": "#ffffff", "ink": "#0b1b3a", "card": "#eaf2ff", "muted": "#5a6f96"},
    {"name": "mint", "accent": "#00875a", "on_accent": "#000000", "text": "#ffffff", "ink": "#06241b", "card": "#d9fbee", "muted": "#3f7a66"},
    {"name": "sand", "accent": "#8f4d00", "on_accent": "#ffffff", "text": "#ffffff", "ink": "#2a1d10", "card": "#f3e6cf", "muted": "#7d6a4f"},
    {"name": "violet", "accent": "#6d28d9", "on_accent": "#ffffff", "text": "#ffffff", "ink": "#1e0f3d", "card": "#f1ebff", "muted": "#6f5a9c"},
    {"name": "noir", "accent": "#ffd400", "on_accent": "#000000", "text": "#ffffff", "ink": "#f5f5f5", "card": "#121212", "muted": "#a0a0a0"},
    {"name": "lime", "accent": "#8dff3a", "on_accent": "#000000", "text": "#ffffff", "ink": "#e9f5df", "card": "#0f2a1a", "muted": "#8fb08f"},
    {"name": "ocean", "accent": "#00c8ff", "on_accent": "#000000", "text": "#ffffff", "ink": "#e8f6ff", "card": "#06263d", "muted": "#8fb8d4"},
    {"name": "magenta", "accent": "#ff3df0", "on_accent": "#000000", "text": "#ffffff", "ink": "#f6e9ff", "card": "#1c0a2e", "muted": "#b79ad6"},
    {"name": "coral", "accent": "#ff6f61", "on_accent": "#000000", "text": "#ffffff", "ink": "#e6fbf9", "card": "#0b3b3c", "muted": "#8cc7c4"},
    {"name": "periwinkle", "accent": "#8c9eff", "on_accent": "#000000", "text": "#ffffff", "ink": "#eceeff", "card": "#10143a", "muted": "#9aa3d9"},
]

# (display, text) - OFL Google families with Latin-Extended (Polish) glyphs
FONT_PAIRS: list[tuple[str, str]] = [
    ("Anton", "Inter"), ("Oswald", "Lato"), ("Archivo Black", "Archivo"),
    ("Space Grotesk", "Manrope"), ("Syne", "Rubik"), ("Unbounded", "Manrope"),
    ("Bricolage Grotesque", "DM Sans"), ("DM Serif Display", "DM Sans"),
    ("Playfair Display", "Source Sans 3"), ("Fraunces", "Work Sans"),
    ("Space Mono", "Space Grotesk"), ("Caveat", "Lato"),
    ("Titan One", "Rubik"), ("Bangers", "Manrope"),
]

SHAPES: dict[str, str] = {
    "sharp": "radius 0, flat fills, no shadows",
    "pill": "999px radii, soft shadow",
    "outline": "transparent cards, 4-6px borders in accent",
    "brutal": "thick ink border + hard offset shadow 8px 8px 0",
    "tape": "rotated label strips, -2..3 degrees",
}

MOTION: dict[str, str] = {
    "snappy": "expo.out 0.18-0.25s, short slides",
    "smooth": "sine.inOut 0.5-0.7s, fade + scale 0.96->1",
    "glitch": "steps(4) + seeded x/clip jitter via U.seed",
    "typewriter": "per-character stagger 0.03s",
    "slam": "scale 3->1, power4.in, rotation settle",
}

CAPTIONS: dict[str, str] = {
    "shadow": "white word captions with a soft drop shadow",
    "boxed": "accent box behind each word",
    "outline": "text stroke, no box",
    "highlight": "key words in an accent pill",
}

CLEAN: dict = {
    "mode": "bundled",
    "palette": {"name": "clean", "accent": "#7dd3fc", "on_accent": "#000000", "text": "#ffffff", "ink": "#0f172a",
                "card": "#ffffff", "muted": "#475569"},
    "fonts": {"display": "Inter", "text": "Inter"},
    "shapes": "rounded",
    "motion": "bouncy",
    "captions": "shadow",
}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise CutmateError(f"bad colour {h!r} (use #rgb or #rrggbb)")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        raise CutmateError(f"bad colour {h!r} (use #rgb or #rrggbb)") from None


def _lum(h: str) -> float:
    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio of two #rgb / #rrggbb colours (1..21)."""
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def roll(seed: int, avoid: list[dict] = ()) -> dict:
    """Deterministic random direction; palette, display font, shapes and motion differ from clean and from `avoid`."""
    rng = random.Random(seed)

    def clash(banned, pal, fonts, shapes, motion) -> bool:
        for d in banned:
            if "palette" in d and (d["palette"] or {}).get("name") == pal["name"]:
                return True
            if (d.get("fonts") or {}).get("display") == fonts[0]:
                return True
            if d.get("shapes") == shapes or d.get("motion") == motion:
                return True
        return False

    # Strict: differ from clean and every avoided theme. If that is exhausted (many themes), relax to
    # clean + the most recent avoided one so users with lots of themes still get a roll.
    for banned in ([CLEAN, *avoid], [CLEAN, *list(avoid)[-1:]]):
        for _ in range(500):
            pal = rng.choice(PALETTES)
            fonts = rng.choice(FONT_PAIRS)
            shapes = rng.choice(list(SHAPES))
            motion = rng.choice(list(MOTION))
            captions = rng.choice(list(CAPTIONS))
            if clash(banned, pal, fonts, shapes, motion):
                continue
            return {"mode": "random", "seed": seed, "palette": dict(pal),
                    "fonts": {"display": fonts[0], "text": fonts[1]},
                    "shapes": shapes, "motion": motion, "captions": captions,
                    "hints": {"shapes": SHAPES[shapes], "motion": MOTION[motion], "captions": CAPTIONS[captions]}}
        if len(avoid) <= 1:
            break
    raise CutmateError("no fresh style left - drop some --avoid themes or pick custom")


def suggest_name(direction: dict, taken: set[str]) -> str:
    pal = direction["palette"]
    base = f"{pal['name'] if isinstance(pal, dict) else pal}-{direction['shapes']}"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}-{n}"
    return name


def palette_of(images: list[Path], n: int = 8) -> list[tuple[str, float]]:
    """Dominant colours of the images as (hex, share), biggest share first."""
    from PIL import Image

    tiles = []
    for p in images:
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail((200, 200))
                tiles.append(im.copy())
        except (OSError, ValueError) as e:
            raise CutmateError(f"{p}: cannot read image ({e})") from None
    if not tiles:
        raise CutmateError("no images to take a palette from")
    w = sum(t.width for t in tiles)
    h = max(t.height for t in tiles)
    pool = Image.new("RGB", (w, h), (0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    x = 0
    for t in tiles:
        pool.paste(t, (x, 0))
        mask.paste(255, (x, 0, x + t.width, t.height))
        x += t.width
    q = pool.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = [0] * n
    idx = q.load()
    mk = mask.load()
    for yy in range(h):
        for xx in range(w):
            if mk[xx, yy]:
                i = idx[xx, yy]
                if i < n:
                    counts[i] += 1
    total = sum(counts) or 1
    out = [(f"#{pal[3*i]:02x}{pal[3*i+1]:02x}{pal[3*i+2]:02x}", c / total)
           for i, c in enumerate(counts) if c and 3 * i + 2 < len(pal)]
    return sorted(out, key=lambda t: -t[1])
