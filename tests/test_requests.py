import json

from cutmate.asks import check_requests, parse_requests

MD = """# Zrozumiałem tak
- [nagranie IMG_0137 26.6] "w boksie w prawym dolnym rogu" → pip @ S2
- [czat] kula energii na dłoni → custom:orb @ S2:75%
- [nagranie IMG_0137 39.3] "Rasengan." → cut
- [uwagi 0:41] obiekt 3D obok → custom:cube @ S1
- [czat] twerk → skip
- zła linia bez strzałki
"""


def test_parse():
    r = parse_requests(MD)
    assert r[0] == {"source": "nagranie IMG_0137 26.6", "what": '"w boksie w prawym dolnym rogu"', "target": "pip", "anchor": "S2"}
    assert r[1]["target"] == "custom:orb" and r[1]["anchor"] == "S2:75%"
    assert r[2]["target"] == "cut" and r[2]["anchor"] is None
    assert "error" in r[5]


def test_check(tmp_path):
    out = tmp_path / "rec" / "out"
    (out / "work").mkdir(parents=True)
    words = [{"seg": "S1", "word": "a", "start": 0.1, "end": 0.4}, {"seg": "S2", "word": "75%", "start": 4.4, "end": 5.0}]
    (out / "work" / "aligned_words.json").write_text(json.dumps(words), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps([{"id": "S1", "start": 0, "end": 3.5}, {"id": "S2", "start": 3.5, "end": 10}]))
    (out / "edl.json").write_text('{"format": "16:9", "segments": []}')
    (out / "custom").mkdir()
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "custom", "name": "orb", "at": "S2:75%"},
        {"type": "pip", "from": "S2:75%", "to": "S2:75%", "media": "b.png"}]}))
    (out.parent / "b.png").write_bytes(b"x")
    (out / "requests.md").write_text(MD, encoding="utf-8")
    lines = check_requests(out)
    assert lines[0].startswith("OK") and lines[1].startswith("OK")
    assert lines[2].startswith("NOTE") and lines[4].startswith("NOTE")
    assert lines[3].startswith("MISSING") and "custom:cube" in lines[3]
    assert lines[5].startswith("BAD")
    assert check_requests(tmp_path / "empty") == []


def test_cli_requests(tmp_path, capsys):
    from cutmate.cli import main
    assert main(["requests", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "requests: 0 ok, 0 missing, 0 bad"


def test_corrupt_plan_is_one_line_error(tmp_path, capsys):
    from cutmate.cli import main
    (tmp_path / "work").mkdir()
    (tmp_path / "requests.md").write_text("- [x] a → pip @ S1\n", encoding="utf-8")
    (tmp_path / "plan.json").write_text("{nope")
    assert main(["requests", str(tmp_path)]) == 2
    assert capsys.readouterr().err.startswith("cutmate: ")


def _setup(tmp_path, md):
    out = tmp_path / "rec" / "out"
    (out / "work").mkdir(parents=True)
    words = [{"seg": "S1", "word": "a", "start": 0.1, "end": 0.4}, {"seg": "S2", "word": "75%", "start": 4.4, "end": 5.0}]
    (out / "work" / "aligned_words.json").write_text(json.dumps(words), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps([{"id": "S1", "start": 0, "end": 3.5}, {"id": "S2", "start": 3.5, "end": 10}]))
    (out / "edl.json").write_text('{"format": "16:9", "segments": []}')
    (out / "custom").mkdir()
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "pip", "from": "S2:75%", "to": "S2:75%", "media": "b.png"}]}))
    (out.parent / "b.png").write_bytes(b"x")
    (out / "requests.md").write_text(md, encoding="utf-8")
    return out


def test_unresolvable_anchors_are_bad_lines(tmp_path):
    out = _setup(tmp_path, "- [c] a → pip @ S9\n- [c] b → pip @ S2:nonexistent\n- [c] c → pip @ S2\n")
    lines = check_requests(out)
    assert lines[0].startswith("BAD") and lines[1].startswith("BAD")
    assert lines[2].startswith("OK")


def test_graphic_outside_window_is_missing(tmp_path):
    out = _setup(tmp_path, "- [c] a → pip @ S1\n")
    assert check_requests(out)[0].startswith("MISSING")


def test_time_anchors(tmp_path):
    out = _setup(tmp_path, "- [uwagi 0:04] a → pip @ 0:04\n- [uwagi] b → pip @ 4.9\n- [uwagi] c → pip @ 2.5\n"
                           "- [uwagi] d → pip @ 1:30\n")
    lines = check_requests(out)                                   # the pip starts at 4.4 s
    assert lines[0].startswith("OK") and lines[1].startswith("OK") and lines[2].startswith("MISSING")
    assert lines[3].startswith("BAD") and "outside the video" in lines[3]


def test_cli_summary_counts_bad(tmp_path, capsys):
    from cutmate.cli import main
    out = _setup(tmp_path, "- [c] a → pip @ S2\n- [c] b → pip @ S9\n- [c] c → pip @ S1\n- zła linia\n")
    assert main(["requests", str(out)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "requests: 1 ok, 1 missing, 2 bad"


def test_explainer_targets(tmp_path):
    md = ("- [czat] explainery → explainers\n"
          "- [czat] liczba → explainer @ S2\n"
          "- [czat] schemat → explainer @ S1\n"
          "- [niespodzianka] burst → custom:burst @ S2\n"
          "- [niespodzianka] kula → custom:orb @ S1\n")
    out = _setup(tmp_path, md)
    plan = json.loads((out / "plan.json").read_text())
    plan["graphics"] = [
        {"type": "side", "from": "S2:75%", "to": "S2:75%", "effect": "stat-card", "speaker": "right"},
        {"type": "side", "from": "S2:75%", "to": "S2:75%", "media": "b.png"},
        {"type": "custom", "name": "burst", "at": "S2:75%"}]
    (out / "plan.json").write_text(json.dumps(plan))
    lines = check_requests(out)
    assert lines[0].startswith("NOTE") and "explainers" in lines[0]
    assert lines[1].startswith("OK") and lines[2].startswith("MISSING")
    assert lines[3].startswith("SURPRISE OK")
    assert lines[4].startswith("SURPRISE MISSING")


def test_surprise_bad_note_and_summary(tmp_path, capsys):
    from cutmate.cli import main
    out = _setup(tmp_path, "- [niespodzianka] a → custom:x @ S1\n- [niespodzianka] b → cut\n"
                           "- [niespodzianka] c → pip @ S9\n- [niespodzianka] d → pip @ S2\n")
    lines = check_requests(out)
    assert [ln.split()[:2] for ln in lines] == [["SURPRISE", "MISSING"], ["SURPRISE", "NOTE"],
                                                ["SURPRISE", "BAD"], ["SURPRISE", "OK"]]
    assert main(["requests", str(out)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "requests: 1 ok, 1 missing, 1 bad"


def test_explainer_split_916(tmp_path):
    out = _setup(tmp_path, "- [czat] a → explainer @ S2\n- [czat] b → explainer @ S2:75%\n")
    (out / "edl.json").write_text('{"format": "9:16", "segments": []}')
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "split", "from": "S1:a", "to": "S1:a", "effect": "flow", "params": {}},
        {"type": "split", "from": "S2:75%", "to": "S2:75%", "media": "b.png"}]}))
    lines = check_requests(out)
    assert lines[0].startswith("MISSING") and lines[1].startswith("MISSING")
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "split", "from": "S2:75%", "to": "S2:75%", "effect": "flow", "params": {}}]}))
    assert all(ln.startswith("OK") for ln in check_requests(out))


def test_explainer_request_matches_panel_item(tmp_path):
    out = _setup(tmp_path, "- [czat] explainer → explainer @ S1\n- [czat] panel → panel @ S2\n"
                           "- [czat] zrzut → panel @ S1\n")
    (out / "edl.json").write_text('{"format": "9:16", "segments": []}')
    (out / "plan.json").write_text(json.dumps({"panel": [
        {"at": "S1:a", "effect": "stat-card", "params": {"value": 44}},
        {"at": "S2:75%", "media": "b.png"}]}))
    lines = check_requests(out)
    assert lines[0].startswith("OK") and lines[1].startswith("OK") and lines[2].startswith("OK")
    (out / "requests.md").write_text("- [czat] explainer → explainer @ S2\n", encoding="utf-8")
    assert check_requests(out)[0].startswith("MISSING")      # a panel screenshot is not an explainer


def test_word_anchor_matches_the_hit_of_an_effect(tmp_path):
    # the skill logs a requested burst-out on its impact word; the bg starts >= 1 s before that word
    out = _setup(tmp_path, "- [czat] klejnot → custom:burst-out @ S2:75%\n- [czat] b → custom:burst-out @ S1:a\n")
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "bg", "from": 2.0, "to": 7.0, "effect": "burst-out", "hit": "S2:75%"}]}))
    lines = check_requests(out)
    assert lines[0].startswith("OK"), lines
    assert lines[1].startswith("MISSING"), lines
