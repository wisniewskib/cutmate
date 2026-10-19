import json
import re

import pytest
import requests
import responses

from cutmate import directions, fonts, themes
from cutmate.cli import main
from cutmate.errors import CutmateError
from cutmate.paths import plugin_root

TTF = (plugin_root() / "themes" / "clean" / "fonts" / "Inter-Black.ttf").read_bytes()
GSTATIC = "https://fonts.gstatic.com/x.ttf"


def _css(w):
    return f"@font-face {{ font-weight: {w}; src: url({GSTATIC}) format('truetype'); }}"


def _mock_family(family, weights):
    s = fonts.slug(family)
    responses.add(responses.GET, fonts.OFL_URL.format(slug=s), body="OFL text", status=200)
    for w in fonts.WEIGHTS:
        url = f"{fonts.CSS2}?family={family.replace(' ', '+')}:wght@{w}"
        responses.add(responses.GET, url, body=_css(w) if w in weights else "no", status=200 if w in weights else 400)
    responses.add(responses.GET, GSTATIC, body=TTF, status=200)


def _tokens(d):
    return (d / "tokens.css").read_text(encoding="utf-8")


def test_slug():
    assert fonts.slug("Bebas Neue") == "bebasneue"
    assert fonts.slug("DM Serif Display") == "dmserifdisplay"


@responses.activate
def test_set_font_display():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    _mock_family("Anton", (400, 900))
    r = fonts.set_font(d, "Anton", "display")
    css = _tokens(d)
    assert css.count('font-family: "Anton"') == 2
    assert '--font-display: "Anton"' in css
    assert "font-synthesis: none" in css
    assert (d / "fonts" / "Anton-900.ttf").exists() and (d / "fonts" / "OFL-anton.txt").exists()
    assert json.loads((d / "theme.json").read_text(encoding="utf-8"))["fonts"]["black"] == "Anton-900.ttf"
    for f in ("Inter-Medium.ttf", "Inter-ExtraBold.ttf", "Inter-Black.ttf"):
        assert (d / "fonts" / f).exists()
    assert "https://" not in css
    assert r["family"] == "Anton" and r["role"] == "display" and "Anton-900.ttf" in r["files"]


@responses.activate
def test_set_font_text_prunes_old():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    _mock_family("Manrope", (400, 500, 600, 700, 800))
    fonts.set_font(d, "Manrope", "text")
    names = {p.name for p in (d / "fonts").iterdir()}
    assert not any(n.startswith("Inter-") for n in names)   # display has no @font-face of its own
    assert "OFL-inter.txt" not in names
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    assert tj["fonts"]["text"] == "Manrope-500.ttf" and tj["fonts"]["bold"] == "Manrope-800.ttf"
    assert '--font-display: "Manrope"' in _tokens(d)
    assert tj["fonts"]["black"].startswith("Manrope-") and (d / "fonts" / tj["fonts"]["black"]).exists()
    assert tj["direction"]["fonts"] == {"display": "Manrope", "text": "Manrope"}


@responses.activate
def test_set_font_text_keeps_display_font():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    _mock_family("Anton", (400, 900))
    _mock_family("Manrope", (400, 500, 800))
    fonts.set_font(d, "Anton", "display")
    fonts.set_font(d, "Manrope", "text")
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    assert '--font-display: "Anton"' in _tokens(d) and tj["fonts"]["black"] == "Anton-900.ttf"
    assert (d / "fonts" / "Anton-900.ttf").exists()
    assert tj["direction"]["fonts"] == {"display": "Anton", "text": "Manrope"}


def test_set_font_duplicate_block():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    css = _tokens(d)
    (d / "tokens.css").write_text(css + css[:css.index("/* cutmate:font display")], encoding="utf-8")
    with pytest.raises(CutmateError, match="2 'cutmate:font text' blocks"):
        fonts.set_font(d, "Anton", "text")


@responses.activate
def test_set_font_leaves_no_temp_in_draft():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    before = sorted(p.name for p in d.iterdir())
    _mock_family("Anton", (400, 900))
    fonts.set_font(d, "Anton", "display")
    assert sorted(p.name for p in d.iterdir()) == before


@responses.activate
def test_set_font_text_then_display_same_family_shares_files():
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    _mock_family("Anton", (400, 900))
    fonts.set_font(d, "Anton", "text")
    fonts.set_font(d, "Anton", "display")
    css = _tokens(d)
    assert '--font: "Anton"' in css and '--font-display: "Anton"' in css
    assert (d / "fonts" / "Anton-400.ttf").exists() and (d / "fonts" / "OFL-anton.txt").exists()


@responses.activate
def test_set_font_rejects_missing_polish(tmp_path):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    opts = subset.Options()
    f = TTFont(plugin_root() / "themes" / "clean" / "fonts" / "Inter-Black.ttf")
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=range(0x20, 0x7F))
    sub.subset(f)
    out = tmp_path / "ascii.ttf"
    f.save(out)
    themes.new_theme("mine")
    d = themes.draft_dir("mine")
    before_css, before_files = _tokens(d), sorted(p.name for p in (d / "fonts").iterdir())
    _mock_family("Anton", (400, 900))
    responses.replace(responses.GET, GSTATIC, body=out.read_bytes(), status=200)
    with pytest.raises(CutmateError, match="Polish"):
        fonts.set_font(d, "Anton", "display")
    assert _tokens(d) == before_css
    assert sorted(p.name for p in (d / "fonts").iterdir()) == before_files


@responses.activate
def test_set_font_not_ofl():
    themes.new_theme("mine")
    responses.add(responses.GET, fonts.OFL_URL.format(slug="anton"), status=404)
    with pytest.raises(CutmateError, match="not an OFL font"):
        fonts.set_font(themes.draft_dir("mine"), "Anton", "display")


@responses.activate
def test_set_font_no_weight_found():
    themes.new_theme("mine")
    _mock_family("Anton", ())
    with pytest.raises(CutmateError, match="not found on Google Fonts"):
        fonts.set_font(themes.draft_dir("mine"), "Anton", "display")


@responses.activate
def test_set_font_network_error():
    themes.new_theme("mine")
    responses.add(responses.GET, fonts.OFL_URL.format(slug="anton"), body="OFL")
    responses.add(responses.GET, re.compile(re.escape(fonts.CSS2) + ".*"), body=requests.ConnectionError("down"))
    with pytest.raises(CutmateError, match="cannot reach Google Fonts"):
        fonts.set_font(themes.draft_dir("mine"), "Anton", "display")


def test_set_font_bad_role():
    themes.new_theme("mine")
    with pytest.raises(CutmateError, match="role"):
        fonts.set_font(themes.draft_dir("mine"), "Anton", "bold")


def test_theme_font_cli_needs_draft():
    assert main(["theme", "font", "nope", "Anton", "--role", "display"]) == 2


@pytest.mark.net
def test_font_pairs_download(tmp_path):
    families = sorted({f for pair in directions.FONT_PAIRS for f in pair})
    bad = []
    for fam in families:
        try:
            r = fonts.download_family(fam, tmp_path / fonts.slug(fam))
            assert r["files"] and all(fonts.has_glyphs(p) for p in r["files"].values())
        except (CutmateError, AssertionError) as e:
            bad.append(f"{fam}: {e}")
    assert not bad, bad
