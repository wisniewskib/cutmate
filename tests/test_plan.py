import json

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
