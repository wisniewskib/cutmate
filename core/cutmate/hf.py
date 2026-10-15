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
    r = run(hf("init", proj.name, "--non-interactive", "--example=blank", f"--resolution={res}"), cwd=proj.parent, env=env)
    if r.returncode or not (proj / "hyperframes.json").exists():
        tail = " ".join((r.stdout + r.stderr).split())[-300:]
        raise CutmateError(f"hyperframes init failed in {proj.parent}: {tail}")
