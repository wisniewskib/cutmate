import json
from pathlib import Path

from .errors import CutmateError

FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080)}


def size_of(fmt: str) -> tuple[int, int]:
    try:
        return FORMATS[fmt]
    except KeyError:
        raise CutmateError(f"unknown format {fmt!r}; use 9:16 or 16:9") from None


def aspect(width: int, height: int) -> str:
    return "16:9" if width > height else "9:16"


def format_of(out_dir: Path) -> str:
    """The project's format: "format" in out/edl.json, 9:16 when there is no EDL yet."""
    p = Path(out_dir) / "edl.json"
    if not p.exists():
        return "9:16"
    try:
        fmt = json.loads(p.read_text(encoding="utf-8")).get("format", "9:16")
    except (ValueError, OSError, AttributeError):
        raise CutmateError(f"{p}: cannot read the format — fix the JSON") from None
    size_of(fmt)
    return fmt
