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


def test_rmtree_failure_is_one_line_and_keeps_state(monkeypatch):
    _stamped()
    themes.save_theme("mine")
    _, d = _stamped()
    monkeypatch.setattr(themes.shutil, "rmtree", lambda *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(CutmateError, match="cannot delete"):
        themes.new_theme("mine")
    assert (d / "theme.json").exists() and themes.stamp_ok(d)


def test_save_target_without_theme_json_needs_force_and_is_backed_up():
    fonts = config.home() / "themes" / "mine" / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "x.ttf").write_text("f", encoding="utf-8")
    _stamped()
    with pytest.raises(CutmateError, match="--force"):
        themes.save_theme("mine")
    themes.save_theme("mine", force=True)
    (b,) = (config.home() / "themes" / ".backup").glob("mine-*")
    assert (b / "fonts" / "x.ttf").read_text(encoding="utf-8") == "f"
    assert not (config.home() / "themes" / "mine" / "fonts" / "x.ttf").exists()


def test_save_failure_keeps_old_theme(monkeypatch):
    _stamped()
    themes.save_theme("mine")
    t = config.home() / "themes" / "mine"
    before = (t / "tokens.css").read_bytes()
    _, d = _stamped()
    (d / "tokens.css").write_text("new", encoding="utf-8")
    themes.write_stamp(d)
    real = themes.os.replace

    def boom(src, dst):
        if str(dst) == str(t):
            raise OSError("disk says no")
        return real(src, dst)
    monkeypatch.setattr(themes.os, "replace", boom)
    with pytest.raises(CutmateError, match="backup"):
        themes.save_theme("mine", force=True)
    assert (t / "tokens.css").read_bytes() == before
    assert not list((config.home() / "themes").glob(".mine.saving-*"))


def test_only_top_level_check_and_custom_are_skipped():
    src = themes.new_theme("base")
    b = themes.draft_dir("base")
    (b / "fonts" / "check").mkdir()
    (b / "fonts" / "check" / "k.txt").write_text("k", encoding="utf-8")
    (b / "components" / "custom").mkdir()
    themes.write_stamp(b)
    themes.new_theme("copy", base="base")
    c = themes.draft_dir("copy")
    assert (c / "fonts" / "check" / "k.txt").exists() and not (c / "check").exists()
    assert not (c / "components" / "custom").exists()
    (c / "fonts" / "custom").mkdir()
    themes.write_stamp(c)
    t = themes.save_theme("copy")
    assert (t / "fonts" / "custom").is_dir() and (t / "check" / "check.json").exists()


def test_new_from_itself_keeps_draft():
    themes.new_theme("mine")
    (themes.draft_dir("mine") / "tokens.css").write_text("kept", encoding="utf-8")
    themes.new_theme("mine", base="mine")
    assert (themes.draft_dir("mine") / "tokens.css").read_text(encoding="utf-8") == "kept"
    assert [t["name"] for t in themes.list_themes()].count("mine") == 1


def test_stamp_needs_current_hyperframes_version(monkeypatch):
    _, d = _stamped()
    assert themes.stamp_ok(d)
    monkeypatch.setattr(themes, "HF_VERSION", "9.9.9")
    assert not themes.stamp_ok(d)


@pytest.mark.parametrize("bad", ["Clean", "con", "NUL", "com1", "LPT9", "x.", "x "])
def test_check_name_rejects_system_and_case_clashes(bad):
    with pytest.raises(CutmateError):
        themes.check_name(bad)


def test_use_theme_rejects_abs_path(tmp_path):
    with pytest.raises(CutmateError):
        themes.use_theme(str(tmp_path))
    with pytest.raises(CutmateError):
        config.set_values([f"theme={tmp_path}"])


# ---- theme check: lint, contact sheet, stamp -------------------------------------------------------------------

def _edit(d, rel, fn):
    p = d / rel
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")


def test_lint_clean_draft_ok():
    themes.new_theme("d")
    assert themes.lint_theme(themes.draft_dir("d"), "d") == []


def test_lint_bundled_clean_ok():
    assert themes.lint_theme(plugin_root() / "themes" / "clean", "clean") == []


def _rm_stamp(d):
    (d / "components" / "stamp.html").unlink()


def _title_random(d):
    _edit(d, "components/title.html", lambda t: t.replace("tl.", "Math.random(); tl.", 1))


def _import_http(d):
    _edit(d, "tokens.css", lambda t: '@import url("https://fonts.googleapis.com/css2?family=X");\n' + t)


def _accent(d):
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    tj["accent"] = "#000000"
    (d / "theme.json").write_text(json.dumps(tj), encoding="utf-8")


def _contrast(d):
    _edit(d, "tokens.css", lambda t: t.replace("--card: rgba(255, 255, 255, 0.94);", "--card: #111111;")
          .replace("--ink: #0f172a;", "--ink: #222222;"))


def _sfx(d):
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    tj["sfx"]["stamp"] = [["boom", 0, 0.4]]
    (d / "theme.json").write_text(json.dumps(tj), encoding="utf-8")


def _frame_name(d):
    _edit(d, "frame.md", lambda t: t.replace("name: d", "name: other", 1))


def _on_accent(d):
    tj = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    tj["direction"]["palette"] = {"on_accent": "#7dd3fd"}  # same as --accent: unreadable text on the accent
    (d / "theme.json").write_text(json.dumps(tj), encoding="utf-8")


def _no_token(d):
    _edit(d, "tokens.css", lambda t: t.replace("--shadow:", "--shade:"))


def _no_frame_sel(d):
    _edit(d, "theme.css", lambda t: t.replace("#captions", "#caps"))


def _missing_font(d):
    (d / "fonts" / "Inter-Black.ttf").unlink()


@pytest.mark.parametrize("edit, expect", [
    (_rm_stamp, "stamp"), (_title_random, "Math.random"), (_import_http, "http"), (_accent, "accent"),
    (_contrast, "contrast"), (_sfx, "boom"), (_frame_name, "frame.md"), (_on_accent, "on_accent"),
    (_no_token, "--shadow"), (_no_frame_sel, "#captions"), (_missing_font, "Inter-Black.ttf")])
def test_lint_problems(edit, expect):
    themes.new_theme("d")
    d = themes.draft_dir("d")
    edit(d)
    problems = themes.lint_theme(d, "d")
    assert any(expect in p for p in problems), problems


def test_lint_accepts_f169_override_pattern():
    themes.new_theme("d")
    d = themes.draft_dir("d")
    assert "html.f169 ROOT" in (d / "components" / "counter.html").read_text(encoding="utf-8")
    assert themes.lint_theme(d, "d") == []


def test_lint_random_must_not_look_like_clean():
    themes.new_theme("r", mode="random", seed=1)
    problems = themes.lint_theme(themes.draft_dir("r"), "r")
    assert any("looks like clean" in p for p in problems), problems


def _fake_check(monkeypatch, tmp_path):
    from PIL import Image

    def fake(theme, workdir=None, language="pl", fmt="9:16", clip=None):
        d = tmp_path / ("fake-" + fmt.replace(":", "x"))
        d.mkdir(exist_ok=True)
        snaps, labels = [], []
        for i, (ty, kind) in enumerate([("title", "entrance"), ("title", "settled"), ("counter", "settled")]):
            p = d / f"s{i}.png"
            Image.new("RGB", (270, 480) if fmt == "9:16" else (480, 270), "#336699").save(p)
            snaps.append(p)
            labels.append((float(i), ty, kind))
        sheet = d / "sheet.png"
        Image.new("RGB", (100, 100), "red").save(sheet)
        return {"sheet": sheet, "snapshots": snaps, "labels": labels, "times": [l[0] for l in labels]}
    monkeypatch.setattr("cutmate.theme_check.theme_check", fake)


def test_check_theme_writes_contact_and_stamp(tmp_path, monkeypatch):
    from PIL import Image
    _fake_check(monkeypatch, tmp_path)
    themes.new_theme("d")
    d = themes.draft_dir("d")
    r = themes.check_theme("d")
    assert r["kind"] == "draft" and r["contact"] == d / "check" / "contact.png"
    assert Image.open(r["contact"]).width == 1620
    assert (d / "check" / "sheet-9x16.png").exists() and (d / "check" / "sheet-16x9.png").exists()
    assert set(r["sheets"]) == {"9:16", "16:9"}
    assert themes.stamp_ok(d)


def test_check_lint_failure_is_one_line_and_unstamped(tmp_path, monkeypatch):
    _fake_check(monkeypatch, tmp_path)
    themes.new_theme("d")
    d = themes.draft_dir("d")
    _rm_stamp(d)
    with pytest.raises(CutmateError) as e:
        themes.check_theme("d")
    assert "\n" not in str(e.value) and "fails lint" in str(e.value)
    assert not themes.stamp_ok(d)


def test_check_bundled_goes_to_home(tmp_path, monkeypatch):
    _fake_check(monkeypatch, tmp_path)
    before = sorted(p for p in (plugin_root() / "themes" / "clean").rglob("*"))
    r = themes.check_theme("clean")
    assert r["kind"] == "bundled"
    assert r["contact"] == config.home() / "checks" / "clean" / "contact.png" and r["contact"].exists()
    assert sorted(p for p in (plugin_root() / "themes" / "clean").rglob("*")) == before


@pytest.mark.hf
def test_check_theme_draft_real():
    from PIL import Image
    themes.new_theme("d")
    r = themes.check_theme("d")
    assert Image.open(r["contact"]).width == 1620
    themes.save_theme("d")
