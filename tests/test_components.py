import pytest

from cutmate import paths
from cutmate.build import _sections
from cutmate.plan import TYPES


def test_every_component_has_a_script_and_no_forbidden_apis():
    d = paths.theme_dir("clean") / "components"
    for t in TYPES:
        sec = _sections(d / f"{t}.html")
        js = sec["script"]
        for bad in ("Date.now", "Math.random", "performance.now", "onUpdate", "setTimeout", ".play("):
            assert bad not in js, f"{t}: {bad}"
        assert "tl." in js, t


def test_split_uses_media_tag():
    sec = _sections(paths.theme_dir("clean") / "components" / "split.html")
    assert "{{media_tag}}" in sec["markup"]


@pytest.mark.hf
def test_theme_check_clean(tmp_path):
    from cutmate.theme_check import theme_check
    r = theme_check("clean", tmp_path)
    assert r["sheet"].exists() and len(r["snapshots"]) == len(TYPES) + 1
