"""plan.json — which graphic appears on which spoken word.

Anchors: "S2:word" (first occurrence in segment S2), "S2:word#2" (second), or a number (A-roll seconds).
Times resolve against out/work/aligned_words.json, so re-cutting moves every graphic with its word.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .cut import load_timed
from .errors import PlanError

TYPES = ("title", "counter", "list", "chip", "stamp", "bars", "point", "split")
REQUIRED = {"title": ("at", "text"), "counter": ("at", "to", "label"), "list": ("items",), "chip": ("at", "text"),
            "stamp": ("at", "text"), "bars": ("at", "head", "rows"), "point": ("at", "image", "corner"),
            "split": ("from", "to", "media")}
TIMING_KEYS = ("type", "at", "from", "until", "hit", "sfx")
CORNERS = ("tl", "tr", "bl", "br")
HOLD = 2.5
_PUNCT = ".,!?;:…\"'„""()[]–—-"


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


def norm(word: str) -> str:
    return str(word).strip().strip(_PUNCT).lower()


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


def _graphic(i: int, g, words: list[dict], end: float, rec: Path) -> Graphic:
    where = f"graphic #{i + 1}"
    if not isinstance(g, dict) or "type" not in g:
        raise PlanError(f"{where}: must be an object with a \"type\"")
    t = g["type"]
    if t not in TYPES:
        raise PlanError(f"{where}: unknown type {t!r} (use {', '.join(TYPES)})")
    where = f"graphic #{i + 1} ({t})"
    for k in REQUIRED[t]:
        if k not in g:
            raise PlanError(f"{where}: missing \"{k}\"")
    params = {k: v for k, v in g.items() if k not in TIMING_KEYS}
    stop = None
    if t == "split":
        start = resolve_anchor(g["from"], words, end)[0]
        stop = resolve_anchor(g["to"], words, end)[1]
        params["media"] = _media(g["media"], rec, where)
    elif t == "list":
        if not isinstance(g["items"], list) or not g["items"]:
            raise PlanError(f"{where}: \"items\" must be a non-empty list")
        items = []
        for j, it in enumerate(g["items"]):
            if not isinstance(it, dict) or "text" not in it or "at" not in it:
                raise PlanError(f"{where}: item {j + 1} needs \"text\" and \"at\"")
            items.append({"text": str(it["text"]), "at": resolve_anchor(it["at"], words, end)[0]})
        params["items"] = items
        start = min(x["at"] for x in items)
        stop = max(x["at"] for x in items) + HOLD
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
        if not isinstance(rows, list) or not rows or any(
                not isinstance(r, dict) or "label" not in r or isinstance(r.get("value"), bool)
                or not isinstance(r.get("value"), (int, float)) for r in rows):
            raise PlanError(f"{where}: \"rows\" must be a list of {{\"label\", \"value\": number}}")
        params["illustrative"] = bool(g.get("illustrative", False))
    for k in ("logo", "icon"):
        if g.get(k):
            params[k] = _media(g[k], rec, where)
    if "until" in g:
        stop = resolve_anchor(g["until"], words, end)[1]
        if stop <= start:
            raise PlanError(f"{where}: \"until\" is before \"at\"")
    return Graphic(t, round(start, 3), stop, params, bool(g.get("hit", False)), g.get("sfx"), i)


def _budget(gs: list[Graphic]) -> list[str]:
    w = []
    hits = [g for g in gs if g.hit]
    if len(hits) > 2:
        w.append(f"WARN {len(hits)} graphics with \"hit\" (budget 2) at " + ", ".join(f"{g.start:.1f}s" for g in hits))
    titles = [g for g in gs if g.type == "title"]
    if len(titles) > 1:
        w.append(f"WARN {len(titles)} titles (budget 1)")
    for a, b in zip(gs, gs[1:]):
        if b.start < a.end:
            w.append(f"WARN {a.type} ({a.start:.1f}–{a.end:.1f}s) overlaps {b.type} at {b.start:.1f}s")
    return w


def _fmt(n) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _factcheck(out: Path, gs: list[Graphic]) -> list[str]:
    f = out / "factcheck.md"
    ok = [line for line in f.read_text(encoding="utf-8").splitlines() if "✅" in line] if f.exists() else []
    w = []
    for g in gs:
        if g.type == "counter":
            nums = [g.params["to"]]
        elif g.type == "bars" and not g.params.get("illustrative"):
            nums = [r["value"] for r in g.params["rows"]]
        else:
            nums = []
        for n in nums:
            s = _fmt(n)
            if not any(s in line for line in ok):
                w.append(f"WARN {g.type} at {g.start:.1f}s shows {s}, which no ✅ line in factcheck.md confirms")
    return w


def load_plan(out_dir: Path, factcheck: bool = False) -> Plan:
    out = Path(out_dir)
    p = out / "plan.json"
    if not p.exists():
        raise PlanError(f"{p} not found — write the plan first")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlanError(f"{p}: invalid JSON ({e.msg}, line {e.lineno})") from None
    if not isinstance(raw, dict):
        raise PlanError(f"{p}: must be a JSON object")
    words_p = out / "work" / "aligned_words.json"
    if not words_p.exists():
        raise PlanError(f"{words_p} not found — run `cutmate align` first")
    words = json.loads(words_p.read_text(encoding="utf-8"))
    end = float(load_timed(out)[-1]["end"])
    gs = sorted((_graphic(i, g, words, end, out.parent) for i, g in enumerate(raw.get("graphics") or [])),
                key=lambda g: g.start)
    for i, g in enumerate(gs):
        if g.end is None:
            nxt = gs[i + 1].start - 0.05 if i + 1 < len(gs) else end
            g.end = min(g.start + HOLD, nxt)
        g.end = round(max(min(g.end, end - 0.05), min(g.start + 0.3, end - 0.05)), 3)
        if g.end <= g.start:
            raise PlanError(f"graphic #{g.index + 1} ({g.type}) starts at {g.start:.2f}s, too close to the end ({end:.2f}s)")
    warnings = _budget(gs) + (_factcheck(out, gs) if factcheck else [])
    cap = raw.get("captions") or {}
    captions = {"key": [str(k).upper() for k in cap.get("key", [])], "max_words": int(cap.get("max_words", 3))}
    music = raw.get("music") if isinstance(raw.get("music"), dict) else None
    return Plan(gs, captions, music, end, warnings)
