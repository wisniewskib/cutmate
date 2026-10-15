"""Render the HyperFrames project: check → render (progress streamed) → finalize (-14 LUFS, spec check, frames)."""
import json
import subprocess
from pathlib import Path

from .errors import CutmateError
from .finalize import finalize
from .formats import format_of
from .hf import hf
from .media import run


def _stream(cmd: list[str], cwd: Path) -> int:
    """Run with output going straight to the terminal so HyperFrames' progress bar is visible."""
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def render(out_dir: Path) -> dict:
    out = Path(out_dir).resolve()
    proj = out / "composition"
    if not (proj / "index.html").exists():
        raise CutmateError(f"{proj / 'index.html'} not found — run `cutmate build` first")
    chk = run(hf("check"), cwd=proj)
    if chk.returncode:
        raise CutmateError("hyperframes check failed: " + " ".join((chk.stdout + chk.stderr).split())[-500:])
    dst = out / "work" / "render.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.unlink(missing_ok=True)
    for old in out.glob("check_*.png"):
        old.unlink()
    cmd = hf("render", "--fps", "30", "--quality", "delivery", "--format", "mp4", "-o", "../work/render.mp4")
    code = _stream(cmd, proj)
    if code or not dst.exists():
        raise CutmateError(f"hyperframes render failed (exit {code}) — rerun in {proj}: {' '.join(cmd)}")
    cp = out / "work" / "checkpoints.json"
    try:
        checkpoints = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else []
    except ValueError:
        raise CutmateError(f"malformed checkpoints.json in {cp}")
    return finalize(dst, out / "final.mp4", format_of(out), check=checkpoints)
