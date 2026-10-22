"""plan.json — which graphic appears on which spoken word.

Anchors: "S2:word" (first occurrence in segment S2), "S2:word#2" (second), or a number (A-roll seconds).
Times resolve against out/work/aligned_words.json, so re-cutting moves every graphic with its word.
"""
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .cut import load_timed
from .errors import PlanError
from .formats import format_of
from .layout import SPLIT_DEFAULTS, Layout
from .tracks import face_median, gesture_at, load_tracks, place_at, tracks_fresh

TYPES = ("title", "counter", "list", "chip", "stamp", "bars", "point", "split", "pip", "lower-third", "custom", "bg", "side")
REQUIRED = {"title": ("at", "text"), "counter": ("at", "to", "label"), "list": ("items",), "chip": ("at", "text"),
            "stamp": ("at", "text"), "bars": ("at", "head", "rows"), "point": ("at", "image", "corner"),
            "split": ("from", "to"), "pip": ("from", "to", "media"), "lower-third": ("at", "name"),
            "custom": ("name",), "bg": ("from", "to"), "side": ("from", "to")}
TIMING_KEYS = ("type", "at", "from", "until", "hit", "sfx")
CORNERS = ("tl", "tr", "bl", "br")
HOLD = 2.5
PLATE = 1.5                       # chapter plate length (s)
ONLY = {"split": "9:16", "pip": "16:9", "lower-third": "16:9", "side": "16:9"}  # component → the only format it exists in
HINT = {"split": "in 16:9 use pip", "pip": "in 9:16 use split", "lower-third": "use chip or title in 9:16",
        "side": "in 9:16 use split"}
HOLDS = {"lower-third": 4.0}      # default hold per type (s); others use HOLD
PIP_CORNERS = ("br", "bl")
FOLLOW = ("face", "hand_left", "hand_right", "hand")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
FADE = {"bg": 0.3, "side": 0.45}  # entrance / exit of an effect expanded from bg / side (s), matching their components
SIDE_PANEL = {"right": [60, 60, 840, 960], "left": [1020, 60, 840, 960]}  # x, y, w, h in 1920x1080 px
SPLIT_PANEL = [40, 40, 1000, 820]  # x, y, w, h in 1080x1920 px (the .split-panel .media box)
BARE_MAX = {"9:16": 4.0, "16:9": 20.0}  # longest stretch of bare face (captions only) frame.md allows (s)
COVER_MIN = {"9:16": 0.5}              # share of the video with a visual layer on screen (frame.md)
HOOK = 1.5                             # the first seconds are exempt from the bare-face rule (the hook)
CTA_TAIL = 6.0                         # at most this much of the end (within the last segment) is exempt (the CTA)
MIN_CHECK = 8.0                        # shorter videos (the 5 s smoke render) are not density-checked
PANEL_ITEM_KEYS = ("at", "until", "effect", "params", "media", "fit", "sfx")
SCENE_KEYS = ("from", "to", "effect", "params", "media")
PANEL_REPLACES = ("split", "pip", "side", "bg")  # graphics the persistent panel replaces
ITEM_MIN, ITEM_SLACK = 0.6, 1.5   # panel item: shorter warns; longer than cadence max + slack warns (s)
PANEL_PACE = (1.1, 1.7)           # panel: one item per clause / key phrase — seconds per item (fast, slow end)
PANEL_GAP = 1.0                   # an empty panel longer than this (not covered by a scene) warns (s)
SCENE_MIN, SCENE_MAX = 1.0, 6.0   # full-screen scene: shorter is an error, longer warns (s)
SCENE_FADE = 0.25                 # entrance / exit of an effect scene (s)
_PUNCT = ".,!?;:…\"'„\u201c\u201d()[]–—-"


@dataclass
class Graphic:
    type: str
    start: float
    end: float | None
    params: dict
    hit: bool
    sfx: object
    index: int


@dataclass
class Plan:
    graphics: list
    captions: dict
    music: dict | None
    end: float
    warnings: list
    chapters: list = field(default_factory=list)
    face: dict = field(default_factory=dict)
    format: str = "9:16"
    tracks: dict | None = None          # tracks.json when it is fresh (not older than aroll.mp4), else None
    panel: dict | None = None           # {"start", "end", "ratio", "open_at_zero", "stays", "items"} when plan.json has a panel
    layout: Layout | None = None        # the theme layout load_plan was given (None = split-panel defaults for validation)


def norm(word: str) -> str:
    return str(word).replace("\u2019", "'").strip().strip(_PUNCT).lower()


def resolve_anchor(a, words: list[dict], end: float) -> tuple[float, float]:
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        t = float(a)
        if not 0 <= t <= end:
            raise PlanError(f"anchor {a} is outside the video (0–{end:.2f}s)")
        return t, t
    if not isinstance(a, str) or ":" not in a:
        raise PlanError(f"bad anchor {a!r}: use \"S2:word\", \"S2:word#2\" or seconds")
    seg, _, rest = a.partition(":")
    word, n = rest, 1
    m = re.fullmatch(r"(.*)#(\d+)", rest)
    if m:
        word, n = m.group(1), int(m.group(2))
    seg_words = [w for w in words if str(w["seg"]) == seg]
    if not seg_words:
        names = ", ".join(sorted({str(w["seg"]) for w in words}))
        raise PlanError(f"anchor {a!r}: no segment {seg!r} (segments: {names})")
    hits = [w for w in seg_words if norm(w["word"]) == norm(word)]
    if len(hits) < n:
        hits = [w for w in seg_words if norm(w["word"]) == norm(word + "%")]
    if len(hits) < n:
        raise PlanError(f"anchor {a!r}: word {word!r} #{n} not in {seg} "
                        f"(words: {' '.join(w['word'] for w in seg_words)})")
    w = hits[n - 1]
    return float(w["start"]), float(w["end"])


def _media(rel, rec: Path, where: str) -> str:
    p = Path(str(rel))
    p = p if p.is_absolute() else rec / p
    if not p.exists():
        raise PlanError(f"{where}: media not found: {p}")
    return str(p)


def _effect_params(g: dict, rec: Path, where: str, params: dict) -> None:
    """An effect's "params" (an object); a string params.media is a file next to the recording, like "media"."""
    if "params" not in g:
        return
    if not isinstance(g["params"], dict):
        raise PlanError(f'{where}: "params" must be an object')
    p = dict(g["params"])
    if isinstance(p.get("media"), str):
        p["media"] = _media(p["media"], rec, where)
    params["params"] = p


def _media_or_effect(g: dict, params: dict, rec: Path, where: str) -> None:
    if ("media" in g) == ("effect" in g):
        raise PlanError(f'{where}: needs exactly one of "media" or "effect"')
    if "media" in g:
        params["media"] = _media(g["media"], rec, where)
    elif not NAME_RE.match(str(g["effect"])):
        raise PlanError(f"{where}: effect must be an effect name (e.g. space-bg)")
    else:
        _effect_params(g, rec, where, params)


def _range(g: dict, words: list[dict], end: float, where: str) -> tuple[float, float]:
    if "to" not in g:
        raise PlanError(f'{where}: missing "to"')
    start = resolve_anchor(g["from"], words, end)[0]
    stop = resolve_anchor(g["to"], words, end)[1]
    if stop <= start:
        raise PlanError(f"{where}: \"to\" is before the start")
    return start, stop


def _graphic(i: int, g, words: list[dict], end: float, rec: Path, fmt: str = "9:16") -> Graphic:
    where = f"graphic #{i + 1}"
    if not isinstance(g, dict) or "type" not in g:
        raise PlanError(f"{where}: must be an object with a \"type\"")
    t = g["type"]
    if t not in TYPES:
        raise PlanError(f"{where}: unknown type {t!r} (use {', '.join(TYPES)})")
    where = f"graphic #{i + 1} ({t})"
    if t in ONLY and ONLY[t] != fmt:
        raise PlanError(f"{where}: {t} is not available in {fmt} ({HINT[t]})")
    for k in REQUIRED[t]:
        if k not in g:
            raise PlanError(f"{where}: missing \"{k}\"")
    if "place" in g:
        if t not in ("custom", "chip"):
            raise PlanError(f'{where}: "place" works only on custom and chip')
        if g["place"] != "gesture":
            raise PlanError(f'{where}: place must be "gesture"')
    if g.get("speaker") == "gesture" and t != "side":
        raise PlanError(f'{where}: speaker "gesture" works only on side')
    params = {k: v for k, v in g.items() if k not in TIMING_KEYS}
    stop = None
    if t in ("split", "pip"):
        start, stop = _range(g, words, end, where)
        if t == "split":
            _media_or_effect(g, params, rec, where)
        else:
            params["media"] = _media(g["media"], rec, where)
        fit = g.get("fit", "cover" if t == "pip" else "contain")
        if fit not in ("contain", "cover"):
            raise PlanError(f"{where}: fit must be contain or cover")
        params["fit"] = fit
        if t == "pip":
            corner = g.get("corner", "br")
            if corner not in PIP_CORNERS:
                raise PlanError(f"{where}: corner must be br or bl")
            params["corner"] = corner
        params.pop("to", None)
        params.pop("from", None)
    elif t == "list":
        if not isinstance(g["items"], list) or not g["items"]:
            raise PlanError(f"{where}: \"items\" must be a non-empty list")
        if len(g["items"]) > 4:
            raise PlanError(f"{where}: a list has at most 4 items (got {len(g['items'])})")
        items = []
        for j, it in enumerate(g["items"]):
            if not isinstance(it, dict) or "text" not in it or "at" not in it:
                raise PlanError(f"{where}: item {j + 1} needs \"text\" and \"at\"")
            items.append({"text": str(it["text"]), "at": resolve_anchor(it["at"], words, end)[0]})
        params["items"] = items
        start = min(x["at"] for x in items)
        stop = max(x["at"] for x in items) + HOLD
    elif t == "custom":
        if not NAME_RE.match(str(g["name"])):
            raise PlanError(f"{where}: name must be lowercase letters, digits and dashes (e.g. energy-ball)")
        if "from" in g:
            start, stop = _range(g, words, end, where)
        elif "at" in g:
            start = resolve_anchor(g["at"], words, end)[0]
        else:
            raise PlanError(f'{where}: needs "at" or "from"/"to"')
        if "follow" in g and g["follow"] not in FOLLOW:
            raise PlanError(f"{where}: follow must be one of {', '.join(FOLLOW)}")
        r = g.get("region")
        if "region" in g and not (isinstance(r, list) and len(r) == 4 and all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0 for x in r) and r[2] > 0 and r[3] > 0):
            raise PlanError(f"{where}: region must be [x, y, w, h] in px (non-negative numbers, w and h > 0)")
        params = {k: g[k] for k in ("name", "follow", "region", "place") if k in g}
        _effect_params(g, rec, where, params)
        if "media" in g:
            if not isinstance(g["media"], str):
                raise PlanError(f'{where}: "media" must be a file path')
            params["media"] = _media(g["media"], rec, where)
    elif t in ("bg", "side"):
        start, stop = _range(g, words, end, where)
        _media_or_effect(g, params, rec, where)
        if t == "side":
            sp = g.get("speaker", "right")
            if sp not in ("right", "left", "gesture"):
                raise PlanError(f"{where}: speaker must be right, left or gesture")
            params["speaker"] = sp
        params.pop("from", None)
        params.pop("to", None)
    else:
        start = resolve_anchor(g["at"], words, end)[0]
    if t == "counter" and (isinstance(g["to"], bool) or not isinstance(g["to"], (int, float))):
        raise PlanError(f"{where}: \"to\" must be a number")
    if t == "stamp" and len(str(g["text"]).split()) != 1:
        raise PlanError(f"{where}: stamp text must be one word")
    if t == "point":
        if g["corner"] not in CORNERS:
            raise PlanError(f"{where}: corner must be one of {', '.join(CORNERS)}")
        params["image"] = _media(g["image"], rec, where)
    if t == "bars":
        rows = g["rows"]
        if isinstance(rows, list) and len(rows) > 3:
            raise PlanError(f"{where}: bars have at most 3 rows (got {len(rows)})")
        if not isinstance(rows, list) or not rows or any(
                not isinstance(r, dict) or "label" not in r or isinstance(r.get("value"), bool)
                or not isinstance(r.get("value"), (int, float)) for r in rows):
            raise PlanError(f"{where}: \"rows\" must be a list of {{\"label\", \"value\": number}}")
        params["illustrative"] = bool(g.get("illustrative", False))
    for k in ("logo", "icon"):
        if g.get(k):
            params[k] = _media(g[k], rec, where)
    if "until" in g:
        u = g["until"]
        if isinstance(u, (int, float)) and not isinstance(u, bool):
            stop = float(u)
        else:
            stop = resolve_anchor(u, words, end)[1]
        if stop <= start:
            raise PlanError(f"{where}: \"until\" is before the start")
    return Graphic(t, round(start, 3), stop, params, bool(g.get("hit", False)), g.get("sfx"), i)


def panel_box(ratio: float) -> list[int]:
    """The panel's content box [x, y, w, h] in 1080x1920 px for a panel taking `ratio` of the frame height."""
    return [40, 40, 1000, round(1920 * ratio) - 80]


def _layer(g: Graphic) -> bool:
    """A planner-made layer (the persistent panel, its items, a full-screen scene), not a band graphic."""
    return g.type == "panel" or bool(g.params.get("_panel") or g.params.get("_scene"))


def _until(u, words: list[dict], end: float) -> float:
    if isinstance(u, (int, float)) and not isinstance(u, bool):
        return float(u)
    return resolve_anchor(u, words, end)[1]


def _uncovered(a: float, b: float, covers) -> float:
    """Seconds of a..b that no cover span (a scene) overlaps."""
    cur, free = a, 0.0
    for c0, c1 in sorted(covers):
        if c1 <= cur or c0 >= b:
            continue
        free += max(0.0, c0 - cur)
        cur = max(cur, c1)
    return free + max(0.0, b - cur)


def _panel(raw: dict, words: list[dict], end: float, rec: Path, fmt: str, layout: Layout | None,
           covers=()) -> tuple[list[Graphic], dict | None, list[str]]:
    """plan.json "panel" → the frame host Graphic("panel") + one custom / panel-media Graphic per item.
    `covers` are the full-screen scene spans (a panel gap under a scene does not warn)."""
    if "panel" not in raw:
        return [], None, []
    items = raw["panel"]
    if not isinstance(items, list) or not items:
        raise PlanError('"panel" must be a non-empty list of items {"at", "effect" | "media"}')
    lay = layout if layout is not None and layout.mode == "split-panel" else SPLIT_DEFAULTS
    box = panel_box(lay.ratio)
    rows = []
    for i, it in enumerate(items):
        bare = f"panel item #{i + 1}"
        if not isinstance(it, dict) or "at" not in it:
            raise PlanError(f'{bare}: must be an object with "at"')
        for k in it:
            if k not in PANEL_ITEM_KEYS:
                raise PlanError(f"{bare}: unknown key {k!r} (use {', '.join(PANEL_ITEM_KEYS)})")
        name = str(it["effect"]) if "effect" in it else Path(str(it.get("media", "?"))).name
        where = f"{bare} ({name})" if ("effect" in it) != ("media" in it) else bare
        params: dict = {}
        _media_or_effect(it, params, rec, where)
        if "fit" in it:
            if "media" not in it:
                raise PlanError(f'{where}: "fit" works only with "media"')
            if it["fit"] not in ("contain", "cover"):
                raise PlanError(f"{where}: fit must be contain or cover")
        start = resolve_anchor(it["at"], words, end)[0]
        if rows and start <= rows[-1]["start"]:
            raise PlanError(f"{bare}: starts before or with item #{i} ({rows[-1]['start']:.2f}s) — "
                            f"items go in time order")
        if start >= end - 0.05:
            raise PlanError(f"{where}: starts at {start:.2f}s, too close to the end ({end:.2f}s)")
        until = None
        if "until" in it:
            until = _until(it["until"], words, end)
            if until <= start:
                raise PlanError(f'{where}: "until" is before the start')
        rows.append({"start": start, "until": until, "name": name, "where": where, "params": params, "raw": it})
    for j, r in enumerate(rows):
        nxt = rows[j + 1]["start"] if j + 1 < len(rows) else None
        stop = r["until"] if r["until"] is not None else (nxt if nxt is not None else r["start"] + lay.cadence[1])
        if nxt is not None:
            stop = min(stop, nxt)
        r["end"] = min(stop, end - 0.05)
    span_start, span_end = rows[0]["start"], rows[-1]["end"]
    open_at_zero, stays = span_start < 0.5, span_end >= end - 0.5
    if open_at_zero:
        span_start = rows[0]["start"] = 0.0
    if stays:
        span_end = rows[-1]["end"] = end - 0.05
    warns = []
    longest = lay.cadence[1] + ITEM_SLACK
    shortest = min(ITEM_MIN, lay.cadence[0])          # a reel-paced theme (cadence min 0.5 s) may cut every 0.5 s
    for j, r in enumerate(rows):
        d = r["end"] - r["start"]
        if d < shortest - 1e-6:
            warns.append(f"WARN panel item #{j + 1} ({r['name']}) is {d:.1f} s — shorter than {shortest:g} s, "
                         f"too fast to read")
        elif d > longest + 1e-6:
            warns.append(f"WARN panel item #{j + 1} ({r['name']}) is {d:.1f} s — longer than {longest:g} s "
                         f"(cadence max {lay.cadence[1]:g} s): split it or add an item")
        if j + 1 < len(rows):
            a, b = r["end"], rows[j + 1]["start"]
            if b - a > PANEL_GAP and _uncovered(a, b, covers) > PANEL_GAP + 1e-6:
                warns.append(f"WARN panel gap {a:.1f}–{b:.1f} s ({b - a:.1f} s) — the panel is empty: "
                             f"extend an item or cover the gap with a scene")
    # pace: about one item per clause / key phrase (1-2 s), not one per sentence; time under a scene needs none
    shown = _uncovered(span_start, span_end, covers)
    fast, slow = max(lay.cadence[0], PANEL_PACE[0]), max(lay.cadence[0], min(PANEL_PACE[1], lay.cadence[1]))
    if shown >= MIN_CHECK and shown / len(rows) > slow + 0.05:
        warns.append(f"WARN panel pace: {len(rows)} items in {shown:.1f} s (one per {shown / len(rows):.1f} s) — "
                     f"aim for {round(shown / slow)}–{round(shown / fast)}: one item per clause / key phrase, "
                     f"mix templates and page screenshots")
    gs = []
    last = len(rows) - 1
    for j, r in enumerate(rows):
        enter = ("cut" if open_at_zero else "slide") if j == 0 else lay.transition
        exit_ = ("none" if stays else "slide") if j == last else "none"
        it, params = r["raw"], r["params"]
        if "effect" in it:
            p = {"name": str(it["effect"]), "region": list(box)}
            if "params" in params:
                p["params"] = params["params"]
            gtype = "custom"
        else:
            p = {"media": params["media"], "fit": it.get("fit", "cover")}
            gtype = "panel-media"
        p.update({"_panel": True, "_enter": enter, "_exit": exit_})
        gs.append(Graphic(gtype, round(r["start"], 3), round(r["end"], 3), p, False, it.get("sfx"), j))
    span_start, span_end = round(span_start, 3), round(span_end, 3)
    host = Graphic("panel", span_start, span_end, {"ratio": lay.ratio, "open_at_zero": open_at_zero, "stays": stays},
                   False, None, 0)
    info = {"start": span_start, "end": span_end, "ratio": lay.ratio, "open_at_zero": open_at_zero, "stays": stays,
            "items": len(rows)}
    return [host] + gs, info, warns


def _scenes(raw: dict, words: list[dict], end: float, rec: Path, fmt: str,
            layout: Layout | None) -> tuple[list[Graphic], list[str]]:
    """plan.json "scenes" → full-frame covers: Graphic("scene") for media, a region-less custom for an effect."""
    if "scenes" not in raw:
        return [], []
    sc = raw["scenes"]
    if not isinstance(sc, list) or not sc:
        raise PlanError('"scenes" must be a non-empty list of {"from", "to", "effect" | "media"}')
    lay = layout if layout is not None and layout.mode == "split-panel" else SPLIT_DEFAULTS
    gs, warns = [], []
    for i, s in enumerate(sc):
        bare = f"scene #{i + 1}"
        if not isinstance(s, dict) or "from" not in s:
            raise PlanError(f'{bare}: must be an object with "from" and "to"')
        for k in s:
            if k not in SCENE_KEYS:
                raise PlanError(f"{bare}: unknown key {k!r} (use {', '.join(SCENE_KEYS)})")
        name = str(s["effect"]) if "effect" in s else Path(str(s.get("media", "?"))).name
        where = f"{bare} ({name})" if ("effect" in s) != ("media" in s) else bare
        start, stop = _range(s, words, end, where)
        stop = min(stop, end - 0.05)
        d = stop - start
        if d < SCENE_MIN - 1e-6:
            raise PlanError(f"{where}: lasts {d:.1f} s — a full-screen scene needs at least {SCENE_MIN:.1f} s")
        if d > SCENE_MAX + 1e-6:
            warns.append(f"WARN {where} is {d:.1f} s — longer than {SCENE_MAX:g} s, the speaker is gone too long")
        params: dict = {}
        _media_or_effect(s, params, rec, where)
        if "effect" in s:
            p = {"name": str(s["effect"])}
            if "params" in params:
                p["params"] = params["params"]
            p.update({"_fade": SCENE_FADE, "_scene": True})
            gs.append(Graphic("custom", round(start, 3), round(stop, 3), p, False, None, i))
        else:
            gs.append(Graphic("scene", round(start, 3), round(stop, 3), {"media": params["media"], "_scene": True},
                              False, None, i))
    ordered = sorted(gs, key=lambda g: g.start)
    for a, b in zip(ordered, ordered[1:]):
        if b.start < a.end - 1e-6:                     # two full-frame covers at once: one hides the other's text
            first, second = sorted((a.index, b.index))
            raise PlanError(f"scene #{second + 1} overlaps scene #{first + 1}")
    allowed = math.ceil(lay.fullscreen_max_per_min * end / 60 - 1e-9)
    if len(gs) > allowed:
        warns.append(f"WARN scenes: {len(gs)} (layout allows {allowed} in {end:.0f} s at "
                     f"{lay.fullscreen_max_per_min} per minute) — keep the speaker on screen")
    return gs, warns


_HINTS = {"stat-card": lambda p: f"{_fmt(p['value']) if _number(p.get('value')) else p.get('value', '')}"
                                 f"{p.get('suffix', '')}",
          "ui-mock": lambda p: p.get("kind", ""), "checklist": lambda p: p.get("title", ""),
          "headline": lambda p: p.get("text", ""),
          "flow": lambda p: (p.get("nodes") or [""])[0] if isinstance(p.get("nodes"), list) else ""}


def panel_summary(plan: Plan) -> list[str]:
    """One line per panel item ("0.00–1.40 stat-card 44%"), then one per full-screen scene — the timeline at a glance."""
    lines, scenes = [], []
    for g in plan.graphics:
        if g.params.get("_panel"):
            if g.type == "panel-media":
                line = f"{g.start:.2f}–{g.end:.2f} {Path(g.params['media']).name}"
            else:
                ep = g.params.get("params") or {}
                hint = str(_HINTS[g.params["name"]](ep)) if g.params["name"] in _HINTS else ""
                line = f"{g.start:.2f}–{g.end:.2f} {g.params['name']}" + (f" {hint}" if hint else "")
            lines.append(line if len(line) <= 60 else line[:59] + "…")
        elif g.params.get("_scene"):
            what = Path(g.params["media"]).name if g.type == "scene" else g.params["name"]
            scenes.append(f"{g.start:.2f}–{g.end:.2f} SCENE {what}")
    return lines + scenes


def _chapters(raw: dict, words: list[dict], end: float) -> list[dict]:
    ch = raw.get("chapters")
    if ch is None:
        return []
    if not isinstance(ch, list) or not ch:
        raise PlanError('"chapters" must be a non-empty list of {"at", "title"}')
    out = []
    for j, c in enumerate(ch):
        if not isinstance(c, dict) or "at" not in c or not str(c.get("title", "")).strip():
            raise PlanError(f'chapter {j + 1}: needs "at" and "title"')
        title = str(c["title"]).strip()
        if len(title) > 40:
            raise PlanError(f"chapter {j + 1}: title longer than 40 characters ({len(title)})")
        out.append({"start": round(resolve_anchor(c["at"], words, end)[0], 3), "title": title, "num": j + 1})
    if any(b["start"] <= a["start"] for a, b in zip(out, out[1:])):
        raise PlanError("chapters must be in order (each one starts after the previous one)")
    return out


def plate_chapters(chs: list[dict], end: float) -> list[dict]:
    """Chapters 2+ that get a full-screen plate (not so close to the end that the plate would be cut off)."""
    return [c for c in chs[1:] if c["start"] < end - 0.35]


def _chapter_warnings(chs: list[dict], gs: list[Graphic], end: float, first_word: float = 0.0) -> list[str]:
    w = []
    if chs and chs[0]["start"] - first_word > 0.5:
        w.append(f"WARN chapter 1 starts at {chs[0]['start']:.1f}s — it is listed as 00:00")
    if chs and len(chs) < 3:
        w.append(f"WARN {len(chs)} chapters — YouTube needs at least 3 to show chapter markers")
    bounds = [0.0] + [c["start"] for c in chs[1:]] + [end]  # the first chapter always starts at 00:00
    for c, a, b in zip(chs, bounds, bounds[1:]):
        if b - a < 10:
            w.append(f"WARN chapter {c['num']} ({c['title']}) lasts {b - a:.1f}s — YouTube needs at least 10 s")
    for c in chs[1:]:
        for g in gs:
            if c["start"] - 0.05 < g.start < c["start"] + PLATE:
                w.append(f"WARN {g.type} at {g.start:.1f}s starts under the chapter {c['num']} plate "
                         f"({c['start']:.1f}–{c['start'] + PLATE:.1f}s)")
    return w


def _face(raw: dict, words: list[dict]) -> dict:
    f = raw.get("face")
    if f is None:
        return {}
    if not isinstance(f, dict):
        raise PlanError('"face" must be an object like {"S1": [0.42, 0.3]}')
    segs = {str(w["seg"]) for w in words}
    out = {}
    for k, v in f.items():
        if k not in segs:
            raise PlanError(f"face: no segment {k!r} (segments: {', '.join(sorted(segs))})")
        if not (isinstance(v, list) and len(v) == 2 and all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1 for x in v)):
            raise PlanError(f"face {k}: must be [x, y] with fractions 0–1 of the frame")
        out[k] = [float(v[0]), float(v[1])]
    return out


def _resolve_gestures(gs: list[Graphic], tr: dict | None) -> list[str]:
    """place/speaker "gesture" -> concrete values from the pointing tracks (before _expand, so regions follow)."""
    uses = [g for g in gs if g.params.get("place") == "gesture" or g.params.get("speaker") == "gesture"]
    if uses and tr is None:
        g = uses[0]
        raise PlanError(f"graphic #{g.index + 1} ({g.type}): gesture needs out/work/tracks.json (fresh) — run `cutmate track`")
    w = []
    pointing = any(k in tr["tracks"] for k in ("point_left", "point_right")) if uses else True
    if not pointing:
        w.append("WARN tracks.json has no pointing data — run `cutmate track --force`")
    places = [g for g in uses if g.params.get("place") == "gesture" and g.type in ("custom", "chip")]
    if places and pointing and not any(k in tr["tracks"] for k in ("palm_left", "palm_right")):
        w.append("WARN tracks.json has no hand-shape data (open palm / index point) — run `cutmate track --force`")
    for g in uses:
        hit = gesture_at(tr["tracks"], g.start)
        if g in places:
            spot = place_at(tr["tracks"], g.start)
            if spot:                                    # open palm: the effect sits on it and follows that hand
                g.params["place_xy"] = [spot["x"], spot["y"]]
                if spot["track"]:
                    g.params["place_track"] = spot["track"]
            elif pointing:
                w.append(f"WARN {g.type} at {g.start:.1f}s: no pointing gesture near the anchor — default position")
        if g.params.get("speaker") == "gesture":
            if hit:
                g.params["speaker"] = "right" if hit["side"] == "left" else "left"
            else:
                g.params["speaker"] = "right"
                if pointing:
                    w.append(f"WARN {g.type} at {g.start:.1f}s: no pointing gesture near the anchor — speaker right")
    return w


def _expand(gs: list[Graphic]) -> list[Graphic]:
    out = []
    for g in gs:
        if g.type == "split" and "effect" in g.params:
            out.append(g)
            # the effect rides with the panel (slides in / out with it), so it is never left over the speaker
            p = {"name": g.params["effect"], "_slide": SPLIT_PANEL[1] * 2 + SPLIT_PANEL[3], "region": list(SPLIT_PANEL)}
            if "params" in g.params:
                p["params"] = g.params["params"]
            out.append(Graphic("custom", g.start, g.end, p, False, False, g.index))
            continue
        if g.type in ("bg", "side") and "effect" in g.params:
            p = {"name": g.params["effect"], "_fade": FADE[g.type]}
            if "params" in g.params:
                p["params"] = g.params["params"]
            if g.type == "side":
                p["region"] = list(SIDE_PANEL[g.params["speaker"]])
            out.append(Graphic("custom", g.start, g.end, p, False, False, g.index))
        out.append(g)
    return out


def _expanded_pair(a: Graphic, b: Graphic) -> bool:
    if a.start != b.start or a.end != b.end:
        return False
    if a.type == "custom" and b.type in ("bg", "side"):
        return b.params.get("effect") == a.params.get("name")
    return a.type == "split" and b.type == "custom" and a.params.get("effect") == b.params.get("name")


def _density(spans: list[tuple[float, float]], end: float, fmt: str, last_start: float) -> list[str]:
    """Bare-face stretches over the frame.md limit and (9:16) the share of the video with a visual on screen.
    Every graphic counts (b-roll, split / pip / side, effects, chips, stamps); captions alone do not. The first HOOK
    seconds and the CTA tail (the last segment, at most CTA_TAIL s) are exempt from the bare-face rule; videos shorter
    than MIN_CHECK are not checked."""
    if end < MIN_CHECK:
        return []
    lo, hi = HOOK, end - min(end - last_start, CTA_TAIL)
    spans = [(max(0.0, a), min(end, b)) for a, b in spans if min(end, b) > max(0.0, a)]  # only what is on screen
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    w, cur, limit = [], lo, BARE_MAX.get(fmt)
    for a, b in [m for m in merged if m[1] > lo and m[0] < hi] + [[hi, hi]]:
        a, b = max(a, lo), min(b, hi)
        if limit is not None and a - cur > limit + 1e-6:
            w.append(f"WARN density: bare face {cur:.1f}–{a:.1f} s ({a - cur:.1f} s) — add a graphic, b-roll or chip "
                     f"(frame.md: max {limit:g} s in {fmt})")
        cur = max(cur, b)
    if fmt in COVER_MIN:
        ratio = sum(b - a for a, b in merged) / end
        if ratio < COVER_MIN[fmt] - 1e-9:
            w.append(f"WARN density: visuals on screen {round(100 * ratio)} % (frame.md: ≥ {round(100 * COVER_MIN[fmt])} %)")
    return w


def _budget(gs: list[Graphic], end: float | None = None, fmt: str = "9:16", last_start: float | None = None,
            plates: list[tuple[float, float]] = ()) -> list[str]:
    w = []
    bg = sum(g.end - g.start for g in gs if g.type == "bg")
    if bg > 30:
        w.append(f"WARN bg covers {bg:.0f}s — background removal takes ~{17 * bg / 60:.0f} min on CPU")
    hits = [g for g in gs if g.hit]
    if len(hits) > 2:
        w.append(f"WARN {len(hits)} graphics with \"hit\" (budget 2) at " + ", ".join(f"{g.start:.1f}s" for g in hits))
    titles = [g for g in gs if g.type == "title"]
    if len(titles) > 1:
        w.append(f"WARN {len(titles)} titles (budget 1)")
    band = [g for g in gs if not _layer(g)]    # the panel, its items and the scenes are layers of their own
    for a, b in zip(band, band[1:]):
        if b.start < a.end and not _expanded_pair(a, b):
            w.append(f"WARN {a.type} ({a.start:.1f}–{a.end:.1f}s) overlaps {b.type} at {b.start:.1f}s")
    if end is not None and last_start is not None:
        w += _density([(g.start, g.end) for g in gs if g.type != "panel"] + list(plates), end, fmt, last_start)
    return w


def _glb_warnings(gs: list[Graphic]) -> list[str]:
    w = []
    for g in gs:
        p = g.params.get("params") or {}
        if g.type != "custom" or p.get("shape") != "glb" or p.get("model"):
            continue
        media = g.params.get("media") or p.get("media")
        if not (isinstance(media, str) and Path(media).suffix.lower() in (".glb", ".gltf")):
            w.append(f'WARN {g.type} at {g.start:.1f}s: shape "glb" needs a .glb / .gltf "media" — it falls back to the torus knot')
    return w


def _fmt(n) -> str:
    return str(int(float(n))) if float(n).is_integer() else str(n)


def _number(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        return isinstance(v, str) and math.isfinite(float(v))
    except ValueError:
        return False


def _factcheck(out: Path, gs: list[Graphic]) -> list[str]:
    f = out / "factcheck.md"
    ok = [line for line in f.read_text(encoding="utf-8").splitlines() if "✅" in line] if f.exists() else []
    w = []
    for g in gs:
        if g.type == "counter":
            nums = [g.params["to"]]
        elif g.type == "bars" and not g.params.get("illustrative"):
            nums = [r["value"] for r in g.params["rows"]]
        elif g.type == "custom" and g.params.get("name") in ("stat-card", "checklist"):
            ep = g.params.get("params") or {}
            src = ep if g.params["name"] == "stat-card" else ep.get("summary")
            v = src.get("value") if isinstance(src, dict) else None
            nums = [v] if _number(v) else []
        else:
            nums = []
        for n in nums:
            s = _fmt(n)
            if not any(re.search(rf"(?<![\d,.]){re.escape(s)}(?![\d])", line) for line in ok):
                w.append(f"WARN {g.type} at {g.start:.1f}s shows {s}, which no ✅ line in factcheck.md confirms")
    return w


def load_plan(out_dir: Path, factcheck: bool = False, layout: Layout | None = None) -> Plan:
    out = Path(out_dir).resolve()
    p = out / "plan.json"
    if not p.exists():
        raise PlanError(f"{p} not found — write the plan first")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlanError(f"{p}: invalid JSON ({e.msg}, line {e.lineno})") from None
    if not isinstance(raw, dict):
        raise PlanError(f"{p}: must be a JSON object")
    fmt = format_of(out)
    words_p = out / "work" / "aligned_words.json"
    if not words_p.exists():
        raise PlanError(f"{words_p} not found — run `cutmate align` first")
    try:
        words = json.loads(words_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlanError(f"{words_p}: invalid JSON ({e.msg}, line {e.lineno})") from None
    if not isinstance(words, list):
        raise PlanError(f"{words_p}: must be a list")
    for j, w in enumerate(words):
        if not isinstance(w, dict) or not all(k in w for k in ("seg", "word", "start", "end")):
            raise PlanError(f"{words_p}: entry {j} missing seg/word/start/end")
        if not isinstance(w.get("start"), (int, float)) or not isinstance(w.get("end"), (int, float)):
            raise PlanError(f"{words_p}: entry {j} start/end must be numbers")
    timed = load_timed(out)
    end = float(timed[-1]["end"])
    graphics_list = raw.get("graphics")
    if graphics_list is not None and not isinstance(graphics_list, list):
        raise PlanError(f"{p}: \"graphics\" must be a list")
    if fmt != "9:16":
        for k in ("panel", "scenes"):
            if k in raw:
                raise PlanError(f'{p}: "{k}": panel exists only in 9:16 — use side / pip')
    gs = sorted((_graphic(i, g, words, end, out.parent, fmt) for i, g in enumerate(graphics_list or [])),
                key=lambda g: g.start)
    scene_gs, scene_warns = _scenes(raw, words, end, out.parent, fmt, layout)
    panel_gs, panel, panel_warns = _panel(raw, words, end, out.parent, fmt, layout,
                                          [(g.start, g.end) for g in scene_gs])
    if panel is not None:
        for g in gs:
            if g.type in PANEL_REPLACES:
                raise PlanError(f"graphic #{g.index + 1} ({g.type}): the panel replaces {g.type} — make it a panel item")
    tr = load_tracks(out)
    if tr is not None and not tracks_fresh(out):
        if any(g.params.get("follow") for g in gs):
            raise PlanError("out/work/tracks.json is older than aroll.mp4 — run `cutmate track`")
        tr = None
    if any(g.params.get("follow") for g in gs) and tr is None:
        raise PlanError("follow needs out/work/tracks.json — run `cutmate track`")
    gesture_warns = _resolve_gestures(gs, tr)
    gs = sorted(_expand(gs) + panel_gs + scene_gs, key=lambda g: g.start)
    band = [g for g in gs if not _layer(g)]     # panel items / scenes have their ends; they do not cut band holds
    for i, g in enumerate(band):
        if g.end is None:
            nxt = band[i + 1].start - 0.05 if i + 1 < len(band) else end
            g.end = min(g.start + HOLDS.get(g.type, HOLD), nxt)
        g.end = round(max(min(g.end, end - 0.05), min(g.start + 0.3, end - 0.05)), 3)
        if g.end <= g.start:
            raise PlanError(f"graphic #{g.index + 1} ({g.type}) starts at {g.start:.2f}s, too close to the end ({end:.2f}s)")
    chapters = _chapters(raw, words, end)
    face = _face(raw, words)
    if tr:
        for s in timed:
            sid = str(s["id"])
            if sid not in face:
                fm = face_median(tr["tracks"], float(s["start"]), float(s["end"]))
                if fm:
                    face[sid] = fm
    if panel and not face:
        panel_warns.append("WARN panel: no face position (no out/work/tracks.json, no plan \"face\") — the face is "
                           "placed by a guess and may sit too low in the bottom part; run `cutmate track <out>` and rebuild")
    plates = [(c["start"], min(c["start"] + PLATE, end)) for c in plate_chapters(chapters, end)]
    warnings = gesture_warns + panel_warns + scene_warns + _glb_warnings(gs) + _budget(gs, end, fmt, float(timed[-1]["start"]), plates) + _chapter_warnings(chapters, gs, end, min((w['start'] for w in words), default=0.0)) + (_factcheck(out, gs) if factcheck else [])
    cap = raw.get("captions") or {}
    if not isinstance(cap, dict):
        raise PlanError(f"{p}: \"captions\" must be a dict")
    try:
        max_words = int(cap.get("max_words", 3))
    except (ValueError, TypeError):
        raise PlanError(f"{p}: captions \"max_words\" must be an int")
    key_list = cap.get("key")
    if key_list is not None and not isinstance(key_list, list):
        raise PlanError(f"{p}: captions \"key\" must be a list")
    captions = {"key": [str(k).upper() for k in key_list or []], "max_words": max_words}
    music = raw.get("music")
    if music is not None:
        v = music.get("volume") if isinstance(music, dict) else None
        if (not isinstance(music, dict) or not ({"volume", "src"} & music.keys()) or ("volume" in music and (isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 2))
                or ("src" in music and not isinstance(music["src"], str))):
            raise PlanError(f"{p}: \"music\" must be an object with an optional numeric \"volume\" (0–2) and an optional string \"src\"")
    return Plan(gs, captions, music, end, warnings, chapters, face, fmt, tr, panel, layout)
