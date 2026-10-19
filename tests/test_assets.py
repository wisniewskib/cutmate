import json

import pytest
from PIL import ImageFont

from cutmate import paths
from cutmate.errors import CutmateError
from cutmate.media import duration

CUES = ("whoosh", "pop", "click", "impact", "swell", "ping")


def test_sfx_manifest_and_files():
    m = json.loads((paths.assets_dir() / "sfx" / "manifest.json").read_text(encoding="utf-8"))
    assert set(CUES) <= set(m)
    for name in CUES:
        f = paths.assets_dir() / "sfx" / m[name]["file"]
        assert f.exists()
        assert abs(duration(f) - m[name]["duration"]) < 0.06
    assert "CC0" in (paths.assets_dir() / "sfx" / "LICENSES.md").read_text(encoding="utf-8")


def test_inter_fonts_render_polish():
    d = paths.plugin_root() / "themes" / "clean" / "fonts"
    for f in ("Inter-Medium.ttf", "Inter-ExtraBold.ttf", "Inter-Black.ttf"):
        font = ImageFont.truetype(str(d / f), 64)
        assert font.getlength("ąęłśżźćńó ĄĘŁŚŻŹĆŃÓ") > 400
    assert "SIL Open Font License" in (d / "OFL-inter.txt").read_text(encoding="utf-8")


def test_theme_dir_prefers_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path))
    (tmp_path / "themes" / "mine").mkdir(parents=True)
    (tmp_path / "themes" / "mine" / "theme.json").write_text("{}", encoding="utf-8")
    assert paths.theme_dir("mine") == tmp_path / "themes" / "mine"
    with pytest.raises(CutmateError, match="not found"):
        paths.theme_dir("nope")
