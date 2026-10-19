"""One-off: download Inter (OFL) and Kenney sound packs (CC0), pick the cues cutmate needs, normalise, write manifest.

    .venv/bin/python tools/fetch_assets.py

Re-runnable; caches zips in ~/.cache/cutmate-assets. Prints every pick so a human can sanity-check durations.
"""
import fnmatch
import io
import json
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache" / "cutmate-assets"
INTER = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
PACKS = {
    "interface": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
    "impact": "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
    "ui": "https://kenney.nl/media/pages/assets/ui-audio/490d233f68-1677590494/kenney_ui-audio.zip",
    "digital": "https://kenney.nl/media/pages/assets/digital-audio/216eac4753-1677590265/kenney_digital-audio.zip",
    "scifi": "https://kenney.nl/media/pages/assets/sci-fi-sounds/6b296f9ecf-1677589334/kenney_sci-fi-sounds.zip",
}
# cue -> ordered candidate globs (matched against basenames of .ogg files in all packs); first hit wins
CUES = {
    "whoosh": ["maximize_00[1-9].ogg", "*swoosh*.ogg", "*whoosh*.ogg", "phaserUp[1-7].ogg"],
    "pop": ["pluck_00[12].ogg", "drop_00[1-4].ogg", "*pop*.ogg", "click[1-5].ogg"],
    "click": ["click_00[1-5].ogg", "tick_00[1-4].ogg", "switch[1-9].ogg"],
    "impact": ["impactPunch_heavy_00[0-4].ogg", "impactSoft_heavy_00[0-4].ogg", "*impact*heavy*.ogg"],
    "swell": ["forceField_00[0-4].ogg", "phaserUp[1-7].ogg", "spaceEngine*.ogg"],
    "ping": ["confirmation_00[1-4].ogg", "glass_00[1-6].ogg", "*bong*.ogg"],
}
MAX_DUR = {"swell": 3.0}  # others must be <= 1.5 s


def fetch(url: str) -> zipfile.ZipFile:
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / url.rsplit("/", 1)[-1]
    if not dst.exists():
        print("download", url)
        req = urllib.request.Request(url, headers={"User-Agent": "cutmate-fetch/1.0"})
        dst.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return zipfile.ZipFile(dst)


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def peak_db(path: Path) -> float:
    err = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"max_volume: (-?[\d.]+) dB", err)[-1])


def fonts() -> None:
    z = fetch(INTER)
    dst = ROOT / "themes" / "clean" / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    names = z.namelist()
    for want in ("Inter-Medium.ttf", "Inter-ExtraBold.ttf", "Inter-Black.ttf"):
        src = next((n for n in names if n.endswith("/" + want) or n == want), None)
        if not src:
            sys.exit(f"{want} not in Inter zip; .ttf files present: {[n for n in names if n.endswith('.ttf')][:20]}")
        (dst / want).write_bytes(z.read(src))
        print("font", src)
    lic = next(n for n in names if n.upper().endswith("LICENSE.TXT"))
    (dst / "OFL-inter.txt").write_bytes(z.read(lic))


def sfx() -> None:
    tmp = CACHE / "ogg"
    tmp.mkdir(parents=True, exist_ok=True)
    files = {}
    for pack, url in PACKS.items():
        z = fetch(url)
        for n in z.namelist():
            if n.lower().endswith(".ogg"):
                files.setdefault(Path(n).name, (pack, z, n))
    dst = ROOT / "assets" / "sfx"
    dst.mkdir(parents=True, exist_ok=True)
    manifest, credits = {}, []
    for cue, globs in CUES.items():
        pick = None
        for g in globs:
            hits = sorted(f for f in files if fnmatch.fnmatch(f, g))
            if hits:
                pick = hits[0]
                break
        if not pick:
            sys.exit(f"no file for {cue!r}; edit CUES. Available: {sorted(files)[:80]}")
        pack, z, inner = files[pick]
        raw = tmp / pick
        raw.write_bytes(z.read(inner))
        gain = -3.0 - peak_db(raw)
        out = dst / f"{cue}.mp3"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af", f"volume={gain:.2f}dB",
                        "-ac", "1", "-ar", "48000", "-b:a", "128k", str(out)], check=True)
        # mp3 encoding/resampling overshoots on transients: re-measure the encoded file and correct once
        err = peak_db(out) + 3.0
        if abs(err) > 0.3:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af",
                            f"volume={gain - err:.2f}dB", "-ac", "1", "-ar", "48000", "-b:a", "128k", str(out)], check=True)
        d = round(probe_duration(out), 3)
        if d > MAX_DUR.get(cue, 1.5):
            sys.exit(f"{cue}: {pick} is {d}s long — pick a shorter candidate in CUES")
        manifest[cue] = {"file": out.name, "duration": d, "source": f"Kenney {pack}: {pick}"}
        credits.append(f"- `{out.name}` ← Kenney.nl *{pack}* pack, `{pick}` (CC0 1.0)")
        print(f"sfx {cue:7} <- {pack}/{pick} ({d}s, gain {gain:+.1f} dB)")
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (dst / "LICENSES.md").write_text(
        "# Sound effects\n\nAll files are from Kenney.nl audio packs, released under CC0 1.0 (public domain).\n"
        "https://kenney.nl/support — attribution not required; credited anyway.\n\n" + "\n".join(credits) + "\n",
        encoding="utf-8")


if __name__ == "__main__":
    fonts()
    sfx()
