"""Theme store: drafts, list/use, and the save gate (a draft must carry a fresh check stamp)."""
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import time
from pathlib import Path

from . import config
from .directions import CLEAN, palette_of, roll, suggest_name  # noqa: F401  (palette_of: used by the CLI)
from .effects import THEME_RE
from .errors import CutmateError
from .hf import HF_VERSION
from .paths import plugin_root, theme_dir

STAMP_FORMATS = ["9:16", "16:9"]


def _themes_root() -> Path:
    return config.home() / "themes"


def draft_dir(name: str) -> Path:
    return _themes_root() / ".drafts" / name


def _bundled_names() -> list[str]:
    root = plugin_root() / "themes"
    return sorted(d.name for d in root.iterdir() if (d / "theme.json").exists()) if root.is_dir() else []


def check_name(name: str) -> None:
    if not THEME_RE.match(str(name)):
        raise CutmateError(f"bad theme name {name!r}: letters, digits, _ and - only")
    if name in _bundled_names():
        raise CutmateError(f"theme name {name!r} is reserved (bundled theme) — pick another")


def resolve(name: str) -> tuple[Path, str]:
    if THEME_RE.match(str(name)) and (draft_dir(name) / "theme.json").exists():
        return draft_dir(name), "draft"
    d = theme_dir(name)
    return d, ("bundled" if d.is_relative_to(plugin_root() / "themes") else "user")


def _rm_onerror(func, path, exc):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        func(path)
    except OSError:
        pass


def _rmtree(path: Path) -> None:
    if not Path(path).exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=lambda f, p, e: _rm_onerror(f, p, e))
    else:
        shutil.rmtree(path, onerror=lambda f, p, e: _rm_onerror(f, p, e))


def _read_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise CutmateError(f"{path}: cannot read ({' '.join(str(e).split())})") from None


def _direction_of(name: str) -> dict:
    d = _read_json(resolve(name)[0] / "theme.json").get("direction")
    return d if isinstance(d, dict) else {}


def _all_names() -> set[str]:
    return {t["name"] for t in list_themes()}


def new_theme(name: str | None, base: str = "clean", mode: str = "custom", seed: int | None = None,
              avoid: list[str] = ()) -> dict:
    if mode not in ("custom", "random", "clone"):
        raise CutmateError(f"unknown mode {mode!r} (custom, random or clone)")
    if mode == "random":
        seed = secrets.randbelow(1_000_000) if seed is None else seed
        direction = roll(seed, [_direction_of(a) for a in avoid])
        if name is None:
            name = suggest_name(direction, _all_names())
    else:
        direction = {"mode": mode}
        if name is None:
            raise CutmateError("a theme name is required (only --mode random can suggest one)")
    check_name(name)
    src, _ = resolve(base)
    dst = draft_dir(name)
    _rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("check"))
    _rmtree(dst / "components" / "custom")
    old = dst / "fonts" / "OFL.txt"
    if old.exists():
        old.replace(dst / "fonts" / "OFL-inter.txt")
    tj = _read_json(dst / "theme.json")
    tj.update({"name": name, "base": base, "direction": direction})
    (dst / "theme.json").write_text(json.dumps(tj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    frame = dst / "frame.md"
    if frame.exists():
        text = frame.read_text(encoding="utf-8")
        head, sep, rest = text.partition("\n---\n")
        if text.startswith("---") and sep:
            head = re.sub(r"(?m)^name:.*$", f"name: {name}", head, count=1)
            frame.write_text(head + sep + rest, encoding="utf-8")
    return {"name": name, "path": str(dst), "direction": direction,
            "exists": (_themes_root() / name / "theme.json").exists()}


def theme_hash(path: Path) -> str:
    path = Path(path)
    files = [path / n for n in ("theme.json", "tokens.css", "theme.css", "frame.md")]
    files += sorted((path / "components").glob("*.html"))
    files += sorted(p for p in (path / "fonts").glob("*") if p.is_file())
    h = hashlib.sha256()
    for f in sorted({f for f in files if f.is_file()}, key=lambda f: f.relative_to(path).as_posix()):
        h.update(f.relative_to(path).as_posix().encode("utf-8") + b"\0")
        h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def write_stamp(path: Path) -> None:
    stamp = Path(path) / "check" / "check.json"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps({"hash": theme_hash(path), "hyperframes": HF_VERSION, "formats": STAMP_FORMATS}),
                     encoding="utf-8")


def stamp_ok(path: Path) -> bool:
    stamp = Path(path) / "check" / "check.json"
    try:
        s = json.loads(stamp.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return isinstance(s, dict) and s.get("hash") == theme_hash(path)


def _mode_of(path: Path) -> str | None:
    try:
        d = json.loads((Path(path) / "theme.json").read_text(encoding="utf-8")).get("direction")
    except (ValueError, OSError):
        return None
    return d.get("mode") if isinstance(d, dict) else None


def list_themes() -> list[dict]:
    out = []
    bundled = plugin_root() / "themes"
    if bundled.is_dir():
        for d in sorted(bundled.iterdir()):
            if (d / "theme.json").exists():
                out.append({"name": d.name, "kind": "bundled", "path": str(d), "checked": None, "mode": _mode_of(d)})
    root = _themes_root()
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if not d.name.startswith(".") and (d / "theme.json").exists():
                out.append({"name": d.name, "kind": "user", "path": str(d), "checked": stamp_ok(d), "mode": _mode_of(d)})
        drafts = root / ".drafts"
        if drafts.is_dir():
            for d in sorted(drafts.iterdir()):
                if (d / "theme.json").exists():
                    out.append({"name": d.name, "kind": "draft", "path": str(d), "checked": stamp_ok(d),
                                "mode": _mode_of(d)})
    return out


def use_theme(name: str) -> None:
    config.set_values([f"theme={name}"])


def save_theme(name: str, force: bool = False) -> Path:
    if not THEME_RE.match(str(name)):
        raise CutmateError(f"bad theme name {name!r}: letters, digits, _ and - only")
    draft = draft_dir(name)
    if not (draft / "theme.json").exists():
        raise CutmateError(f"no draft {name!r} — run `cutmate theme new {name}` first")
    if not stamp_ok(draft):
        raise CutmateError(f"draft {name!r} changed since its last check (or was never checked) — "
                           f"run `cutmate theme check {name}`")
    target = _themes_root() / name
    if (target / "theme.json").exists():
        if not force:
            raise CutmateError(f"theme {name!r} already exists — ask the user, then `cutmate theme save {name} --force` "
                               "(the old one is kept in themes/.backup)")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = _themes_root() / ".backup" / f"{name}-{stamp}"
        n = 1
        while backup.exists():
            n += 1
            backup = _themes_root() / ".backup" / f"{name}-{stamp}-{n}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup)
    if target.exists():  # keep only components/custom (effects saved by `save-effect`)
        for child in list(target.iterdir()):
            if child.name == "components":
                for sub in list(child.iterdir()):
                    if sub.name != "custom":
                        _rmtree(sub) if sub.is_dir() else sub.unlink()
            elif child.is_dir():
                _rmtree(child)
            else:
                child.unlink()
    shutil.copytree(draft, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("custom"))
    _rmtree(draft)
    return target
