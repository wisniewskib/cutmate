"""`cutmate requests`: match the "zrozumiałem tak" list (out/requests.md) against the plan."""
import re
from pathlib import Path

from .errors import CutmateError

_LINE = re.compile(
    r"^- \[(?P<source>[^\]]+)\]\s*(?P<what>.*?)\s*→\s*(?P<target>[a-z0-9:-]+)"
    r"(?:\s*@\s*(?P<anchor>\S+))?\s*$")
_NOTES = ("cut", "skip")


def parse_requests(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        m = _LINE.match(line)
        if not m:
            out.append({"error": f"cannot parse: {line.strip()}"})
            continue
        out.append({k: m.group(k) for k in ("source", "what", "target", "anchor")})
    return out


def _range(anchor, timed: list[dict], words: list[dict], end: float) -> tuple[float, float]:
    from .plan import resolve_anchor
    if ":" in anchor:
        t = resolve_anchor(anchor, words, end)[0]
        return t - 1.0, t + 1.0
    for s in timed:
        if s["id"] == anchor:
            return float(s["start"]), float(s["end"])
    raise CutmateError(f"requests: no segment {anchor!r}")


def check_requests(out_dir: Path) -> list[str]:
    import json
    out = Path(out_dir)
    path = out / "requests.md"
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise CutmateError(f"{path}: cannot read ({e})") from None
    reqs = parse_requests(text)
    if not reqs:
        return []
    from .cut import load_timed
    from .plan import load_plan
    plan = load_plan(out)
    timed = load_timed(out)
    try:
        words = json.loads((out / "work" / "aligned_words.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CutmateError(f"{out / 'work' / 'aligned_words.json'}: unreadable ({e})") from None
    end = float(timed[-1]["end"]) if timed else 0.0
    lines = []
    for r in reqs:
        if "error" in r:
            lines.append(f"BAD  {r['error']}")
            continue
        label = f"[{r['source']}] {r['what']} → {r['target']}" + (f" @ {r['anchor']}" if r["anchor"] else "")
        if r["target"] in _NOTES:
            lines.append(f"NOTE {label}")
            continue
        if not r["anchor"]:
            lines.append(f"BAD  {label} (no anchor)")
            continue
        try:
            lo, hi = _range(r["anchor"], timed, words, end)
        except CutmateError as e:
            lines.append(f"BAD  {label} ({' '.join(str(e).split())})")
            continue
        found = any((g.type == r["target"] or r["target"] == f"custom:{g.params.get('name')}")
                    and lo <= g.start <= hi for g in plan.graphics)
        lines.append((f"OK   {label}" if found else f"MISSING {label}"))
    return lines
