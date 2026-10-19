import json

import pytest

from cutmate import config, themes
from cutmate.directions import roll, suggest_name
from cutmate.effects import find_effect
from cutmate.errors import CutmateError
from cutmate.paths import plugin_root, theme_dir


def _stamped(name="mine", **kw):
    info = themes.new_theme(name, **kw)
    d = themes.draft_dir(name)
    themes.write_stamp(d)
    return info, d


def test_theme_dir_accepts_abs_path(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "theme.json").write_text("{}", encoding="utf-8")
    assert theme_dir(str(d)) == d


def test_find_effect_with_draft_path(tmp_path):
    themes.new_theme("mine")
    found = find_effect("burst", tmp_path, str(themes.draft_dir("mine")))
    assert found.name == "burst.html"


def test_new_custom_copies_clean():
    info = themes.new_theme("mine")
    d = themes.draft_dir("mine")
    clean = plugin_root() / "themes" / "clean"
    for c in (clean / "components").glob("*.html"):
        assert (d / "components" / c.name).exists()
    assert not (d / "components" / "custom").exists()
    assert (d / "fonts" / "OFL-inter.txt").exists() and not (d / "fonts" / "OFL.txt").exists()
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    assert tj["name"] == "mine" and tj["direction"] == {"mode": "custom"} and tj["base"] == "clean"
    assert "name: mine" in (d / "frame.md").read_text(encoding="utf-8").split("---")[1]
    assert info["exists"] is False
    with pytest.raises(CutmateError):
        theme_dir("mine")


def test_new_random_named_and_reproducible():
    info = themes.new_theme(None, mode="random", seed=5)
    assert info["direction"] == roll(5)
    assert info["name"] == suggest_name(roll(5), {"clean"})
    other = themes.new_theme("x", mode="random", seed=5, avoid=[info["name"]])
    a, b = info["direction"], other["direction"]
    assert a["fonts"]["display"] != b["fonts"]["display"]
    assert a["shapes"] != b["shapes"] and a["motion"] != b["motion"]


@pytest.mark.parametrize("bad", ["clean", "../x", "a b"])
def test_new_reserved_and_bad_names(bad):
    with pytest.raises(CutmateError):
        themes.new_theme(bad)


def test_save_refuses_unchecked():
    themes.new_theme("mine")
    with pytest.raises(CutmateError, match="theme check"):
        themes.save_theme("mine")
    with pytest.raises(CutmateError, match="no draft"):
        themes.save_theme("nope")


def test_save_refuses_changed_after_check():
    _, d = _stamped()
    with open(d / "components" / "chip.html", "a", encoding="utf-8") as f:
        f.write("\n<!-- x -->")
    with pytest.raises(CutmateError, match="theme check"):
        themes.save_theme("mine")


def test_save_moves_draft_and_lists_checked():
    _, d = _stamped()
    target = themes.save_theme("mine")
    assert target == config.home() / "themes" / "mine" and (target / "theme.json").exists()
    assert not d.exists()
    by = {t["name"]: t for t in themes.list_themes()}
    assert by["mine"]["kind"] == "user" and by["mine"]["checked"] is True
    assert by["clean"]["kind"] == "bundled" and by["clean"]["checked"] is None


def test_save_existing_needs_force_and_backs_up():
    _stamped()
    themes.save_theme("mine")
    old = (config.home() / "themes" / "mine" / "tokens.css").read_text(encoding="utf-8")
    _, d = _stamped()
    (d / "tokens.css").write_text(":root{--new:1}", encoding="utf-8")
    themes.write_stamp(d)
    with pytest.raises(CutmateError, match="--force"):
        themes.save_theme("mine")
    themes.save_theme("mine", force=True)
    backups = list((config.home() / "themes" / ".backup").glob("mine-*"))
    assert len(backups) == 1 and ":" not in backups[0].name
    assert (backups[0] / "tokens.css").read_text(encoding="utf-8") == old
    assert (config.home() / "themes" / "mine" / "tokens.css").read_text(encoding="utf-8") == ":root{--new:1}"


def test_save_into_effects_only_dir_keeps_custom():
    cust = config.home() / "themes" / "mine" / "components" / "custom"
    cust.mkdir(parents=True)
    (cust / "orb.html").write_text("x", encoding="utf-8")
    (cust / "index.json").write_text("[]", encoding="utf-8")
    _stamped()
    themes.save_theme("mine")
    assert (cust / "orb.html").exists() and (cust / "index.json").exists()
    _stamped()
    themes.save_theme("mine", force=True)
    assert (cust / "orb.html").exists() and (cust / "index.json").exists()


def test_use_theme():
    _stamped()
    themes.save_theme("mine")
    themes.use_theme("mine")
    assert config.load().theme == "mine"
    themes.new_theme("draft-only")
    with pytest.raises(CutmateError):
        themes.use_theme("draft-only")
