"""Theme layout: classic (the default) or split-panel (a persistent explainer panel in 9:16 shorts)."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import CutmateError

MODES = ("classic", "split-panel")
CAPTIONS = ("seam", "bottom")
TRANSITIONS = ("cut", "fade")
KEYS = ("mode", "panel", "ratio", "cadence", "captions", "transition", "fullscreen")


@dataclass(frozen=True)
class Layout:
    mode: str
    panel: str
    ratio: float
    cadence: tuple[float, float]
    captions: str
    transition: str
    fullscreen_max_per_min: int


SPLIT_DEFAULTS = Layout("split-panel", "top", 0.5, (1.0, 3.0), "seam", "cut", 3)
CLASSIC = replace(SPLIT_DEFAULTS, mode="classic")


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def layout_problems(raw) -> list[str]:
    """What is wrong with a theme.json `layout` value (None = absent = fine)."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["layout must be an object"]
    mode = raw.get("mode", "classic")
    if mode not in MODES:
        return ["layout.mode must be classic or split-panel"]
    if mode == "classic":
        return []
    p = [f"layout has unknown key {k!r}" for k in raw if k not in KEYS]
    if raw.get("panel", "top") != "top":
        p.append("layout.panel must be top")
    r = raw.get("ratio", SPLIT_DEFAULTS.ratio)
    if not _num(r) or not 0.40 <= r <= 0.60:
        p.append("layout.ratio must be 0.40–0.60")
    c = raw.get("cadence", SPLIT_DEFAULTS.cadence)
    if not (isinstance(c, (list, tuple)) and len(c) == 2 and all(_num(x) for x in c) and 0.5 <= c[0] < c[1] <= 6):
        p.append("layout.cadence must be [min, max] with 0.5 ≤ min < max ≤ 6")
    if raw.get("captions", "seam") not in CAPTIONS:
        p.append("layout.captions must be seam or bottom")
    if raw.get("transition", "cut") not in TRANSITIONS:
        p.append("layout.transition must be cut or fade")
    fs = raw.get("fullscreen", {})
    m = fs.get("max_per_min", SPLIT_DEFAULTS.fullscreen_max_per_min) if isinstance(fs, dict) else None
    if not isinstance(fs, dict) or set(fs) - {"max_per_min"} or isinstance(m, bool) or not isinstance(m, int) \
            or not 0 <= m <= 6:
        p.append("layout.fullscreen must be {\"max_per_min\": integer 0–6}")
    return p


def parse_layout(raw) -> Layout:
    problems = layout_problems(raw)
    if problems:
        raise CutmateError("theme layout: " + "; ".join(problems))
    if not isinstance(raw, dict) or raw.get("mode", "classic") == "classic":
        return CLASSIC
    d = SPLIT_DEFAULTS
    cad = raw.get("cadence", d.cadence)
    return Layout("split-panel", "top", float(raw.get("ratio", d.ratio)), (float(cad[0]), float(cad[1])),
                  raw.get("captions", d.captions), raw.get("transition", d.transition),
                  raw.get("fullscreen", {}).get("max_per_min", d.fullscreen_max_per_min))


def theme_layout(theme_path: Path) -> Layout:
    """The layout a theme folder declares (no theme.json or no `layout` key = classic)."""
    try:
        meta = json.loads((Path(theme_path) / "theme.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return CLASSIC
    return parse_layout(meta.get("layout") if isinstance(meta, dict) else None)
