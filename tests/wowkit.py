"""WOW pack test kit (hf tests of Tasks 3–6): build a fake recording with a plan, snapshot it, prove seek-safety, and tile
a contact sheet to READ.

    proj = project(tmp_path, {"scenes": [{"from": 0.5, "to": 4.5, "effect": "kinetic-word", "params": {...}}]})
    assert seek_safe(proj, 2.0) <= 1.0              # Review Focus 1: frame T alone == frame T after an earlier
                                                    # and a later frame (worst 12x20 tile)
    sheet = strip(proj, 0.5, 4.5)                   # then look at it (Read the PNG) before committing

Every HyperFrames call is `hyperframes@<hf.HF_VERSION>` through npx (pinned), paths are pathlib, files UTF-8."""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_clip  # noqa: E402
from test_build import TIMED, WORDS  # noqa: E402

from cutmate import build as B  # noqa: E402
from cutmate.formats import size_of  # noqa: E402
from cutmate.hf import hf  # noqa: E402
from cutmate.media import run  # noqa: E402
from cutmate.sheet import contact_sheet  # noqa: E402


def project(tmp_path: Path, plan: dict, fmt: str = "9:16", dur: float = 6.0, theme: str = "clean",
            tracks: dict | None = None, aroll: Path | None = None) -> Path:
    """A built composition (out/composition) for `plan` over a synthetic `dur`-second A-roll (testsrc2) with test_build's
    words; segment S2 runs to `dur`. `tracks`: the tracks.json content ({"tracks": {...}} or just the tracks dict,
    samples [t, x, y, ...] in 0–1 frame units), written after the A-roll so it is fresh. `aroll`: an own A-roll file
    (`dur` s, the format's size) instead of the synthetic one."""
    if dur < TIMED[-1]["end"]:
        raise ValueError(f"dur must be >= {TIMED[-1]['end']} s (the test words run to it)")
    W, H = size_of(fmt)
    out = Path(tmp_path) / "rec" / "out"
    (out / "work").mkdir(parents=True, exist_ok=True)
    if aroll is not None:
        shutil.copyfile(aroll, out / "aroll.mp4")
    else:
        make_clip(out / "aroll.mp4", dur=dur, size=f"{W}x{H}", gaps=())
    timed = [dict(s) for s in TIMED]
    timed[-1]["end"] = float(dur)
    (out / "work" / "aligned_words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps(timed), encoding="utf-8")
    if fmt != "9:16":
        (out / "edl.json").write_text(json.dumps({"format": fmt, "segments": []}), encoding="utf-8")
    if tracks is not None:
        data = tracks if "tracks" in tracks else {"fps": 15, "w": W, "h": H, "tracks": tracks}
        (out / "work" / "tracks.json").write_text(json.dumps(data), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return Path(B.build(out, theme=theme)["project"])


def _key(t: float) -> str:
    return f"{t:.3f}".rstrip("0").rstrip(".")


def _shots(proj: Path, times: list[float]) -> list[Path]:
    """One `hyperframes snapshot` call capturing `times` in this order in ONE page (each seek follows the previous one);
    the PNGs in capture order."""
    proj = Path(proj)
    (proj / "wowkit-snaps").mkdir(exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="s-", dir=proj / "wowkit-snaps"))      # unique: parallel calls never share it
    at = ",".join(_key(t) for t in times)
    r = run(hf("snapshot", "--at", at, "--no-end", "--describe", "false", "-o", d), cwd=proj)
    pngs = sorted(d.glob("frame-*.png"), key=lambda p: int(re.match(r"frame-(\d+)", p.stem).group(1)))
    if r.returncode or len(pngs) != len(times):
        raise AssertionError(f"snapshot --at {at} gave {len(pngs)} PNGs (rc {r.returncode}): "
                             + " ".join((r.stdout + r.stderr).split())[-1500:])
    return pngs


def snap(proj: Path, t: float, before: tuple = ()) -> Path:
    """The frame at `t` (root timeline s), captured after first seeking to each of `before` in the same page."""
    return _shots(proj, [*before, t])[-1]


GRID = (12, 20)         # tiles across x down (9:16; swapped for 16:9): one tile (90x96 px) is ~0.4 % of the frame
HOT = 24                # a pixel "differs" when its mean abs RGB diff is above this


def diff_report(a: Path, b: Path) -> dict:
    """How two PNGs differ: `mean` (whole-frame mean abs RGB diff, 0–255), `tile` (the worst tile's mean on GRID — a
    wrong label or a stale word is ~0.5 % of a frame and vanishes in the mean, not in its tile) and `share` (fraction
    of pixels whose diff is above HOT)."""
    with Image.open(a) as ia, Image.open(b) as ib:
        x, y = ia.convert("RGB"), ib.convert("RGB")
    if x.size != y.size:
        raise AssertionError(f"{Path(a).name} is {x.size}, {Path(b).name} is {y.size}")
    d = np.abs(np.asarray(x, dtype=np.int16) - np.asarray(y, dtype=np.int16)).mean(axis=2)
    h, w = d.shape
    cols, rows = GRID if h >= w else GRID[::-1]
    ys, xs = np.linspace(0, h, rows + 1).astype(int), np.linspace(0, w, cols + 1).astype(int)
    tile = max(float(d[ys[r]:ys[r + 1], xs[c]:xs[c + 1]].mean()) for r in range(rows) for c in range(cols))
    return {"mean": float(d.mean()), "tile": tile, "share": float((d > HOT).mean())}


def diff(a: Path, b: Path) -> float:
    """Mean absolute RGB difference (0–255) of two PNGs (the whole frame)."""
    return diff_report(a, b)["mean"]


def duration(proj: Path) -> float:
    """The root composition's length (s), from index.html."""
    html = (Path(proj) / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<div id="root"[^>]*data-duration="([\d.]+)"', html)
    if not m:
        raise AssertionError(f"{proj}: no root data-duration in index.html")
    return float(m.group(1))


def default_before(t: float, end: float) -> tuple:
    """An earlier AND a later time: forward-only pre-seeks cannot catch state left behind by a backward scrub (GSAP
    renders a timeline's children last-to-first going backwards)."""
    later = min(t + 2.0, end - 0.05)
    if later <= t + 0.05:                              # t at the very end: scrub back from the end instead
        later = max(0.0, t - 1.0)
    return tuple(dict.fromkeys([round(min(0.3, max(0.0, t - 0.5)), 3), round(later, 3)]))


def seek_report(proj: Path, t: float, before: tuple | None = None) -> dict:
    """diff_report of frame `t` captured alone vs after the pre-seeks `before` (default: default_before) in one page,
    plus the `before` used."""
    before = default_before(t, duration(proj)) if before is None else tuple(before)
    return dict(diff_report(snap(proj, t), snap(proj, t, before)), before=before)


def seek_safe(proj: Path, t: float, before: tuple | None = None) -> float:
    """Review Focus 1 (a render worker starts mid-effect): the WORST TILE's mean abs RGB diff between frame `t` captured
    alone and after the pre-seeks `before` — by default an earlier time and a later one (a backward scrub). Seek-safe
    effects give 0.0 in practice; assert <= 1.0. (>= the whole-frame mean, so a small wrong label still fails.)"""
    return seek_report(proj, t, before)["tile"]


def strip(proj: Path, a: float, b: float, step: float = 0.25) -> Path:
    """A contact sheet (cutmate.sheet) of the frames a, a + step, … <= b, labelled with their root times — to READ."""
    proj = Path(proj)
    n = int((b - a) / step + 1e-9) + 1
    times = [round(a + i * step, 3) for i in range(n)]
    shots = _shots(proj, times)
    out_png = proj / "wowkit-strips" / f"strip-{_key(a)}-{_key(b)}.png".replace(":", "_")
    with tempfile.TemporaryDirectory() as td:
        for i, p in enumerate(shots):
            shutil.copyfile(p, Path(td) / f"s{i:05d}.png")
        video = Path(td) / "strip.mp4"
        # the stills at 1/step fps, padded with the first one from 0 s (and the last one after b), so the sheet's
        # time labels (start + i·step) are the root times
        r = run([shutil.which("ffmpeg") or "ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", f"{1 / step:.6f}", "-i", Path(td) / "s%05d.png",
                 "-vf", f"scale=480:-2,tpad=start_duration={a:.3f}:start_mode=clone:stop_duration={step:.3f}"
                        f":stop_mode=clone,fps={2 / step:.6f}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
        if r.returncode:
            raise AssertionError("ffmpeg (strip): " + r.stderr[-800:])
        sheets = contact_sheet(video, out_png, start=a, end=a + (n - 0.5) * step, step=step)
    return sheets[0]
