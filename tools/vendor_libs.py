"""Maintainer tool: vendor every JS / CSS / font / data file a cutmate build loads, so renders are fully offline.

    .venv/bin/python tools/vendor_libs.py [--only NAME] [--dest DIR]

Downloads the pinned files from https://cdn.jsdelivr.net/npm/<name>@<ver>/<path>, follows relative imports of three's
modules, writes assets/vendor/<name>@<ver>/<path as on npm>, the licence text of each package
(assets/vendor/LICENSES/<name>.txt) and assets/vendor/MANIFEST.json. It also builds the globe data
(themes/clean/components/custom/globe/land.json + countries.json) from Natural Earth.

--only NAME      one library (gsap, three, ...) or `globe`.
--dest DIR       write the library folders to DIR instead of assets/vendor (install/setup does this for gsap:
                 `--only gsap --dest "$CUTMATE_HOME/vendor"`); every file is then checked against the committed
                 MANIFEST.json and nothing else (manifest, licences) is written.

This is the only place cutmate uses the network for libraries; builds and renders never do.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "assets" / "vendor"
GLOBE = ROOT / "themes" / "clean" / "components" / "custom" / "globe"
CDN = "https://cdn.jsdelivr.net/npm/{name}@{version}/{path}"
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
          "ne_110m_admin_0_countries.geojson")
GLOBE_POINTS = 40_000
THREE_ADDONS = ["postprocessing/EffectComposer.js", "postprocessing/RenderPass.js", "postprocessing/UnrealBloomPass.js",
                "postprocessing/OutputPass.js", "postprocessing/ShaderPass.js", "postprocessing/SavePass.js",
                "environments/RoomEnvironment.js", "loaders/FontLoader.js", "geometries/TextGeometry.js",
                "loaders/GLTFLoader.js"]
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "license.txt", "LICENSE.txt")
_REL_IMPORT = re.compile(r"""(?:from\s*|import\s*\(?\s*)["'](\.{1,2}/[^"']+)["']""")

# name -> version, files (npm paths). Order = manifest order.
LIBS = {
    "gsap": {"version": "3.14.2", "redistribute": False,
             "files": ["dist/gsap.min.js", "dist/DrawSVGPlugin.min.js", "dist/MorphSVGPlugin.min.js",
                       "dist/MotionPathPlugin.min.js", "dist/SplitText.min.js"]},
    "three": {"version": "0.181.2",
              "files": ["build/three.module.min.js", "build/three.core.min.js",
                        *[f"examples/jsm/{a}" for a in THREE_ADDONS],
                        "examples/fonts/helvetiker_bold.typeface.json", "examples/fonts/droid/droid_sans_bold.typeface.json"],
              "follow": True},
    "postprocessing": {"version": "6.39.5", "files": ["build/index.js"]},
    "animejs": {"version": "4.5.0", "files": ["dist/bundles/anime.umd.min.js"]},
    "lottie": {"npm": "lottie-web", "version": "5.12.2", "files": ["build/player/lottie.min.js"]},
    "katex": {"version": "0.19.0", "files": ["dist/katex.min.js", "dist/katex.min.css"], "fonts": True},
    "roughjs": {"version": "4.6.6", "files": ["bundled/rough.js"]},
    "d3": {"version": "7.9.0", "files": ["dist/d3.min.js"]},
}


def get(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cutmate-vendor/1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(1 + attempt)
    raise SystemExit(f"cannot download {url}: {last}")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(lib: dict, path: str) -> bytes:
    return get(CDN.format(name=lib["npm"], version=lib["version"], path=path))


def resolve_imports(lib: dict, files: dict[str, bytes]) -> None:
    """Add every file reached by a relative import from the JS in `files` (recursively)."""
    todo = [p for p in files if p.endswith(".js")]
    while todo:
        path = todo.pop()
        base = path.rsplit("/", 1)[0] if "/" in path else ""
        for rel in _REL_IMPORT.findall(files[path].decode("utf-8", "replace")):
            parts = [] if not base else base.split("/")
            for seg in rel.split("/"):
                if seg == "..":
                    parts.pop()
                elif seg != ".":
                    parts.append(seg)
            target = "/".join(parts)
            if target not in files:
                files[target] = fetch(lib, target)
                if target.endswith(".js"):
                    todo.append(target)


def katex_css(css: str) -> str:
    """Keep only the woff2 source of every KaTeX font (the plan vendors woff2 only; all browsers cutmate renders with read it)."""
    return re.sub(r',url\(fonts/[^)]+\.woff\) format\("woff"\),url\(fonts/[^)]+\.ttf\) format\("truetype"\)', "", css)


def collect(name: str, spec: dict) -> tuple[dict[str, bytes], bytes, str]:
    lib = {"npm": spec.get("npm", name), "version": spec["version"]}
    files = {p: fetch(lib, p) for p in spec["files"]}
    if spec.get("follow"):
        resolve_imports(lib, files)
    if spec.get("fonts"):
        css = katex_css(files["dist/katex.min.css"].decode("utf-8"))
        files["dist/katex.min.css"] = css.encode("utf-8")
        for f in sorted(set(re.findall(r"url\((fonts/[^)]+)\)", css))):
            files[f"dist/{f}"] = fetch(lib, f"dist/{f}")
    pkg = json.loads(fetch(lib, "package.json"))
    lic = pkg.get("license")
    lic = lic if isinstance(lic, str) else json.dumps(lic)
    text = None
    for cand in LICENSE_NAMES:
        try:
            text = fetch(lib, cand)
            break
        except urllib.error.HTTPError:
            continue
    if text is None:                                     # gsap ships no licence file: its package.json and file header
        head = files[spec["files"][0]].decode("utf-8")   # are the only licence text, recorded verbatim
        header = head[:head.index("*/") + 2]
        text = (f'The npm package {lib["npm"]}@{lib["version"]} contains no licence file. Its package.json says:\n\n'
                f'  "license": {json.dumps(pkg.get("license"))}\n\n'
                f'and every file starts with this header (verbatim):\n\n{header}\n').encode("utf-8")
    return files, text, lic


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def vendor(only: str | None, dest: Path | None) -> None:
    manifest_path = VENDOR / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    by_name = {e["name"]: e for e in manifest}
    for name, spec in LIBS.items():
        if only and only != name:
            continue
        files, lic_text, lic = collect(name, spec)
        folder = f"{name}@{spec['version']}"
        entry = {"name": name, "version": spec["version"], "license": lic,
                 "source": CDN.format(name=spec.get("npm", name), version=spec["version"], path=""),
                 "files": {p: sha(files[p]) for p in sorted(files)}, "license_file": f"LICENSES/{name}.txt"}
        if spec.get("redistribute") is False:
            entry["redistribute"] = False
        if dest:                                         # setup fallback: verify against the committed manifest
            want = by_name.get(name, {}).get("files")
            if want != entry["files"]:
                raise SystemExit(f"{name}: downloaded files do not match assets/vendor/MANIFEST.json (sha256) — refusing")
            for p, data in files.items():
                write_file(dest / folder / p, data)
        else:
            for p, data in files.items():
                write_file(VENDOR / folder / p, data)
            write_file(VENDOR / "LICENSES" / f"{name}.txt", lic_text)
            by_name[name] = entry
        print(f"{folder}: {len(files)} files, {sum(map(len, files.values())) // 1024} KiB")
    if not dest:
        order = list(LIBS)
        manifest = sorted(by_name.values(), key=lambda e: order.index(e["name"]) if e["name"] in order else 99)
        write_file(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def ring_has(ring: list, lng: float, lat: float) -> bool:
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def globe_data() -> None:
    data = json.loads(get(NE_URL).decode("utf-8"))
    polys, countries = [], {}                            # polys: (bbox, [outer, *holes])
    for feat in data["features"]:
        pr, geom = feat["properties"], feat["geometry"]
        iso = pr["ISO_A2"] if pr.get("ISO_A2") not in (None, "-99") else pr["ADM0_A3"]
        countries[iso] = {"en": pr["NAME_EN"], "pl": pr["NAME_PL"], "lat": pr["LABEL_Y"], "lng": pr["LABEL_X"]}
        parts = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for rings in parts:
            xs = [p[0] for p in rings[0]]
            ys = [p[1] for p in rings[0]]
            polys.append(((min(xs), min(ys), max(xs), max(ys)), rings))
    golden = math.pi * (3 - math.sqrt(5))
    pts = []
    for i in range(GLOBE_POINTS):
        lat = math.degrees(math.asin(1 - 2 * (i + 0.5) / GLOBE_POINTS))
        lng = math.degrees((i * golden) % (2 * math.pi)) - 180
        for (x0, y0, x1, y1), rings in polys:
            if x0 <= lng <= x1 and y0 <= lat <= y1 and ring_has(rings[0], lng, lat) \
                    and not any(ring_has(h, lng, lat) for h in rings[1:]):
                pts.append([round(lat, 2), round(lng, 2)])
                break
    GLOBE.mkdir(parents=True, exist_ok=True)
    (GLOBE / "land.json").write_text(json.dumps({"v": 1, "pts": pts}, separators=(",", ":")) + "\n", encoding="utf-8")
    (GLOBE / "countries.json").write_text(json.dumps(dict(sorted(countries.items())), ensure_ascii=False,
                                                     separators=(",", ":")) + "\n", encoding="utf-8")
    (GLOBE / "SOURCE.txt").write_text(
        f"Natural Earth 1:110m Admin 0 - Countries (public domain, https://www.naturalearthdata.com/about/terms-of-use/)\n"
        f"Source file: {NE_URL}\n"
        f"land.json: {len(pts)} of {GLOBE_POINTS} Fibonacci-sphere points that fall inside a land polygon, [lat, lng] rounded to 2 decimals.\n"
        f"countries.json: ISO_A2 (ADM0_A3 where ISO_A2 is -99) -> NAME_EN, NAME_PL, label lat (LABEL_Y), label lng (LABEL_X).\n"
        f"Built by tools/vendor_libs.py.\n", encoding="utf-8")
    print(f"globe: {len(pts)} land points, {len(countries)} countries")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"one of: {', '.join(LIBS)}, globe")
    ap.add_argument("--dest", help="write library folders here (sha-checked against MANIFEST.json)")
    a = ap.parse_args(argv)
    if a.only and a.only not in (*LIBS, "globe"):
        ap.error(f"--only: unknown name {a.only!r}")
    if a.only != "globe":
        vendor(a.only, Path(a.dest) if a.dest else None)
    if a.only in (None, "globe") and not a.dest:
        globe_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
