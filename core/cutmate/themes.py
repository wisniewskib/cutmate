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


_DEVICE_RE = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE)


def check_name(name: str) -> None:
    if not THEME_RE.match(str(name)) or str(name).endswith((".", " ")):
        raise CutmateError(f"bad theme name {name!r}: letters, digits, _ and - only")
    if _DEVICE_RE.match(name):
        raise CutmateError(f"theme name {name!r} is a reserved system name — pick another")
    if name.lower() in (b.lower() for b in _bundled_names()):
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
    path = Path(path)
    if not path.exists():
        return
    cause = None
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=lambda f, p, e: _rm_onerror(f, p, e))
        else:
            shutil.rmtree(path, onerror=lambda f, p, e: _rm_onerror(f, p, e))
    except OSError as e:
        cause = e
    if path.exists():
        why = " ".join(str(cause).split()) if cause else "still there after delete"
        raise CutmateError(f"cannot delete {path} ({why}) — close programs using it and retry")


def _ignoring(root: Path, rel: str, name: str):
    """shutil ignore callback: skip only `<root>/<rel>/<name>`, nothing deeper or elsewhere."""
    here = Path(root) / rel

    def ignore(d, names):
        return {name} if Path(d) == here and name in names else set()
    return ignore


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
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / f".{name}.new-{time.strftime('%Y%m%d-%H%M%S')}"
    _rmtree(tmp)
    try:
        shutil.copytree(src, tmp, ignore=_ignoring(src, "", "check"))
        _rmtree(tmp / "components" / "custom")
        old = tmp / "fonts" / "OFL.txt"
        if old.exists():
            old.replace(tmp / "fonts" / "OFL-inter.txt")
        tj = _read_json(tmp / "theme.json")
        tj.update({"name": name, "base": base, "direction": direction})
        (tmp / "theme.json").write_text(json.dumps(tj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        frame = tmp / "frame.md"
        if frame.exists():
            text = frame.read_text(encoding="utf-8")
            head, sep, rest = text.partition("\n---\n")
            if text.startswith("---") and sep:
                head = re.sub(r"(?m)^name:.*$", f"name: {name}", head, count=1)
                frame.write_text(head + sep + rest, encoding="utf-8")
        _rmtree(dst)
        os.replace(tmp, dst)
    except BaseException:
        try:
            _rmtree(tmp)
        except CutmateError:
            pass
        raise
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
    return isinstance(s, dict) and s.get("hash") == theme_hash(path) and s.get("hyperframes") == HF_VERSION


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
                if not d.name.startswith(".") and (d / "theme.json").exists():
                    out.append({"name": d.name, "kind": "draft", "path": str(d), "checked": stamp_ok(d),
                                "mode": _mode_of(d)})
    return out


def use_theme(name: str) -> None:
    if not THEME_RE.match(str(name)):
        raise CutmateError(f"bad theme name {name!r}: letters, digits, _ and - only")
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
    root = _themes_root()
    target = root / name
    has_other = target.exists() and _has_other(target)
    if has_other and not force:
        raise CutmateError(f"theme {name!r} already exists — ask the user, then `cutmate theme save {name} --force` "
                           "(the old one is kept in themes/.backup)")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tmp = root / f".{name}.saving-{stamp}"
    old_dest = tmp.with_name(f".{name}.old-{stamp}")
    if has_other:
        old_dest = root / ".backup" / f"{name}-{stamp}"
        n = 1
        while old_dest.exists():
            n += 1
            old_dest = root / ".backup" / f"{name}-{stamp}-{n}"
    _rmtree(tmp)
    moved = False
    try:
        shutil.copytree(draft, tmp, ignore=_ignoring(draft, "components", "custom"))
        if (target / "components" / "custom").is_dir():
            shutil.copytree(target / "components" / "custom", tmp / "components" / "custom")
        if not (tmp / "theme.json").exists() or theme_hash(tmp) != theme_hash(draft):
            raise CutmateError("copy of the draft does not match the draft")
        if target.exists():
            old_dest.parent.mkdir(parents=True, exist_ok=True)
            os.rename(target, old_dest)
            moved = True
        os.replace(tmp, target)
    except BaseException as e:
        if moved and not target.exists():
            try:
                os.rename(old_dest, target)
            except OSError:
                pass
        try:
            _rmtree(tmp)
        except CutmateError:
            pass
        where = f" (the old theme is in {old_dest})" if moved else ""
        if isinstance(e, Exception):
            raise CutmateError(f"saving theme {name!r} failed: {' '.join(str(e).split())}{where}") from None
        raise
    for leftover in ((draft,) if has_other else (draft, old_dest)):
        try:
            _rmtree(leftover)
        except CutmateError:
            pass
    return target


def _has_other(target: Path) -> bool:
    for child in target.iterdir():
        if child.name != "components":
            return True
        if child.is_dir() and any(c.name != "custom" for c in child.iterdir()):
            return True
    return False
