"""Where cutmate's bundled files live: the plugin/repo root holds assets/, themes/ and core/."""
from pathlib import Path

from .config import home
from .errors import CutmateError

_ROOT = Path(__file__).resolve().parents[2]


def plugin_root() -> Path:
    return _ROOT


def assets_dir() -> Path:
    return _ROOT / "assets"


def web_dir() -> Path:
    return _ROOT / "core" / "cutmate" / "web"


def theme_dir(name: str) -> Path:
    places = [home() / "themes" / name, _ROOT / "themes" / name]
    for d in places:
        if (d / "theme.json").exists():
            return d
    raise CutmateError(f"theme {name!r} not found (looked in {places[0]} and {places[1]})")
