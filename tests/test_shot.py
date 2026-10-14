import os
import platform
import subprocess

import pytest
from PIL import Image

from cutmate import shot
from cutmate.errors import CutmateError


@pytest.mark.skipif(shot.find_chrome() is None, reason="no Chrome on this machine")
def test_screenshot_local_page(tmp_path):
    page = tmp_path / "strona ą.html"
    page.write_text("<html><body style='background:#123;color:#fff;font:60px sans-serif'>Caveman ąę</body></html>",
                    encoding="utf-8")
    png = shot.screenshot(str(page), tmp_path / "out" / "shot.png", 800, 500)
    im = Image.open(png)
    assert im.size == (1600, 1000)


def test_no_chrome(monkeypatch, tmp_path):
    monkeypatch.setattr(shot, "find_chrome", lambda: None)
    with pytest.raises(CutmateError, match="broll"):
        shot.screenshot("https://example.com", tmp_path / "x.png")


@pytest.mark.skipif(platform.system() == "Windows", reason="executable script not portable on Windows")
def test_stale_output_detection(monkeypatch, tmp_path):
    """Verify that a stale PNG is deleted before Chrome runs, so a failed run doesn't pass the size check."""
    # Create a fake 5 kB PNG at the destination
    png = tmp_path / "shot.png"
    png.write_bytes(b"fake png" * 700)  # ~5.6 kB
    assert png.stat().st_size > 2000

    # Create a tiny executable script that exits 0 without writing anything
    fake_chrome = tmp_path / "fake-chrome"
    fake_chrome.write_text("#!/bin/sh\nexit 0\n")
    fake_chrome.chmod(0o755)

    # Monkeypatch find_chrome to return the fake script
    monkeypatch.setattr(shot, "find_chrome", lambda: str(fake_chrome))

    # Should raise CutmateError because the fake Chrome doesn't create a new PNG
    with pytest.raises(CutmateError, match="failed"):
        shot.screenshot("https://example.com", png)


@pytest.mark.parametrize("arg,expected", [("example.invalid/x", "https://example.invalid/x"),
                                          ("http://a.b/c", "http://a.b/c")])
def test_url_scheme_handling(monkeypatch, tmp_path, arg, expected):
    seen = {}
    monkeypatch.setattr(shot, "find_chrome", lambda: "chrome")

    def fake_run(cmd, **kw):
        seen["url"] = cmd[-1]
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(shot.subprocess, "run", fake_run)
    with pytest.raises(CutmateError):   # nothing written → failure, but the command was built
        shot.screenshot(arg, tmp_path / "x.png")
    assert seen["url"] == expected


def test_existing_path_becomes_file_url(monkeypatch, tmp_path):
    page = tmp_path / "p.html"
    page.write_text("x")
    seen = {}
    monkeypatch.setattr(shot, "find_chrome", lambda: "chrome")
    monkeypatch.setattr(shot.subprocess, "run", lambda cmd, **kw: seen.update(url=cmd[-1]) or subprocess.CompletedProcess(cmd, 0))
    with pytest.raises(CutmateError):
        shot.screenshot(str(page), tmp_path / "x.png")
    assert seen["url"] == page.resolve().as_uri()
