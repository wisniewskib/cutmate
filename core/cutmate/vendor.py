"""Libraries cutmate does not bundle (redistribute: false in assets/vendor/MANIFEST.json): fetched into $CUTMATE_HOME/vendor,
sha-checked against the manifest. `cutmate vendor` runs this; tools/vendor_libs.py --dest shares it."""
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import home
from .errors import CutmateError
from .paths import vendor_dir


def manifest() -> list[dict]:
    try:
        return json.loads((vendor_dir() / "MANIFEST.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CutmateError(f"{vendor_dir() / 'MANIFEST.json'}: cannot read — reinstall the plugin") from None


def fetched_entries(only: str | None = None) -> list[dict]:
    return [e for e in manifest() if e.get("redistribute") is False and (only is None or e["name"] == only)]


def _folder(e: dict) -> str:
    return f"{e['name']}@{e['version']}"


def _ok(base: Path, e: dict) -> bool:
    for path, want in e["files"].items():
        f = base / _folder(e) / path
        try:
            if hashlib.sha256(f.read_bytes()).hexdigest() != want:
                return False
        except OSError:
            return False
    return True


def missing() -> list[str]:
    """Folder names of fetched libraries that are absent or fail their sha256 in both places."""
    return [_folder(e) for e in fetched_entries() if not (_ok(vendor_dir(), e) or _ok(home() / "vendor", e))]


def _get(url: str) -> bytes:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cutmate-vendor/1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        raise CutmateError(f"cannot download {url} ({' '.join(str(getattr(e, 'reason', e)).split())}) — "
                           f"check the connection and run `cutmate vendor` again") from None


def fetch(dest: Path, only: str | None = None) -> list[str]:
    """Download every fetched library that is missing or wrong into dest (idempotent); returns what was done, one line each."""
    done = []
    for e in fetched_entries(only):
        folder = _folder(e)
        if _ok(vendor_dir(), e) or _ok(dest, e):
            done.append(f"{folder}: ok")
            continue
        data = {}
        for path, want in e["files"].items():
            blob = _get(e["source"] + path)
            if hashlib.sha256(blob).hexdigest() != want:
                raise CutmateError(f"{folder}/{path}: downloaded file does not match assets/vendor/MANIFEST.json (sha256) — not written")
            data[path] = blob
        for path, blob in data.items():
            f = dest / folder / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(blob)
        done.append(f"{folder}: fetched {len(data)} files into {dest / folder}")
    if only and not done:
        raise CutmateError(f"{only}: not a fetched library (see redistribute in assets/vendor/MANIFEST.json)")
    return done
