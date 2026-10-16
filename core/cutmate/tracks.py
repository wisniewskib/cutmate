"""Where the speaker's face and hands are over time (out/work/tracks.json), so effects can follow them.

Samples are [t, x, y, conf] with x, y as fractions of the frame; t is A-roll seconds."""
import json
from pathlib import Path
from statistics import median

from .errors import CutmateError

TRACKS = ("face", "hand_left", "hand_right")


def smooth(samples: list[list[float]], k: int = 5) -> list[list[float]]:
    h = k // 2
    out = []
    for i, (t, _, _, c) in enumerate(samples):
        win = samples[max(0, i - h): i + h + 1]
        out.append([t, median(p[1] for p in win), median(p[2] for p in win), c])
    return out


def fill_gaps(samples: list[list[float]], max_gap: float = 0.5, step: float = 1 / 15) -> list[list[float]]:
    out = []
    for a, b in zip(samples, samples[1:]):
        out.append(a)
        gap = b[0] - a[0]
        if step * 1.5 < gap <= max_gap + 1e-9:
            n = round(gap / step)
            for j in range(1, n):
                f = j / n
                out.append([round(a[0] + gap * f, 4), a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 0.0])
    if samples:
        out.append(samples[-1])
    return out


def _in(samples, a, b):
    return [p for p in samples if a <= p[0] <= b]


def pick_hand(tracks: dict, a: float, b: float) -> str:
    left = len(_in(tracks.get("hand_left", []), a, b))
    right = len(_in(tracks.get("hand_right", []), a, b))
    return "hand_left" if left > right else "hand_right"


def face_median(tracks: dict, a: float, b: float) -> list[float] | None:
    s = _in(tracks.get("face", []), a, b)
    if not s:
        return None
    return [round(median(p[1] for p in s), 3), round(median(p[2] for p in s), 3)]


def load_tracks(out_dir: Path) -> dict | None:
    p = Path(out_dir) / "work" / "tracks.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise CutmateError(f"{p}: broken file — run `cutmate track` again") from None


def save_tracks(out_dir: Path, data: dict) -> Path:
    p = Path(out_dir) / "work" / "tracks.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(p)
    return p
