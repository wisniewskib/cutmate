"""HyperFrames CLI access (pinned version, Windows-safe npx path)."""
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import CutmateError
from .media import run

HF_VERSION = "0.8.157"
CHECK_TIMEOUT_MS = 30000  # how long `check` waits for the page to become render-ready (hyperframes default: 3000)
DEADLINE = "did not finish within its deadline"  # hyperframes' fixed 120 s limit on the whole browser pass
DEADLINE_WARN = "WARN hyperframes check ran out of time (busy/slow machine) — rendering anyway"


@dataclass
class CheckResult:
    status: str        # "ok" | "deadline" (cut off by the 120 s limit twice: a busy machine) | "failed"
    output: str = ""   # stdout + stderr of the last run


def npx() -> str:
    p = shutil.which("npx")
    if not p:
        raise CutmateError("npx not found (Node.js ≥ 22 needed). Run /cutmate:setup.")
    return p


def hf(*args) -> list[str]:
    return [npx(), "--yes", f"hyperframes@{HF_VERSION}", *[str(a) for a in args]]


def check(proj: Path, runner=run, cli=hf) -> CheckResult:
    """`hyperframes check` with a generous render-ready wait. A run cut off by hyperframes' fixed 120 s deadline (a busy
    or slow machine, not a broken composition) is retried once; a second cut-off returns status "deadline" — callers warn
    (DEADLINE_WARN) and go on. A script that hangs is reported by hyperframes differently and comes back as "failed"."""
    for _ in range(2):
        r = runner(cli("check", "--timeout", str(CHECK_TIMEOUT_MS)), cwd=proj)
        output = r.stdout + r.stderr
        if not r.returncode:
            return CheckResult("ok", output)
        if DEADLINE not in output:
            return CheckResult("failed", output)
    return CheckResult("deadline", output)


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
