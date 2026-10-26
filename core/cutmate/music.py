"""Music bed: loop/trim to the short, -14 LUFS (same as the voice, so data-volume means the same everywhere),
baked fades; optional HyperFrames voice carve so the bed ducks under speech."""
import glob
import os
import re
import shutil
from pathlib import Path

from .errors import CutmateError
from .hf import HF_VERSION
from .media import run

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"}


def pick_source(plan_music: dict | None, cfg_music: dict | None, rec: Path) -> Path | None:
    if plan_music and plan_music.get("src"):
        p = Path(str(plan_music["src"]))
        p = p if p.is_absolute() else Path(rec) / p
        if not p.exists():
            raise CutmateError(f"music not found: {p}")
        return p
    if cfg_music and cfg_music.get("source") == "folder" and cfg_music.get("folder"):
        folder = Path(cfg_music["folder"]).expanduser()
        files = sorted(f for f in folder.glob("*") if f.suffix.lower() in AUDIO_EXTS) if folder.is_dir() else []
        if not files:
            raise CutmateError(f"no music files (.mp3 .m4a .wav .ogg .flac) in {folder} — run /cutmate:setup")
        return files[0]
    return None


def prepare_music(src: Path, dst: Path, end: float) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fo = min(1.8, end / 3)
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{end:.3f}",
             "-af", f"loudnorm=I=-14:TP=-2:LRA=11,afade=t=in:d=0.8,afade=t=out:st={end - fo:.3f}:d={fo:.3f},aresample=48000",
             "-ac", "2", "-c:a", "aac", "-b:a", "192k", dst])
    if r.returncode:
        raise CutmateError(f"cannot prepare music {src}: {' '.join(r.stderr.split())[-300:]}")
    return dst


def _carve_script() -> str | None:
    # cache/<marketplace>/hyperframes/<version>/: from cutmate's own marketplace or HeyGen's; newer HyperFrames
    # moved the script from hyperframes-audio/ to media-use/audio/
    base = os.path.expanduser("~/.claude/plugins/cache/*/hyperframes/*/skills/")
    hits = glob.glob(base + "hyperframes-audio/scripts/carve.mjs") + glob.glob(base + "media-use/audio/scripts/carve.mjs")
    def version(p: str) -> tuple:
        m = re.search(r"/hyperframes/(\d+)\.(\d+)\.(\d+)/", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    # the copy matching the pinned core first, it is the one cutmate is tested with
    pinned = [p for p in hits if f"/hyperframes/{HF_VERSION}/" in p]
    hits = sorted(pinned or hits, key=lambda p: (version(p), p))
    return hits[-1] if hits else None


def carve(project: Path, strength: float = 0.3) -> bool:
    script = _carve_script()
    if not script or not shutil.which("node") or not shutil.which("npm"):
        print("WARN music: voice carve unavailable (HyperFrames audio skill not found) — bed kept at a plain level")
        return False
    project = Path(project)
    if not (project / "node_modules" / "@hyperframes" / "core").exists():
        r = run([shutil.which("npm"), "i", "-D", "--silent", f"@hyperframes/core@{HF_VERSION}"], cwd=project)
        if r.returncode:
            print("WARN music: could not install @hyperframes/core — bed kept at a plain level")
            return False
    r = run([shutil.which("node"), script, "--comp", "index.html", "--bed", "music-bed", "--voice", "aroll",
             "--strength", str(strength)], cwd=project)
    if r.returncode:
        print("WARN music: carve failed — bed kept at a plain level: " + " ".join(r.stderr.split())[-200:])
        return False
    return True
