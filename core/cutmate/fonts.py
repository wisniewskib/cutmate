"""Google Fonts (OFL) into a theme draft: static TTFs, licence, Polish glyph check, tokens.css font blocks."""
import json
import re
import shutil
import tempfile
from pathlib import Path

import requests

from .errors import CutmateError

POLISH = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
WEIGHTS = (400, 500, 600, 700, 800, 900)
CSS2 = "https://fonts.googleapis.com/css2"
OFL_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/{slug}/OFL.txt"
# Google answers format('truetype') (static TTF) for this old Android UA; Chrome UAs get woff/woff2.
TTF_UA = "Mozilla/5.0 (Linux; U; Android 4.0.3; en-us) AppleWebKit/534.30 Version/4.0 Mobile Safari/534.30"
ROLES = ("text", "display")
_TIMEOUT = 30
_FAMILY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ]*$")
_SRC = re.compile(r"url\(\s*[\"']?(https://[^)\"'\s]+)[\"']?\s*\)\s*format\(\s*[\"']truetype[\"']\s*\)")
_FACE_FAMILY = re.compile(r"@font-face\s*\{\s*font-family:\s*\"([^\"]+)\"")
_FACE_FILE = re.compile(r"url\(\"fonts/([^\"]+)\"\)")


def slug(family: str) -> str:
    return family.replace(" ", "").lower()


def _net_error(e: Exception) -> CutmateError:
    return CutmateError(f"cannot reach Google Fonts ({e}) — check the network")


def _get(url: str, **kw) -> requests.Response:
    try:
        return requests.get(url, timeout=_TIMEOUT, **kw)
    except requests.RequestException as e:
        raise _net_error(e) from e


def download_family(family: str, dest: Path) -> dict:
    """Download every available static weight (400-900) of an OFL family into dest."""
    if not _FAMILY.match(family):
        raise CutmateError(f"bad font name {family!r}: letters, digits and spaces only")
    dest = Path(dest)
    s = slug(family)
    r = _get(OFL_URL.format(slug=s))
    if r.status_code == 404:
        raise CutmateError(f"font '{family}' is not an OFL font on Google Fonts — pick another")
    if r.status_code != 200:
        raise CutmateError(f"cannot read the licence of '{family}' (HTTP {r.status_code}) — try again")
    dest.mkdir(parents=True, exist_ok=True)
    lic = dest / f"OFL-{s}.txt"
    lic.write_bytes(r.content)
    files: dict[int, Path] = {}
    base = family.replace(" ", "")
    for w in WEIGHTS:
        css = _get(CSS2, params={"family": f"{family}:wght@{w}"}, headers={"User-Agent": TTF_UA})
        if css.status_code == 400:
            continue                                         # this weight does not exist
        if css.status_code != 200:
            raise CutmateError(f"Google Fonts answered HTTP {css.status_code} for '{family}' — try again")
        m = _SRC.search(css.text)
        if not m:
            raise CutmateError(f"Google Fonts offers no TrueType file for '{family}' {w} — pick another")
        f = _get(m.group(1))
        if f.status_code != 200:
            raise CutmateError(f"cannot download '{family}' {w} (HTTP {f.status_code}) — try again")
        p = dest / f"{base}-{w}.ttf"
        p.write_bytes(f.content)
        files[w] = p
    if not files:
        raise CutmateError(f"font '{family}' not found on Google Fonts")
    return {"family": family, "files": files, "license": lic}


def has_glyphs(path: Path, chars: str = POLISH) -> bool:
    try:
        from fontTools.ttLib import TTFont
    except ImportError as e:
        raise CutmateError("fonttools missing — re-run /cutmate:setup (step 4)") from e
    font = TTFont(str(path), lazy=True)
    try:
        cmap = font.getBestCmap() or {}
    finally:
        font.close()
    return all(ord(c) in cmap for c in chars)


def _block_re(role: str) -> re.Pattern:
    return re.compile(rf"/\* cutmate:font {role} \*/.*?/\* /cutmate:font {role} \*/", re.S)


def _block(role: str, body: str) -> str:
    return f"/* cutmate:font {role} */\n{body}\n/* /cutmate:font {role} */"


def _faces(family: str, files: dict[int, Path]) -> str:
    return "\n".join(f'@font-face {{ font-family: "{family}"; src: url("fonts/{p.name}") format("truetype"); '
                     f'font-weight: {w}; }}' for w, p in sorted(files.items()))


def _nearest(files: dict[int, Path], target: int) -> int:
    return min(files, key=lambda w: (abs(w - target), w))


def set_font(theme_path: Path, family: str, role: str) -> dict:
    if role not in ROLES:
        raise CutmateError(f"unknown font role {role!r} (text or display)")
    theme_path = Path(theme_path)
    tokens = theme_path / "tokens.css"
    css = tokens.read_text(encoding="utf-8")
    for r in ROLES:
        n = len(_block_re(r).findall(css))
        if n > 1:
            raise CutmateError(f"tokens.css has {n} 'cutmate:font {r}' blocks — keep one")
    if not _block_re(role).search(css):
        raise CutmateError(f"tokens.css has no cutmate:font {role} block — cannot set the font")
    fonts_dir = theme_path / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    files: dict[int, Path] = {}
    moved = False
    try:
        with tempfile.TemporaryDirectory(prefix="cutmate-font-", ignore_cleanup_errors=True) as tmp:
            got = download_family(family, Path(tmp))
            for p in got["files"].values():
                if not has_glyphs(p):
                    raise CutmateError(f"font '{family}' lacks Polish letters (ą ę ł …) — pick another")
            moved = True
            for w, p in got["files"].items():
                shutil.move(str(p), str(fonts_dir / p.name))
                files[w] = fonts_dir / p.name
            shutil.move(str(got["license"]), str(fonts_dir / got["license"].name))

        var = "--font" if role == "text" else "--font-display"
        body = _faces(family, files) + f'\n:root {{ {var}: "{family}", sans-serif; font-synthesis: none; }}'
        css = _block_re(role).sub(lambda _: _block(role, body), css, count=1)

        other = "display" if role == "text" else "text"
        ovar = "--font-display" if other == "display" else "--font"
        omatch = _block_re(other).search(css)
        ofam = re.search(rf'{ovar}:\s*"([^"]+)"', omatch.group(0)) if omatch else None
        if omatch and ofam and ofam.group(1) not in set(_FACE_FAMILY.findall(css)):
            # the other role borrowed faces from the block we just replaced (bundled Inter) — follow the new family
            css = _block_re(other).sub(lambda _: _block(other, f':root {{ {ovar}: "{family}", sans-serif; }}'), css, count=1)
            other_family = family
        else:
            other_family = ofam.group(1) if ofam else None
        tokens.write_text(css, encoding="utf-8")

        tj_path = theme_path / "theme.json"
        tj = json.loads(tj_path.read_text(encoding="utf-8"))
        tf = tj.setdefault("fonts", {})
        if role == "text":
            tf["text"] = files[_nearest(files, 500)].name
            tf["bold"] = files[_nearest(files, 800)].name
            if tf.get("black") not in _FACE_FILE.findall(css):
                tf["black"] = files[max(files)].name      # the old black face was Inter's, now gone
        else:
            tf["black"] = files[max(files)].name
        direction = tj.get("direction")
        if isinstance(direction, dict):
            df = direction.setdefault("fonts", {})
            df[role] = family
            if other_family:
                df[other] = other_family
        tj_path.write_text(json.dumps(tj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        if moved:
            _prune(fonts_dir, tokens.read_text(encoding="utf-8"))
    return {"family": family, "role": role, "files": [p.name for _, p in sorted(files.items())]}


def _prune(fonts_dir: Path, css: str) -> None:
    used = set(_FACE_FILE.findall(css))
    keep_lic = {f"OFL-{slug(f)}.txt" for f in _FACE_FAMILY.findall(css)}
    for p in fonts_dir.glob("*.ttf"):
        if p.name not in used:
            p.unlink()
    for p in fonts_dir.glob("OFL-*.txt"):
        if p.name not in keep_lic:
            p.unlink()
