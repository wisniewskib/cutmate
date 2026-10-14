"""Screenshot a web page (or local HTML) with headless Chrome for split-panel b-roll."""
import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import CutmateError

NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")


def find_chrome() -> str | None:
    for n in NAMES:
        p = shutil.which(n)
        if p:
            return p
    fixed = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(env):
            fixed.append(os.path.join(os.environ[env], "Google", "Chrome", "Application", "chrome.exe"))
    for p in fixed:
        if os.path.exists(p):
            return p
    cached = sorted(glob.glob(os.path.expanduser("~/.cache/hyperframes/chrome/**/chrome-headless-shell*"), recursive=True))
    cached = [c for c in cached if os.path.isfile(c) and os.access(c, os.X_OK)]
    return cached[-1] if cached else None


def screenshot(url: str, dst: Path, width: int = 1000, height: int = 700, dark: bool = True) -> Path:
    chrome = find_chrome()
    if not chrome:
        raise CutmateError("Chrome not found — install Google Chrome, or put a screenshot into broll/ yourself")
    dst = Path(dst).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Delete stale output to ensure we detect failed runs
    dst.unlink(missing_ok=True)
    if "://" not in url:
        url = Path(url).resolve().as_uri()
    # Use isolated profile to prevent interference from running Chrome instances
    profile_dir = tempfile.mkdtemp()
    try:
        cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
               f"--user-data-dir={profile_dir}", "--force-device-scale-factor=2",
               f"--window-size={width},{height}", "--virtual-time-budget=4000",
               f"--screenshot={dst}", url]
        if dark:
            cmd.insert(4, "--force-dark-mode")
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except subprocess.TimeoutExpired:
            raise CutmateError(f"screenshot of {url} timed out after 60 s") from None
        if not dst.exists() or dst.stat().st_size < 2000:
            raise CutmateError(f"screenshot of {url} failed (exit code {result.returncode}) — page may need login or block bots; save one into broll/ yourself")
        return dst
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
