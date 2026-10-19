"""Theme store: drafts, list/use, and the save gate (a draft must carry a fresh check stamp)."""
import difflib
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
from .build import _SECTION, _sections, _theme_meta
from .directions import CLEAN, contrast, palette_of, roll, suggest_name  # noqa: F401  (palette_of: used by the CLI)
from .effects import FORBIDDEN, THEME_RE
from .errors import CutmateError
from .fonts import migrate_theme
from .hf import HF_VERSION
from .paths import assets_dir, plugin_root, theme_dir
from .plan import TYPES
from .theme_check import LOOK

STAMP_FORMATS = ["9:16", "16:9"]
REQUIRED_TOKENS = ("--accent", "--text", "--ink", "--muted", "--card", "--shadow", "--font", "--font-display")
FRAME_SELECTORS = ("#captions", ".cw", ".band")
COMPONENTS = tuple(t for t in TYPES if t != "custom") + ("chapter",)
DIRECTION_KEYS = ("palette", "fonts", "shapes", "motion", "captions")
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_NS = re.compile(r"https?://www\.w3\.org/[^\s\"'<>)]*")       # XML namespace strings are not fetched
_FETCH = re.compile(r"@import[^;{}]*?https?://|url\(\s*[\"']?https?://|\b(?:src|href)\s*=\s*[\"']?https?://"
                    r"|\b(?:fetch|import)\s*\(\s*[\"'`]?https?://")
_COMMENTS = re.compile(r"/\*.*?\*/|<!--.*?-->|(?<![:\w\"'])//[^\n]*", re.S)
LOOKS_CLEAN = "looks like clean with new colours — restyle the look components (shapes, motion) and set a display font"


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


def resolve(name: str, saved: bool = False) -> tuple[Path, str]:
    """The folder and kind of a theme name: a draft wins over a saved / bundled theme of the same name unless `saved`."""
    if not saved and THEME_RE.match(str(name)) and (draft_dir(name) / "theme.json").exists():
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
        migrate_theme(tmp)                                   # a pre-3b base: font blocks + --font-display
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


def write_stamp(path: Path, checked_hash: str | None = None) -> None:
    stamp = Path(path) / "check" / "check.json"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    h = checked_hash or theme_hash(path)
    stamp.write_text(json.dumps({"hash": h, "hyperframes": HF_VERSION, "formats": STAMP_FORMATS}),
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
    if not target.is_dir():
        raise CutmateError(f"{target} is a file, not a folder — move it away, then save again")
    for child in target.iterdir():
        if child.name != "components":
            return True
        if child.is_dir() and any(c.name != "custom" for c in child.iterdir()):
            return True
    return False


def _token(tokens: str, name: str) -> str | None:
    m = re.search(rf"(?<![\w-]){re.escape(name)}\s*:\s*([^;}}]+)", tokens)
    return m.group(1).strip() if m else None


def _norm(text: str) -> str:
    """Comments and all whitespace removed: what is left is the code a restyle has to change."""
    return "".join(_COMMENTS.sub("", text).split())


def _rgb(value: str) -> tuple[float, float, float, float] | None:
    v = value.strip()
    if _HEX.match(v):
        h = v[1:] if len(v) == 7 else "".join(c * 2 for c in v[1:])
        return (*(int(h[i:i + 2], 16) for i in (0, 2, 4)), 1.0)
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$", v)
    if not m:
        return None
    a = m.group(4)
    alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)), min(1.0, alpha))


def _solid(value: str | None, bg: str | None) -> str | None:
    """A #rrggbb for a hex / rgb() / rgba() colour, composited over `bg` (hex, else black); None if not a colour."""
    c = _rgb(value or "")
    if c is None:
        return None
    base = _rgb(bg or "") or (0, 0, 0, 1.0)
    mix = [round(c[i] * c[3] + base[i] * (1 - c[3])) for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*mix)


def _display_family(tokens: str) -> str | None:
    val = _token(tokens, "--font-display") or ""
    m = re.match(r"\s*var\(\s*(--[\w-]+)", val)
    if m:
        val = _token(tokens, m.group(1)) or ""
    fam = re.match(r"\s*[\"']?([^\"',]+)", val)
    return fam.group(1).strip() if fam else None


def _read(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def lint_theme(path: Path, name: str) -> list[str]:
    """Everything wrong with a theme folder, as short problems (empty list = clean)."""
    path = Path(path)
    problems: list[str] = []
    tokens = _read(path / "tokens.css")
    css = _read(path / "theme.css")
    try:
        raw = json.loads(_read(path / "theme.json") or "")
    except ValueError:
        raw = None
    legacy = isinstance(raw, dict) and "direction" not in raw   # a pre-3b theme: --font-display falls back to --font
    if tokens is None:
        problems.append("tokens.css missing")
    else:
        problems += [f"tokens.css lacks {t}" for t in REQUIRED_TOKENS if _token(tokens, t) is None
                     and not (legacy and t == "--font-display")]
        for rel in dict.fromkeys(re.findall(r"url\(\s*[\"']?(fonts/[^\"')]+)", tokens)):
            if not (path / rel).is_file():
                problems.append(f"tokens.css points to missing {rel}")
    if css is None:
        problems.append("theme.css missing")
    else:
        problems += [f"theme.css lacks the {s} rule" for s in FRAME_SELECTORS if s not in css]
    texts = {"tokens.css": tokens or "", "theme.css": css or ""}
    for t in COMPONENTS:
        f = path / "components" / f"{t}.html"
        text = _read(f)
        if text is None:
            problems.append(f"component {t} missing")
            continue
        texts[f"components/{t}.html"] = text
        script = dict(_SECTION.findall(text)).get("script")
        if script is None:
            problems.append(f"{t}: no <script> section")
            continue
        if "tl." not in script:
            problems.append(f"{t}: script never uses tl. (no timeline animation)")
        problems += [f"{t}: uses {api} (not allowed)" for api in FORBIDDEN if api in script]
    for extra in sorted((path / "components").glob("*.html")):
        texts.setdefault(f"components/{extra.name}", _read(extra) or "")
    problems += [f"{rel}: loads something over http(s) (themes must work offline)" for rel, text in texts.items()
                 if _FETCH.search(_NS.sub("", text))]
    meta = None
    try:
        meta = _theme_meta(path)
    except CutmateError as e:
        problems.append(f"theme.json invalid ({' '.join(str(e).split())[-120:]})")
    if meta is not None:
        fonts = meta.get("fonts") if isinstance(meta.get("fonts"), dict) else {}
        for k in ("text", "bold", "black"):
            if not fonts.get(k) or not (path / "fonts" / str(fonts[k])).is_file():
                problems.append(f"theme.json fonts.{k} file {fonts.get(k)!r} missing in fonts/")
        acc = _token(tokens or "", "--accent")
        if acc and str(meta.get("accent", "")).lower() != acc.lower():
            problems.append(f"theme.json accent {meta.get('accent')!r} differs from tokens.css --accent {acc}")
        try:
            known = set(json.loads((assets_dir() / "sfx" / "manifest.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            known = set()
        used = [e[0] for lst in meta["sfx"].values() if isinstance(lst, list) for e in lst
                if isinstance(e, list) and e] + [meta["hit_sfx"][0]]
        problems += [f"unknown sound effect {n!r}" for n in dict.fromkeys(used) if known and n not in known]
    ink, acc = (_token(tokens or "", k) for k in ("--ink", "--accent"))
    bg = _token(tokens or "", "--bg")
    ink, card = _solid(ink, bg), _solid(_token(tokens or "", "--card"), bg)
    if ink and card and contrast(ink, card) < 4.5:
        problems.append(f"contrast of --ink on --card is {contrast(ink, card):.1f} (needs 4.5)")
    direction = (meta or {}).get("direction") if isinstance((meta or {}).get("direction"), dict) else {}
    on_acc = (direction.get("palette") or {}).get("on_accent") if isinstance(direction.get("palette"), dict) else None
    if on_acc and acc and _HEX.match(str(on_acc)) and _HEX.match(acc) and contrast(on_acc, acc) < 4.5:
        problems.append(f"palette on_accent {on_acc} on --accent {acc} has contrast {contrast(on_acc, acc):.1f} (needs 4.5)")
    frame = _read(path / "frame.md")
    m = re.search(r"(?m)^name:\s*(\S+)", (frame or "").partition("\n---\n")[0]) if frame else None
    if not m or m.group(1) != name:
        problems.append(f"frame.md name is {m.group(1) if m else 'missing'}, expected {name}")
    if meta is not None and not legacy and not direction \
            and not path.resolve().is_relative_to((plugin_root() / "themes").resolve()):
        problems.append("theme.json direction is not a valid object — recreate it with cutmate theme new")
    if direction.get("mode") in ("random", "clone"):
        need = DIRECTION_KEYS + (("sources",) if direction["mode"] == "clone" else ())
        problems += [f"direction lacks {k}" for k in need if not direction.get(k)]
        clean = plugin_root() / "themes" / "clean" / "components"
        changed = sum(1 for t in LOOK if difflib.SequenceMatcher(
            None, _norm(_read(path / "components" / f"{t}.html") or ""), _norm(_read(clean / f"{t}.html") or "x")).ratio() < 0.85)
        fam = _display_family(tokens or "")
        black = str(((meta or {}).get("fonts") or {}).get("black", "")).lower()
        if changed < 5 or (fam and fam.lower() == "inter") or black.startswith("inter"):
            problems.append(LOOKS_CLEAN)
    return problems


def check_theme(name: str, clip: Path | None = None, language: str = "pl", saved: bool = False) -> dict:
    """Lint + render the theme in both formats, write the sheets and contact.png, stamp drafts / user themes.
    `saved`: check the saved (or bundled) theme even when a draft of the same name exists."""
    import tempfile
    from . import theme_check as tc
    path, kind = resolve(name, saved)
    problems = lint_theme(path, name)
    if problems:
        raise CutmateError(f"theme '{name}' fails lint: " + "; ".join(problems))
    checked = theme_hash(path)
    out = path / "check" if kind != "bundled" else config.home() / "checks" / name
    out.mkdir(parents=True, exist_ok=True)
    results, sheets = {}, {}
    with tempfile.TemporaryDirectory(prefix="cutmate-check-", ignore_cleanup_errors=True) as tmp:
        for fmt in STAMP_FORMATS:
            r = tc.theme_check(str(path), Path(tmp) / fmt.replace(":", "x"), language, fmt, clip)
            dst = out / f"sheet-{fmt.replace(':', 'x')}.png"
            shutil.copyfile(r["sheet"], dst)
            sheets[fmt] = dst
            results[fmt] = r
        contact = out / "contact.png"
        _contact_sheet(results, contact)
    if kind != "bundled":
        if theme_hash(path) != checked:
            raise CutmateError("theme changed during the check — run theme check again")
        write_stamp(path, checked)
    return {"name": name, "kind": kind, "path": path, "contact": contact, "sheets": sheets}


def _contact_sheet(results: dict, dest: Path) -> None:
    """Width 1620: 9:16 entrance row + settled row of the LOOK components (6 x 270x480), 16:9 settled row (6 x 270x152)."""
    from PIL import Image, ImageDraw

    def pick(r, kind):
        by = {}
        for p, (_, ty, k) in zip(r["snapshots"], r["labels"]):
            if k == kind and ty in LOOK:
                by.setdefault(ty, p)
        return by
    rows = [("entrance", results["9:16"], (270, 480)), ("settled", results["9:16"], (270, 480)),
            ("settled", results["16:9"], (270, 152))]
    height = sum(sz[1] for _, _, sz in rows)
    sheet = Image.new("RGB", (270 * len(LOOK), height), "black")
    draw = ImageDraw.Draw(sheet)
    y = 0
    for kind, r, (w, h) in rows:
        found = pick(r, kind)
        for i, ty in enumerate(LOOK):
            if ty not in found:
                raise CutmateError(f"contact sheet: no {kind} snapshot of the {ty} component")
            with Image.open(found[ty]) as im:
                sheet.paste(im.convert("RGB").resize((w, h)), (i * 270, y))
            label = f"{ty} {kind}"
            draw.rectangle((i * 270, y, i * 270 + 8 * len(label) + 8, y + 16), fill="black")
            draw.text((i * 270 + 4, y + 2), label, fill="white")
        y += h
    sheet.save(dest)
