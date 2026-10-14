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
