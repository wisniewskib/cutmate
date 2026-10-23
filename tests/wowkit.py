"""WOW pack test kit (hf tests of Tasks 3–6): build a fake recording with a plan, snapshot it, prove seek-safety, and tile
a contact sheet to READ.

    proj = project(tmp_path, {"scenes": [{"from": 0.5, "to": 4.5, "effect": "kinetic-word", "params": {...}}]})
    assert seek_safe(proj, 2.0) <= 1.0              # Review Focus 1: frame T alone == frame T after other frames
    sheet = strip(proj, 0.5, 4.5)                   # then look at it (Read the PNG) before committing

Every HyperFrames call is `hyperframes@<hf.HF_VERSION>` through npx (pinned), paths are pathlib, files UTF-8."""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_clip  # noqa: E402
from test_build import TIMED, WORDS  # noqa: E402

from cutmate import build as B  # noqa: E402
from cutmate.formats import size_of  # noqa: E402
from cutmate.hf import hf  # noqa: E402
from cutmate.media import run  # noqa: E402
from cutmate.sheet import contact_sheet  # noqa: E402


def project(tmp_path: Path, plan: dict, fmt: str = "9:16", dur: float = 6.0, theme: str = "clean",
            tracks: dict | None = None) -> Path:
    """A built composition (out/composition) for `plan` over a synthetic `dur`-second A-roll (testsrc2) with test_build's
    words; segment S2 runs to `dur`. `tracks`: the tracks.json content ({"tracks": {...}} or just the tracks dict,
    samples [t, x, y, ...] in 0–1 frame units), written after the A-roll so it is fresh."""
    if dur < TIMED[-1]["end"]:
        raise ValueError(f"dur must be >= {TIMED[-1]['end']} s (the test words run to it)")
    W, H = size_of(fmt)
    out = Path(tmp_path) / "rec" / "out"
    (out / "work").mkdir(parents=True, exist_ok=True)
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
    d = proj / "wowkit-snaps" / "_".join(_key(t) for t in times)[:120].replace(".", "p")
    shutil.rmtree(d, ignore_errors=True)
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


def diff(a: Path, b: Path) -> float:
    """Mean absolute RGB difference (0–255) of two PNGs."""
    with Image.open(a) as ia, Image.open(b) as ib:
        x, y = ia.convert("RGB"), ib.convert("RGB")
        if x.size != y.size:
            raise AssertionError(f"{a.name} is {x.size}, {b.name} is {y.size}")
        return sum(ImageStat.Stat(ImageChops.difference(x, y)).mean) / 3


def seek_safe(proj: Path, t: float, before: tuple = (0.3,)) -> float:
    """Review Focus 1 (a render worker starts mid-effect): mean abs RGB diff between frame `t` captured alone and after
    seeking to `before` first. A seek-safe effect gives ~0 (assert <= 1.0). Pass a `before` later than `t` too (a scrub
    backwards), e.g. seek_safe(proj, 2.0, (0.3, 3.5))."""
    return diff(snap(proj, t), snap(proj, t, tuple(before)))


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
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", f"{1 / step:.6f}", "-i", Path(td) / "s%05d.png",
                 "-vf", f"scale=480:-2,tpad=start_duration={a:.3f}:start_mode=clone:stop_duration={step:.3f}"
                        f":stop_mode=clone,fps={2 / step:.6f}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
        if r.returncode:
            raise AssertionError("ffmpeg (strip): " + r.stderr[-800:])
        sheets = contact_sheet(video, out_png, start=a, end=a + (n - 0.5) * step, step=step)
    return sheets[0]
