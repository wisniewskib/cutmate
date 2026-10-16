"""HyperFrames CLI access (pinned version, Windows-safe npx path)."""
import os
import shutil
from pathlib import Path

from .errors import CutmateError
from .media import run

HF_VERSION = "0.8.157"


def npx() -> str:
    p = shutil.which("npx")
    if not p:
        raise CutmateError("npx not found (Node.js ≥ 22 needed). Run /cutmate:setup.")
    return p


def hf(*args) -> list[str]:
    return [npx(), "--yes", f"hyperframes@{HF_VERSION}", *[str(a) for a in args]]


def ensure_project(proj: Path, fmt: str = "9:16") -> None:
    proj = Path(proj)
    if (proj / "hyperframes.json").exists():
        return
    proj.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    res = "landscape" if fmt == "16:9" else "portrait"
    tmp = proj.parent / f".cm-init-{proj.name}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        r = run(hf("init", tmp.name, "--non-interactive", "--example=blank", f"--resolution={res}"), cwd=proj.parent, env=env)
        if r.returncode or not (tmp / "hyperframes.json").exists():
            tail = " ".join((r.stdout + r.stderr).split())[-300:]
            raise CutmateError(f"hyperframes init failed in {proj.parent}: {tail}")
        _merge(tmp, proj)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _merge(src: Path, dst: Path) -> None:
    """Move src's entries into dst, never overwriting existing files."""
    dst.mkdir(parents=True, exist_ok=True)
    for e in src.iterdir():
        t = dst / e.name
        if e.is_dir() and t.is_dir():
            _merge(e, t)
        elif not t.exists():
            shutil.move(str(e), str(t))
