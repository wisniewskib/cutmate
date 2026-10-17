import json
from pathlib import Path

import pytest

from cutmate.errors import PlanError
from cutmate.plan import load_plan, norm, resolve_anchor

WORDS = [
    {"seg": "S1", "word": "Mówić", "start": 0.10, "end": 0.40},
    {"seg": "S1", "word": "krótko,", "start": 0.45, "end": 0.80},
    {"seg": "S1", "word": "mniej", "start": 0.90, "end": 1.10},
    {"seg": "S1", "word": "mniej", "start": 1.50, "end": 1.70},
    {"seg": "S2", "word": "minus", "start": 4.00, "end": 4.30},
    {"seg": "S2", "word": "75%", "start": 4.40, "end": 5.00},
    {"seg": "S2", "word": "Claude'a.", "start": 5.10, "end": 5.60},
    {"seg": "S2", "word": "koniec.", "start": 9.60, "end": 9.95},
]
TIMED = [{"id": "S1", "start": 0.0, "end": 3.5, "text": "x"}, {"id": "S2", "start": 3.5, "end": 10.0, "text": "y"}]


def make_out(tmp_path, plan, words=WORDS):
    out = tmp_path / "rec" / "out"
    (out / "work").mkdir(parents=True)
    (out / "work" / "aligned_words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return out


def test_norm():
    assert norm("Claude'a.") == "claude'a"
    assert norm("„Krótko,\u201d") == "krótko"
    assert norm("\u201dx\u201d") == "x"
    assert norm("\u201cx\u201d") == "x"
    assert norm("75%") == "75%"


def test_anchor_normalisation():
    assert resolve_anchor("S2:claude'a", WORDS, 10.0) == (5.10, 5.60)
    assert resolve_anchor("S1:KRÓTKO", WORDS, 10.0) == (0.45, 0.80)
    assert resolve_anchor("S1:mniej#2", WORDS, 10.0) == (1.50, 1.70)
    assert resolve_anchor(4.2, WORDS, 10.0) == (4.2, 4.2)


def test_anchor_wrong_word_lists_words():
    with pytest.raises(PlanError, match="Mówić krótko, mniej mniej"):
        resolve_anchor("S1:dlugo", WORDS, 10.0)
    with pytest.raises(PlanError, match="#3"):
        resolve_anchor("S1:mniej#3", WORDS, 10.0)
    with pytest.raises(PlanError, match="segments: S1, S2"):
        resolve_anchor("S9:x", WORDS, 10.0)
    with pytest.raises(PlanError, match="outside"):
        resolve_anchor(12.0, WORDS, 10.0)


def test_load_plan_times_and_defaults(tmp_path):
    out = make_out(tmp_path, {
        "captions": {"key": ["claude"]},
        "graphics": [
            {"type": "counter", "at": "S2:75%", "to": 75, "suffix": "%", "label": "TOKENÓW", "hit": True},
            {"type": "stamp", "at": "S1:krótko", "text": "KRÓTKO", "until": "S1:mniej#2"},
            {"type": "list", "items": [{"text": "a", "at": "S1:mniej"}, {"text": "b", "at": "S1:mniej#2"}]},
        ]})
    p = load_plan(out)
    assert [g.type for g in p.graphics] == ["stamp", "list", "counter"]
    stamp, lst, counter = p.graphics
    assert (stamp.start, stamp.end) == (0.45, 1.70)
    assert lst.start == 0.90 and lst.end == pytest.approx(1.50 + 2.5)
    assert [i["at"] for i in lst.params["items"]] == [0.90, 1.50]
    assert counter.start == 4.40 and counter.end == pytest.approx(6.90) and counter.hit
    assert counter.params == {"to": 75, "suffix": "%", "label": "TOKENÓW"}
    assert p.captions == {"key": ["CLAUDE"], "max_words": 3}
    assert p.end == 10.0


def test_default_end_stops_before_next_graphic(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "chip", "at": "S2:minus", "text": "A"},
        {"type": "chip", "at": "S2:75%", "text": "B"}]})
    a, b = load_plan(out).graphics
    assert a.end == pytest.approx(4.35)


def test_end_clamped_to_video(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "stamp", "at": "S2:koniec", "text": "KONIEC", "until": 9.99}]})
    g = load_plan(out).graphics[0]
    assert g.end == pytest.approx(9.95) and g.end > g.start


def test_split_and_media(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "split", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/zrzut ekranu ą.png"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "zrzut ekranu ą.png").write_bytes(b"x")
    g = load_plan(out).graphics[0]
    assert (g.start, g.end) == (4.00, 5.60)
    assert g.params["media"] == str(out.parent / "broll" / "zrzut ekranu ą.png")
    assert "to" not in g.params and "from" not in g.params


def test_split_fit(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "split", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png", "fit": "cover"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    assert load_plan(out).graphics[0].params["fit"] == "cover"
    p = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    p["graphics"][0]["fit"] = "stretch"
    (out / "plan.json").write_text(json.dumps(p), encoding="utf-8")
    with pytest.raises(PlanError, match="fit must be"):
        load_plan(out)


def test_split_order_validation(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "split", "from": "S2:75%", "to": "S2:minus", "media": "broll/x.png"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    with pytest.raises(PlanError, match="before the start"):
        load_plan(out)


def test_numeric_until_clamp(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "stamp", "at": "S2:koniec", "text": "KONIEC", "until": 10.5}]})
    g = load_plan(out).graphics[0]
    assert g.end == pytest.approx(9.95)


def test_anchor_fallback_percent(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "counter", "at": "S2:75", "to": 75, "label": "x"}]})
    g = load_plan(out).graphics[0]
    assert g.start == 4.40


def test_factcheck_digit_boundaries(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "counter", "at": "S2:75%", "to": 5, "label": "x"}]})
    (out / "factcheck.md").write_text('- „75%" ✅ OK\n', encoding="utf-8")
    w = load_plan(out, factcheck=True).warnings
    assert len(w) == 1 and "5" in w[0]


@pytest.mark.parametrize("graphic,msg", [
    ({"type": "spinner", "at": 1}, "unknown type"),
    ({"type": "counter", "at": "S2:75%", "to": 75}, "missing \"label\""),
    ({"type": "counter", "at": "S2:75%", "to": "dużo", "label": "x"}, "must be a number"),
    ({"type": "stamp", "at": "S1:mniej", "text": "DWA SŁOWA"}, "one word"),
    ({"type": "point", "at": "S1:mniej", "image": "a.png", "corner": "middle"}, "corner"),
    ({"type": "split", "from": "S2:minus", "to": "S2:75%", "media": "broll/missing.mp4"}, "media not found"),
    ({"type": "chip", "at": "S2:75%", "text": "x", "until": "S1:mniej"}, "before"),
    ({"type": "bars", "at": "S2:75%", "head": "h", "rows": [{"label": "a"}]}, "rows"),
    ({"type": "list", "items": []}, "items"),
    ({"type": "list", "items": [{"text": "a", "at": "S1:mniej"}] * 5}, "at most 4 items"),
    ({"type": "bars", "at": "S2:75%", "head": "h", "rows": [{"label": "a", "value": 1}] * 4}, "at most 3 rows"),
])
def test_validation_errors(tmp_path, graphic, msg):
    with pytest.raises(PlanError, match=msg):
        load_plan(make_out(tmp_path, {"graphics": [graphic]}))


def test_plan_file_errors(tmp_path):
    out = make_out(tmp_path, {})
    (out / "plan.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(PlanError, match="invalid JSON"):
        load_plan(out)
    (out / "plan.json").unlink()
    with pytest.raises(PlanError, match="not found"):
        load_plan(out)


@pytest.mark.parametrize("bad_input,msg", [
    ({"aligned_words": "invalid"}, "invalid JSON"),
    ({"aligned_words": [{"seg": "S1"}]}, "missing seg/word/start/end"),
    ({"aligned_words": [{"seg": "S1", "word": "x", "start": "bad", "end": 1.0}]}, "must be numbers"),
    ({"graphics": "not a list"}, "must be a list"),
    ({"captions": "not a dict"}, "must be a dict"),
    ({"captions": {"max_words": "not_int"}}, "must be an int"),
    ({"captions": {"key": "not_a_list"}}, "must be a list"),
])
def test_malformed_inputs(tmp_path, bad_input, msg):
    out = tmp_path / "rec" / "out"
    (out / "work").mkdir(parents=True)
    (out / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps({}), encoding="utf-8")

    if "aligned_words" in bad_input:
        if bad_input["aligned_words"] == "invalid":
            (out / "work" / "aligned_words.json").write_text("{oops", encoding="utf-8")
        else:
            (out / "work" / "aligned_words.json").write_text(json.dumps(bad_input["aligned_words"]), encoding="utf-8")
    else:
        (out / "work" / "aligned_words.json").write_text(json.dumps(WORDS), encoding="utf-8")

    if "graphics" in bad_input or "captions" in bad_input:
        plan_content = {}
        plan_content.update({k: v for k, v in bad_input.items() if k != "aligned_words"})
        (out / "plan.json").write_text(json.dumps(plan_content), encoding="utf-8")

    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_budget_warnings(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "title", "at": "S1:Mówić", "text": "A", "hit": True},
        {"type": "title", "at": "S1:mniej", "text": "B", "hit": True, "until": "S1:mniej#2"},
        {"type": "stamp", "at": "S1:mniej#2", "text": "C", "hit": True},
    ]})
    w = " | ".join(load_plan(out).warnings)
    assert "3 graphics with \"hit\"" in w and "2 titles" in w and "overlaps" in w


def test_factcheck_warning(tmp_path):
    out = make_out(tmp_path, {"graphics": [
        {"type": "counter", "at": "S2:75%", "to": 75, "label": "x"},
        {"type": "bars", "at": "S1:mniej", "head": "h", "rows": [{"label": "a", "value": 40}], "illustrative": True}]})
    (out / "factcheck.md").write_text('- 0:04 „minus 75%" ❌ BŁĄD — naprawdę 3%\n', encoding="utf-8")
    w = load_plan(out, factcheck=True).warnings
    assert len(w) == 1 and "75" in w[0] and "factcheck" in w[0]
    (out / "factcheck.md").write_text('- „minus 75%" ✅ OK\n', encoding="utf-8")
    assert load_plan(out, factcheck=True).warnings == []


@pytest.mark.parametrize("music", [[], "x", {}, {"volume": "loud"}, {"volume": True}, {"volume": 3},
                                   {"volume": 0.4, "src": 5}])
def test_bad_music_rejected(tmp_path, music):
    out = make_out(tmp_path, {"music": music})
    with pytest.raises(PlanError, match="music"):
        load_plan(out)


def test_good_music_accepted(tmp_path):
    out = make_out(tmp_path, {"music": {"volume": 0.45, "src": "a.mp3"}})
    assert load_plan(out).music == {"volume": 0.45, "src": "a.mp3"}


def test_norm_curly_apostrophe():
    assert norm("Claude’a") == "claude'a"


def make_out169(tmp_path, plan, words=WORDS):
    out = make_out(tmp_path, plan, words)
    (out / "edl.json").write_text(json.dumps({"format": "16:9", "segments": []}), encoding="utf-8")
    return out


def test_split_rejected_in_169(tmp_path):
    out = make_out169(tmp_path, {"graphics": [
        {"type": "split", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    with pytest.raises(PlanError, match="not available in 16:9"):
        load_plan(out)


def test_chapters_parsed_and_numbered(tmp_path):
    out = make_out169(tmp_path, {"chapters": [{"at": "S1:Mówić", "title": " Intro "},
                                              {"at": "S2:minus", "title": "Drugi „rozdział”"}]})
    p = load_plan(out)
    assert p.format == "16:9"
    assert p.chapters == [{"start": 0.1, "title": "Intro", "num": 1}, {"start": 4.0, "title": "Drugi „rozdział”", "num": 2}]


def test_chapters_warnings(tmp_path):
    out = make_out169(tmp_path, {"chapters": [{"at": "S1:Mówić", "title": "A"}, {"at": "S2:minus", "title": "B"}],
                                 "graphics": [{"type": "chip", "at": "S2:75%", "text": "X"}]})
    w = " | ".join(load_plan(out).warnings)
    assert "2 chapters" in w and "at least 3" in w
    assert "chapter 1 (A) lasts 4.0s" in w and "chapter 2 (B) lasts 6.0s" in w
    assert "chip at 4.4s starts under the chapter 2 plate" in w


@pytest.mark.parametrize("chapters, msg", [
    ([], "non-empty list"),
    ([{"at": "S1:Mówić"}], "needs \"at\" and \"title\""),
    ([{"at": "S1:Mówić", "title": "x" * 41}], "longer than 40"),
    ([{"at": "S2:minus", "title": "a"}, {"at": "S1:Mówić", "title": "b"}], "in order"),
])
def test_chapters_invalid(tmp_path, chapters, msg):
    out = make_out169(tmp_path, {"chapters": chapters})
    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_face(tmp_path):
    out = make_out169(tmp_path, {"face": {"S1": [0.4, 0.3]}})
    assert load_plan(out).face == {"S1": [0.4, 0.3]}


@pytest.mark.parametrize("face, msg", [({"S9": [0.5, 0.5]}, "no segment 'S9'"), ({"S1": [1.2, 0.5]}, "fractions 0–1"),
                                       ({"S1": [0.5]}, "fractions 0–1"), ([0.5, 0.5], "must be an object")])
def test_face_invalid(tmp_path, face, msg):
    out = make_out169(tmp_path, {"face": face})
    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_916_defaults(tmp_path):
    p = load_plan(make_out(tmp_path, {}))
    assert (p.format, p.chapters, p.face) == ("9:16", [], {})


def test_pip_and_lower_third_169(tmp_path):
    out = make_out169(tmp_path, {"graphics": [
        {"type": "lower-third", "at": "S1:Mówić", "name": "Anna", "role": "AI"},
        {"type": "pip", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    lt, pip = load_plan(out).graphics
    assert (lt.start, lt.end) == (0.1, 3.95)                   # lower-third holds 4 s, clamped before the pip
    assert pip.params["corner"] == "br" and pip.params["fit"] == "cover" and (pip.start, pip.end) == (4.0, 5.6)


@pytest.mark.parametrize("g, msg", [
    ({"type": "pip", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png", "corner": "tr"}, "corner must be br or bl"),
    ({"type": "pip", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png", "fit": "fill"}, "fit must be"),
    ({"type": "lower-third", "at": "S1:Mówić"}, "missing \"name\""),
])
def test_pip_lower_third_invalid(tmp_path, g, msg):
    out = make_out169(tmp_path, {"graphics": [g]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_pip_rejected_in_916(tmp_path):
    out = make_out(tmp_path, {"graphics": [{"type": "lower-third", "at": "S1:Mówić", "name": "B"}]})
    with pytest.raises(PlanError, match="not available in 9:16"):
        load_plan(out)


def test_chapter_one_late_warning(tmp_path):
    out = make_out169(tmp_path, {"chapters": [{"at": "S1:mniej", "title": "A"}, {"at": "S2:minus", "title": "B"}]})
    assert "WARN chapter 1 starts at 0.9s — it is listed as 00:00" in load_plan(out).warnings
    out = make_out169(tmp_path / "x", {"chapters": [{"at": "S1:Mówić", "title": "A"}, {"at": "S2:minus", "title": "B"}]})
    assert not any("chapter 1 starts" in w for w in load_plan(out).warnings)


def _tracks(out, face=(0.45, 0.3)):
    (out / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [[t / 10, face[0], face[1], 0.9] for t in range(0, 100)],
        "hand_left": [], "hand_right": [[4.0, 0.7, 0.6, 0.9], [4.5, 0.72, 0.6, 0.9]]}}), encoding="utf-8")


def test_custom_follow_and_timing(tmp_path):
    out = make_out169(tmp_path, {"graphics": [
        {"type": "custom", "name": "energy-ball", "from": "S2:minus", "to": "S2:Claude'a", "follow": "hand",
         "params": {"color": "#7dd3fc"}},
        {"type": "custom", "name": "logo-3d", "at": "S1:Mówić", "until": "S1:mniej"}]})
    _tracks(out)
    g1, g2 = load_plan(out).graphics
    assert (g1.type, g1.start) == ("custom", 0.1) and g1.params["name"] == "logo-3d"
    assert g2.params == {"name": "energy-ball", "follow": "hand", "params": {"color": "#7dd3fc"}}
    assert (g2.start, g2.end) == (4.0, 5.6)


@pytest.mark.parametrize("g, msg", [
    ({"type": "custom", "name": "Bad Name", "at": "S1:Mówić"}, "name must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "follow": "elbow"}, "follow must be one of"),
    ({"type": "custom", "name": "x"}, "needs \"at\" or \"from\"/\"to\""),
    ({"type": "bg", "from": "S2:minus", "to": "S2:koniec."}, "exactly one of \"media\" or \"effect\""),
    ({"type": "side", "from": "S2:minus", "to": "S2:koniec.", "effect": "x", "speaker": "up"}, "speaker must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "region": [0, 0, 100]}, "region must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "region": [-1, 0, 100, 100]}, "region must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "region": [0, 0, 0, 100]}, "region must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "region": [0, 0, True, 100]}, "region must be"),
    ({"type": "custom", "name": "x", "at": "S1:Mówić", "region": "left"}, "region must be"),
])
def test_effects_invalid(tmp_path, g, msg):
    out = make_out169(tmp_path, {"graphics": [g]})
    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_follow_needs_tracks(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "x", "at": "S1:Mówić", "follow": "face"}]})
    with pytest.raises(PlanError, match="cutmate track"):
        load_plan(out)


def test_side_and_bg_effect_expansion(tmp_path):
    out = make_out169(tmp_path, {"graphics": [
        {"type": "side", "from": "S2:minus", "to": "S2:koniec.", "effect": "diagram", "speaker": "right"},
        {"type": "bg", "from": "S1:Mówić", "to": "S1:mniej#2", "effect": "space"}]})
    pl = load_plan(out)
    gs = pl.graphics
    assert [(g.type, g.params.get("name")) for g in gs] == [("custom", "space"), ("bg", None),
                                                             ("custom", "diagram"), ("side", None)]
    assert gs[2].params["region"] == [60, 60, 840, 960] and "region" not in gs[0].params
    assert gs[0].params["_fade"] == 0.3 and gs[2].params["_fade"] == 0.45
    assert gs[1].params["effect"] == "space" and gs[3].params["speaker"] == "right"
    assert gs[0].start == gs[1].start and gs[0].end == gs[1].end
    assert not any("overlaps" in w for w in pl.warnings)


def test_side_only_169(tmp_path):
    out = make_out(tmp_path, {"graphics": [{"type": "side", "from": "S2:minus", "to": "S2:koniec.", "effect": "x"}]})
    with pytest.raises(PlanError, match="not available in 9:16"):
        load_plan(out)


def test_auto_face_from_tracks(tmp_path):
    out = make_out169(tmp_path, {"face": {"S1": [0.2, 0.2]}})
    _tracks(out, face=(0.45, 0.3))
    assert load_plan(out).face == {"S1": [0.2, 0.2], "S2": [0.45, 0.3]}


def test_bg_budget_warning(tmp_path):
    words = WORDS + [{"seg": "S2", "word": "dalej", "start": 45.0, "end": 45.5}]
    out = make_out169(tmp_path, {"graphics": [{"type": "bg", "from": "S2:minus", "to": "S2:dalej", "media": "broll/k.png"}]},
                      words=words)
    (out / "work" / "edl_timed.json").write_text(json.dumps(
        [{"id": "S1", "start": 0.0, "end": 3.5}, {"id": "S2", "start": 3.5, "end": 50.0}]), encoding="utf-8")
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "k.png").write_bytes(b"x")
    assert any("bg covers 42s" in w for w in load_plan(out).warnings)


def _stale(out):
    import os
    t = (out / "work" / "tracks.json").stat().st_mtime
    (out / "aroll.mp4").write_bytes(b"x")
    os.utime(out / "aroll.mp4", (t + 5, t + 5))


def test_follow_with_stale_tracks(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "x", "at": "S1:Mówić", "follow": "face"}]})
    _tracks(out)
    _stale(out)
    with pytest.raises(PlanError, match=r"tracks.json is older than aroll.mp4 — run `cutmate track`"):
        load_plan(out)


def test_auto_face_ignores_stale_tracks(tmp_path):
    out = make_out169(tmp_path, {"face": {"S1": [0.2, 0.2]}})
    _tracks(out, face=(0.45, 0.3))
    assert load_plan(out).tracks is not None
    _stale(out)
    pl = load_plan(out)
    assert pl.face == {"S1": [0.2, 0.2]} and pl.tracks is None


def test_load_plan_relative_out(tmp_path, monkeypatch):
    out = make_out(tmp_path, {"graphics": [
        {"type": "split", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/x.png"}]})
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "x.png").write_bytes(b"x")
    monkeypatch.chdir(out)
    g = load_plan(Path(".")).graphics[0]
    assert g.params["media"] == str((out.parent / "broll" / "x.png").resolve())


def _point_tracks(out, x=0.8, y=0.4, t0=3.8, t1=4.6):
    (out / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [[t / 10, 0.45, 0.3, 0.9] for t in range(0, 100)],
        "point_right": [[round(t0 + i * 0.1, 2), x, y, 0.9] for i in range(int((t1 - t0) * 10) + 1)]}}), encoding="utf-8")


def test_split_effect_expansion(tmp_path):
    out = make_out(tmp_path, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:koniec.", "effect": "diagram"}]})
    pl = load_plan(out)
    a, b = pl.graphics
    assert (a.type, b.type) == ("split", "custom")
    assert a.params["effect"] == "diagram" and "media" not in a.params
    assert b.params == {"name": "diagram", "_slide": 900, "region": [40, 40, 1000, 820]}  # rides with the 900 px panel
    assert (a.start, a.end) == (b.start, b.end)
    assert not any("overlaps" in w for w in pl.warnings)


def test_split_media_and_effect_exclusive(tmp_path):
    for extra in ({}, {"media": "x.png", "effect": "d"}):
        out = make_out(tmp_path / str(len(extra)), {"graphics": [dict({"type": "split", "from": "S2:minus", "to": "S2:koniec."}, **extra)]})
        with pytest.raises(PlanError, match='exactly one of "media" or "effect"'):
            load_plan(out)


def test_place_gesture_resolves(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "arrow", "at": "S2:minus", "place": "gesture"}]})
    _point_tracks(out)
    g = load_plan(out).graphics[0]
    assert g.params["place_xy"] == [0.8, 0.4]


def test_place_gesture_without_gesture_warns(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "chip", "text": "tu", "at": "S2:minus", "place": "gesture"}]})
    _point_tracks(out, t0=8.0, t1=8.5)
    pl = load_plan(out)
    assert "place_xy" not in pl.graphics[0].params
    assert "WARN chip at 4.0s: no pointing gesture near the anchor — default position" in pl.warnings


def test_place_gesture_needs_fresh_tracks(tmp_path):
    g = {"graphics": [{"type": "custom", "name": "arrow", "at": "S2:minus", "place": "gesture"}]}
    out = make_out169(tmp_path / "a", g)
    with pytest.raises(PlanError, match=r"needs out/work/tracks.json \(fresh\) — run `cutmate track`"):
        load_plan(out)
    out = make_out169(tmp_path / "b", g)
    _point_tracks(out)
    _stale(out)
    with pytest.raises(PlanError, match=r"needs out/work/tracks.json \(fresh\) — run `cutmate track`"):
        load_plan(out)


def test_side_speaker_gesture(tmp_path):
    g = {"type": "side", "from": "S2:minus", "to": "S2:koniec.", "effect": "diagram", "speaker": "gesture"}
    out = make_out169(tmp_path / "a", {"graphics": [g]})
    _point_tracks(out, x=0.2)
    gs = load_plan(out).graphics
    assert gs[1].params["speaker"] == "right" and gs[0].params["region"] == [60, 60, 840, 960]
    out = make_out169(tmp_path / "b", {"graphics": [g]})
    _point_tracks(out, x=0.8)
    gs = load_plan(out).graphics
    assert gs[1].params["speaker"] == "left" and gs[0].params["region"] == [1020, 60, 840, 960]
    out = make_out169(tmp_path / "c", {"graphics": [g]})
    _point_tracks(out, t0=8.0, t1=8.5)
    pl = load_plan(out)
    assert pl.graphics[1].params["speaker"] == "right"
    assert any(w.startswith("WARN side at 4.0s: no pointing gesture") for w in pl.warnings)


def test_custom_media_param_resolved(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "card", "at": "S2:minus", "media": "broll/a.png"}]})
    with pytest.raises(PlanError, match=r"media not found: .*broll/a.png"):
        load_plan(out)
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "a.png").write_bytes(b"x")
    assert load_plan(out).graphics[0].params["media"] == str(out.parent / "broll" / "a.png")


def test_effect_params_forwarded_to_expanded_custom(tmp_path):
    gs = [{"type": "split", "from": "S2:minus", "to": "S2:koniec.", "effect": "stat-card", "params": {"value": 75}}]
    custom = load_plan(make_out(tmp_path / "a", {"graphics": gs})).graphics[1]
    assert custom.params["params"] == {"value": 75}
    with pytest.raises(PlanError, match='"params" must be an object'):
        load_plan(make_out(tmp_path / "b", {"graphics": [dict(gs[0], params=[1])]}))


def test_effect_params_media_resolved(tmp_path):
    gs = [{"type": "split", "from": "S2:minus", "to": "S2:koniec.", "effect": "stat-card",
           "params": {"value": 75, "media": "broll/a.png"}}]
    out = make_out(tmp_path, {"graphics": gs})
    with pytest.raises(PlanError, match=r"media not found: .*broll/a.png"):
        load_plan(out)
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "a.png").write_bytes(b"x")
    split, custom = load_plan(out).graphics
    assert custom.params["params"] == {"value": 75, "media": str(out.parent / "broll" / "a.png")}
    raw = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert raw["graphics"][0]["params"]["media"] == "broll/a.png"
    out = make_out169(tmp_path / "c", {"graphics": [{"type": "custom", "name": "stat-card", "at": "S2:minus",
                                                      "params": {"media": "shot.png"}}]})
    (out.parent / "shot.png").write_bytes(b"x")
    assert load_plan(out).graphics[0].params["params"]["media"] == str(out.parent / "shot.png")


@pytest.mark.parametrize("g, msg", [
    ({"type": "title", "at": "S2:minus", "text": "X", "place": "gesture"}, '"place" works only on custom and chip'),
    ({"type": "chip", "at": "S2:minus", "text": "X", "place": "left"}, 'place must be "gesture"'),
    ({"type": "custom", "name": "x", "at": "S2:minus", "place": [1, 2]}, 'place must be "gesture"'),
    ({"type": "chip", "at": "S2:minus", "text": "X", "speaker": "gesture"}, 'speaker "gesture" works only on side'),
])
def test_place_and_speaker_validated(tmp_path, g, msg):
    out = make_out169(tmp_path, {"graphics": [g]})
    _point_tracks(out)
    with pytest.raises(PlanError, match=msg):
        load_plan(out)


def test_no_pointing_data_warns(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "chip", "text": "tu", "at": "S2:minus", "place": "gesture"}]})
    _tracks(out)                                               # pre-2d tracks.json: face and hands, no point_* tracks
    pl = load_plan(out)
    assert "place_xy" not in pl.graphics[0].params
    assert "WARN tracks.json has no pointing data — run `cutmate track --force`" in pl.warnings


def test_glb_shape_needs_glb_media(tmp_path):
    def plan_with(**kw):
        g = dict({"type": "custom", "name": "showcase-3d", "at": "S2:minus", "params": {"shape": "glb"}}, **kw)
        out = make_out169(tmp_path / str(len(list(tmp_path.iterdir()))), {"graphics": [g]})
        for f in ("a.png", "a.glb"):
            (out.parent / f).write_bytes(b"x")
        return load_plan(out).warnings
    msg = 'WARN custom at 4.0s: shape "glb" needs a .glb / .gltf "media" — it falls back to the torus knot'
    assert msg in plan_with(media="a.png")
    assert msg in plan_with()
    assert not any("glb" in w for w in plan_with(media="a.glb"))
    assert not any("glb" in w for w in plan_with(params={"shape": "glb", "model": "robot.glb"}))
    assert not any("glb" in w for w in plan_with(params={"shape": "torus-knot"}, media="a.png"))


def _hand_tracks(out, palm=None, finger=None, t0=3.8, t1=4.6):
    n = int((t1 - t0) * 10) + 1
    ts = [round(t0 + i * 0.1, 2) for i in range(n)]
    tr = {"face": [[t / 10, 0.45, 0.3, 0.9] for t in range(0, 100)], "point_left": [], "point_right": [],
          "palm_left": [], "palm_right": [], "finger_left": [], "finger_right": []}
    if palm:
        tr["palm_right"] = [[t, palm[0], palm[1], palm[2]] for t in ts]
    if finger:
        tr["finger_right"] = [[t, finger[0], finger[1], finger[2]] for t in ts]
    (out / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": tr}), encoding="utf-8")


def test_place_gesture_open_palm_follows_the_hand(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "showcase-3d", "at": "S2:minus", "place": "gesture"}]})
    _hand_tracks(out, palm=(0.2, 0.78, 1.0), finger=(0.05, 0.78, 0.0))
    pl = load_plan(out)
    g = pl.graphics[0]
    assert g.params["place_xy"] == [0.2, 0.78] and g.params["place_track"] == "palm_right"
    assert not any("hand-shape" in w for w in pl.warnings)


def test_place_gesture_index_point_uses_the_target(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "burst", "at": "S2:minus", "place": "gesture"}]})
    _hand_tracks(out, palm=(0.6, 0.6, 0.0), finger=(0.66, 0.5, 1.0))
    g = load_plan(out).graphics[0]
    assert g.params["place_xy"] == [0.66, 0.5] and "place_track" not in g.params


def test_place_gesture_warns_without_hand_shapes(tmp_path):
    out = make_out169(tmp_path, {"graphics": [{"type": "custom", "name": "arrow", "at": "S2:minus", "place": "gesture"}]})
    _point_tracks(out)
    pl = load_plan(out)
    assert pl.graphics[0].params["place_xy"] == [0.8, 0.4]
    assert "WARN tracks.json has no hand-shape data (open palm / index point) — run `cutmate track --force`" in pl.warnings
