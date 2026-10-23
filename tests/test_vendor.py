"""assets/vendor: every library a build loads is bundled (or, for gsap, fetched by setup), pinned, hashed, licensed."""
import hashlib
import json
import re

import pytest

from cutmate import effects
from cutmate.paths import plugin_root, vendor_dir

MANIFEST = vendor_dir() / "MANIFEST.json"
GLOBE = plugin_root() / "themes" / "clean" / "components" / "custom" / "globe"
LAZY_LOADERS = ("postprocessing@6.39.5",)             # fetch() of a URL given at run time by the effect itself


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_matches_files():
    entries = manifest()
    assert {e["name"] for e in entries} == set(effects.VENDOR)
    for e in entries:
        assert e["version"] and e["license"] and e["source"].startswith("https://")
        assert (vendor_dir() / e["license_file"]).is_file(), e["name"]
        folder = f"{e['name']}@{e['version']}"
        assert folder == effects.VENDOR[e["name"]]
        for path, want in e["files"].items():
            f = effects.vendor_root(folder) / path          # gsap (redistribute: false) may live in $CUTMATE_HOME/vendor
            assert f.is_file(), f"{folder}/{path}"
            assert hashlib.sha256(f.read_bytes()).hexdigest() == want, f"{folder}/{path}"
    assert [e["name"] for e in entries if e.get("redistribute") is False] in ([], ["gsap"])


def test_committed_files_are_the_manifest_files():
    """Everything under assets/vendor (but the manifest, licences and a non-redistributable gsap) is in the manifest."""
    listed = {f"{e['name']}@{e['version']}/{p}" for e in manifest() for p in e["files"]}
    on_disk = {p.relative_to(vendor_dir()).as_posix() for p in vendor_dir().rglob("*")
               if p.is_file() and p.relative_to(vendor_dir()).parts[0] not in ("LICENSES", "MANIFEST.json")}
    assert on_disk <= listed


def test_three_addons_relative_imports_resolve():
    jsm = effects.vendor_root("three@0.181.2") / "examples" / "jsm"
    files = list(jsm.rglob("*.js"))
    assert files
    for f in files:
        for rel in re.findall(r"""(?:from\s*|import\s*\(?\s*)["'](\.{1,2}/[^"']+)["']""", f.read_text(encoding="utf-8")):
            assert (f.parent / rel).resolve().is_file(), f"{f.name} imports missing {rel}"


def test_vendor_has_no_network_at_load():
    for js in vendor_dir().rglob("*.js"):
        if js.relative_to(vendor_dir()).parts[0] in LAZY_LOADERS:
            continue
        text = js.read_text(encoding="utf-8")
        assert 'fetch("http' not in text and 'import("http' not in text, js.name
    css_dir = effects.vendor_root("katex@0.19.0") / "dist"
    urls = re.findall(r"url\(([^)]+)\)", (css_dir / "katex.min.css").read_text(encoding="utf-8"))
    assert urls
    for u in urls:
        assert not u.startswith(("http", "//", "data:")) and (css_dir / u).is_file(), u


def test_globe_data():
    land = json.loads((GLOBE / "land.json").read_text(encoding="utf-8"))
    assert land["v"] == 1 and 8000 <= len(land["pts"]) <= 12000
    assert all(-90 <= lat <= 90 and -180 <= lng <= 180 for lat, lng in land["pts"])
    countries = json.loads((GLOBE / "countries.json").read_text(encoding="utf-8"))
    assert countries["PL"]["pl"] == "Polska" and countries["PL"]["en"] == "Poland"
    for iso in ("US", "JP", "CN", "DE"):
        assert isinstance(countries[iso]["lat"], float) and isinstance(countries[iso]["lng"], float)
    assert "-99" not in countries and "FRA" in countries
    assert (GLOBE / "SOURCE.txt").read_text(encoding="utf-8").startswith("Natural Earth")


def test_gitattributes_keeps_vendor_bytes():
    lines = (plugin_root() / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "assets/vendor/** -text" in lines
    assert "themes/clean/components/custom/*/** -text" in lines


def test_vendor_libs_only_unknown_name_is_usage_error():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vendor_libs", plugin_root() / "tools" / "vendor_libs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.main(["--only", "nope"])
    assert set(mod.LIBS) == set(effects.VENDOR)
    assert {n: f"{n}@{s['version']}" for n, s in mod.LIBS.items()} == effects.VENDOR


@pytest.fixture
def no_net(tmp_path, monkeypatch):
    """Empty bundled dir with the real manifest, and a fake download that serves the real gsap files."""
    from cutmate import vendor
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "MANIFEST.json").write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(vendor, "vendor_dir", lambda: bundled)
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    calls = []
    monkeypatch.setitem(vendor.__dict__, "_real_get", vendor._get)
    real = effects.vendor_root("gsap@3.14.2")

    def fake_get(url):
        calls.append(url)
        assert url.startswith("https://cdn.jsdelivr.net/npm/gsap@3.14.2/")
        return (real / url.split("gsap@3.14.2/", 1)[1]).read_bytes()
    monkeypatch.setattr(vendor, "_get", fake_get)
    return vendor, tmp_path / "home" / "vendor", calls


def test_cutmate_vendor_fetches_idempotently(no_net, capsys):
    from cutmate.cli import main
    vendor, dest, calls = no_net
    assert vendor.missing() == ["gsap@3.14.2"]
    assert main(["vendor"]) == 0
    assert "gsap@3.14.2: fetched 5 files" in capsys.readouterr().out
    assert (dest / "gsap@3.14.2" / "dist" / "gsap.min.js").is_file() and vendor.missing() == [] and len(calls) == 5
    assert main(["vendor"]) == 0 and "gsap@3.14.2: ok" in capsys.readouterr().out and len(calls) == 5   # nothing re-fetched
    (dest / "gsap@3.14.2" / "dist" / "gsap.min.js").write_bytes(b"tampered")                              # sha mismatch → repaired
    assert vendor.missing() == ["gsap@3.14.2"]
    assert main(["vendor"]) == 0 and vendor.missing() == [] and len(calls) == 10


def test_cutmate_vendor_errors_are_one_line(no_net, monkeypatch, capsys):
    from cutmate.cli import main
    vendor, dest, _ = no_net
    real_get = vendor.__dict__["_real_get"]
    monkeypatch.setattr(vendor, "_get", lambda url: b"not gsap")
    assert main(["vendor"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("cutmate: gsap@3.14.2/dist/") and "does not match" in err and err.count("\n") == 1
    assert not dest.exists()                                                  # nothing written on a mismatch
    import urllib.error

    def boom(*a, **k):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(vendor, "_get", real_get)                              # the real downloader, a dead network
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert main(["vendor"]) == 2
    err = capsys.readouterr().err
    assert "cannot download" in err and "offline" in err and "cutmate vendor" in err and err.count("\n") == 1
