import json
import re
import shutil

import pytest

from conftest import make_clip
from cutmate import build as B
from cutmate import paths
from cutmate.plan import Graphic

WORDS = [
    {"seg": "S1", "word": "Mówić", "start": 0.10, "end": 0.40},
    {"seg": "S1", "word": "krótko,", "start": 0.45, "end": 0.80},
    {"seg": "S1", "word": "mniej", "start": 0.90, "end": 1.10},
    {"seg": "S2", "word": "minus", "start": 2.10, "end": 2.30},
    {"seg": "S2", "word": "75%", "start": 2.35, "end": 2.70},
    {"seg": "S2", "word": "Claude'a", "start": 2.75, "end": 3.10},
    {"seg": "S2", "word": "</script>", "start": 3.20, "end": 3.50},
]
TIMED = [{"id": "S1", "start": 0.0, "end": 2.0, "text": "a"}, {"id": "S2", "start": 2.0, "end": 4.0, "text": "b"}]
FAKE_COMPONENT = """<style>ROOT .band .x { color: red; }</style>
<markup><div class="band"><div class="x">{{label}}</div>{{media_tag}}</div></markup>
<script>
tl.fromTo(root.querySelector(".x"), { opacity: 0 }, { opacity: 1, duration: 0.2 }, P.at);
U.out(root.querySelector(".band"), P.end - 0.2);
</script>"""


@pytest.fixture
def theme(tmp_path, monkeypatch):
    """The real clean theme base + fake component files (real components arrive in Task 6)."""
    src = paths.plugin_root() / "themes" / "clean"
    dst = tmp_path / "home" / "themes" / "testtheme"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("components"))
    (dst / "components").mkdir()
    for t in ("title", "counter", "list", "chip", "stamp", "bars", "point", "split", "chapter"):
        (dst / "components" / f"{t}.html").write_text(FAKE_COMPONENT, encoding="utf-8")
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    return "testtheme"


@pytest.fixture
def out(tmp_path, monkeypatch):
    rec = tmp_path / "rec ą"
    o = rec / "out"
    (o / "work").mkdir(parents=True)
    make_clip(o / "aroll.mp4", dur=4.0, gaps=())
    (o / "work" / "aligned_words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (o / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")

    def fake_project(proj, fmt="9:16"):
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "hyperframes.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(B, "ensure_project", fake_project)
    return o


def write_plan(o, plan):
    (o / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")


def cfg_of(index_html):
    m = re.search(r"const CFG = (.*?);\n", index_html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_caption_pages_rules():
    pages = B.caption_pages(WORDS, 4.0, ["CLAUDE'A"])
    texts = [[w[0] for w in p["words"]] for p in pages]
    assert texts == [["Mówić", "krótko,"], ["mniej"], ["minus", "75%"], ["Claude'a"], ["</script>"]]
    assert pages[2]["words"][1][2] == "num" and pages[3]["words"][0][2] == "key"
    assert pages[0]["start"] == pytest.approx(0.06)
    assert pages[1]["end"] <= pages[2]["start"]
    assert all(p["end"] < 4.0 for p in pages)
    assert all(pages[i]["end"] <= pages[i + 1]["start"] for i in range(len(pages) - 1))


def test_caption_pages_no_overlap_short_gap():
    ws = [{"seg": "S1", "word": "No,", "start": 1.00, "end": 1.08},
          {"seg": "S1", "word": "dobra", "start": 1.12, "end": 1.40}]
    pages = B.caption_pages(ws, 4.0, [])
    assert len(pages) == 2 and pages[0]["end"] <= pages[1]["start"]


def test_caption_pages_skip_empty_words():
    ws = [{"seg": "S1", "word": "", "start": 0.0, "end": 0.1}, {"seg": "S1", "word": "  ", "start": 0.1, "end": 0.2},
          {"seg": "S1", "word": "ok", "start": 0.3, "end": 0.5}]
    assert [[w[0] for w in p["words"]] for p in B.caption_pages(ws, 4.0, [])] == [["ok"]]


def test_caption_key_matches_curly_apostrophe():
    ws = [{"seg": "S1", "word": "Claude\u2019a", "start": 0.0, "end": 0.3}]
    assert B.caption_pages(ws, 4.0, ["Claude'a"])[0]["words"][0][2] == "key"


def test_cam_and_hits():
    cam = B.cam_from_cuts(TIMED)
    assert cam == [[0.0, 1.0], [2.0, 1.12]]
    g = Graphic("stamp", 2.35, 3.0, {"text": "X"}, True, None, 0)
    h = B.hits_for([g], cam, TIMED, 4.0)
    assert h == [[2.35, 1.12, 0.5]]
    near_end = Graphic("stamp", 3.75, 3.95, {"text": "X"}, True, None, 0)
    assert B.hits_for([near_end], cam, TIMED, 4.0) == [[3.75, 1.12, 0]]


def test_build_writes_project(out, theme):
    write_plan(out, {"captions": {"key": ["claude'a"]}, "graphics": [
        {"type": "counter", "at": "S2:75%", "to": 75, "label": "TOKENÓW", "hit": True},
        {"type": "chip", "at": "S1:Mówić", "text": "Caveman"}]})
    r = B.build(out, theme=theme)
    proj = r["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert '<video id="aroll" src="assets/aroll.mp4"' in html and 'data-has-audio="true"' in html
    assert 'data-composition-src="compositions/gx-01-chip.html"' in html
    assert 'data-composition-src="compositions/gx-02-counter.html"' in html
    sub = (proj / "compositions" / "gx-02-counter.html").read_text(encoding="utf-8")
    assert '<div id="gx-02-counter" data-composition-id="gx-02-counter"' in sub
    assert "#gx-02-counter .band .x" in sub and 'window.__timelines["gx-02-counter"]' in sub
    assert "TOKENÓW" in sub
    cfg = cfg_of(html)
    assert cfg["hits"][0][0] == 2.35 and cfg["cam"][1] == [2.0, 1.12]
    assert len(cfg["pages"]) == 5
    for f in ("assets/aroll.mp4", "assets/tokens.css", "assets/theme.css", "assets/cutmate.js",
              "assets/fonts/Inter-Black.ttf"):
        assert (proj / f).exists(), f
    ids = re.findall(r'<audio id="([^"]+)"', html)
    assert len(ids) == len(set(ids)) >= 4   # chip pop, counter pop + ping, hit impact
    assert json.loads((out / "work" / "checkpoints.json").read_text()) == r["checkpoints"]


def test_markup_placeholder_escaped(out, theme):
    comp = paths.theme_dir(theme) / "components" / "chip.html"
    comp.write_text(comp.read_text(encoding="utf-8").replace("{{label}}", "{{text}}"), encoding="utf-8")
    write_plan(out, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "<b>&"}]})
    proj = B.build(out, theme=theme)["project"]
    sub = (proj / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    assert "&lt;b&gt;&amp;" in sub


def test_rebuild_prunes_unused_assets(out, theme):
    broll = out.parent / "broll"
    broll.mkdir()
    shutil.copy(out / "aroll.mp4", broll / "b.mp4")
    write_plan(out, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/b.mp4"}]})
    proj = B.build(out, theme=theme)["project"]
    assert list((proj / "assets" / "media").iterdir()) and list((proj / "assets" / "sfx").iterdir())
    write_plan(out, {"graphics": []})
    B.build(out, theme=theme)
    assert list((proj / "assets" / "media").iterdir()) == []
    assert list((proj / "assets" / "sfx").iterdir()) == []


@pytest.mark.parametrize("content", ["{not json", '{"sfx": {}}', '{"hit_sfx": ["impact", 0.3]}'])
def test_broken_theme_json_is_one_line_error(out, theme, content):
    from cutmate.errors import CutmateError
    write_plan(out, {"graphics": []})
    (paths.theme_dir(theme) / "theme.json").write_text(content, encoding="utf-8")
    with pytest.raises(CutmateError, match="theme.json"):
        B.build(out, theme=theme)


def test_text_with_script_tag_is_escaped(out, theme):
    write_plan(out, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "</script><b>&"}]})
    proj = B.build(out, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    sub = (proj / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    assert html.count("</script>") == html.count("<script")
    assert sub.count("</script>") == sub.count("<script")
    assert "<\\/script>" in html and "<\\/script>" in sub


def test_rebuild_prunes_stale_subcomps(out, theme):
    write_plan(out, {"graphics": [{"type": "chip", "at": "S1:Mówić", "text": "a"},
                                  {"type": "stamp", "at": "S2:minus", "text": "B"}]})
    proj = B.build(out, theme=theme)["project"]
    write_plan(out, {"graphics": [{"type": "stamp", "at": "S2:minus", "text": "B"}]})
    B.build(out, theme=theme)
    assert sorted(p.name for p in (proj / "compositions").glob("gx-*.html")) == ["gx-01-stamp.html"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    for src in re.findall(r'data-composition-src="([^"]+)"', html):
        assert (proj / src).exists()


def test_media_with_unicode_name_copied_ascii(out, theme):
    broll = out.parent / "broll"
    broll.mkdir()
    shutil.copy(out / "aroll.mp4", broll / "nagranie ekranu ą.mp4")
    write_plan(out, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:Claude'a",
                                   "media": "broll/nagranie ekranu ą.mp4"}]})
    proj = B.build(out, theme=theme)["project"]
    media = list((proj / "assets" / "media").iterdir())
    assert len(media) == 1 and media[0].name.isascii() and " " not in media[0].name
    sub = (proj / "compositions" / "gx-01-split.html").read_text(encoding="utf-8")
    assert f'src="assets/media/{media[0].name}"' in sub
    assert 'data-hf-media-start-basis="local"' in sub and "muted" in sub
    assert '"fit": "contain"' in sub or '"fit":"contain"' in sub
    cfg = cfg_of((proj / "index.html").read_text(encoding="utf-8"))
    assert cfg["splits"] == [[2.1, pytest.approx(2.7)]]


def test_hosts_inside_root_duration(out, theme):
    write_plan(out, {"graphics": [{"type": "stamp", "at": "S2:</script>", "text": "END", "until": 4.0}]})
    proj = B.build(out, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    root_end = float(re.search(r'id="root"[^>]*data-duration="([\d.]+)"', html).group(1))
    for s, d in re.findall(r'-slot"[^>]*data-start="([\d.]+)" data-duration="([\d.]+)"', html):
        assert float(s) + float(d) <= root_end + 1e-6


@pytest.mark.hf
def test_hyperframes_check_passes(out, theme, monkeypatch):
    from cutmate.hf import ensure_project as real_ensure
    from cutmate.hf import hf
    from cutmate.media import run
    monkeypatch.setattr(B, "ensure_project", real_ensure)
    write_plan(out, {"captions": {"key": ["claude'a"]}, "graphics": [
        {"type": "stamp", "at": "S2:75%", "text": "NIE", "hit": True}]})
    proj = B.build(out, theme=theme)["project"]
    r = run(hf("check", str(proj)), cwd=proj)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_key_matches_inflected_forms():
    def key_of(word, keys):
        ws = [{"seg": "S1", "word": word, "start": 0.0, "end": 0.3}]
        return B.caption_pages(ws, 4.0, keys)[0]["words"][0][2]
    assert key_of("Cavemana", ["CAVEMAN"]) == "key"
    assert key_of("Cavemanem,", ["Caveman"]) == "key"
    assert key_of("Claude’a", ["CLAUDE"]) == "key"
    assert key_of("Cavemanowski", ["CAVEMAN"]) == ""     # > 3 extra letters
    assert key_of("Cavemany", ["CAVE"]) == ""            # 4-char key, 4 extra letters
    assert key_of("nowy", ["NOW"]) == ""                 # key shorter than 4 chars


def test_checkpoint_for_list_uses_last_item(out, theme):
    write_plan(out, {"graphics": [{"type": "list", "items": [
        {"text": "a", "at": "S1:Mówić"}, {"text": "b", "at": "S1:mniej"}]}]})
    # list: last item at 0.90 s + 0.4
    assert B.build(out, theme=theme)["checkpoints"] == [1.3]


def test_music_without_carve_halves_volume(out, theme, monkeypatch, capsys):
    from conftest import make_wav
    make_wav(out.parent / "bed.wav", dur=2.0)
    write_plan(out, {"music": {"src": "bed.wav", "volume": 0.4}})
    monkeypatch.setattr(B, "carve", lambda proj: False)
    html = (B.build(out, theme=theme)["project"] / "index.html").read_text(encoding="utf-8")
    assert 'id="music-bed"' in html and 'data-volume="0.2" data-audio-group="music"' in html
    assert "halved" in capsys.readouterr().out


def test_music_with_carve_keeps_volume(out, theme, monkeypatch):
    from conftest import make_wav
    make_wav(out.parent / "bed.wav", dur=2.0)
    write_plan(out, {"music": {"src": "bed.wav", "volume": 0.4}})
    monkeypatch.setattr(B, "carve", lambda proj: True)
    html = (B.build(out, theme=theme)["project"] / "index.html").read_text(encoding="utf-8")
    assert 'data-volume="0.4" data-audio-group="music"' in html


def test_relative_music_src_resolves_against_recording_folder(out, theme, monkeypatch):
    from conftest import make_wav
    (out.parent / "muzyka").mkdir()
    make_wav(out.parent / "muzyka" / "bed.wav", dur=2.0)
    write_plan(out, {"music": {"src": "muzyka/bed.wav", "volume": 0.3}})
    monkeypatch.setattr(B, "carve", lambda proj: True)
    r = B.build(out, theme=theme)
    assert (r["project"] / "assets" / "bgm" / "bed.m4a").exists()


@pytest.fixture
def out169(tmp_path, monkeypatch):
    rec = tmp_path / "rec169"
    o = rec / "out"
    (o / "work").mkdir(parents=True)
    make_clip(o / "aroll.mp4", dur=4.0, size="1920x1080", gaps=())
    (o / "work" / "aligned_words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (o / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")
    (o / "edl.json").write_text(json.dumps({"format": "16:9", "segments": []}), encoding="utf-8")
    monkeypatch.setattr(B, "ensure_project", lambda proj, fmt="9:16": (proj.mkdir(parents=True, exist_ok=True),
                                                                       (proj / "hyperframes.json").write_text("{}")))
    return o


def test_cam_169_uses_face():
    cam = B.cam_from_cuts(TIMED, "16:9", {"S2": [0.3, 0.25]})
    assert cam == [[0.0, 1.0, 0.5, 0.4], [2.0, 1.25, 0.3, 0.25]]
    g = Graphic("stamp", 2.35, 3.0, {"text": "X"}, True, None, 0)
    assert B.hits_for([g], cam, TIMED, 4.0) == [[2.35, 1.25, 0.5]]


def test_build_169_project(out169, theme):
    write_plan(out169, {"face": {"S1": [0.45, 0.3]}, "graphics": [{"type": "chip", "at": "S2:minus", "text": "X"}]})
    proj = B.build(out169, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert 'class="f169"' in html and 'data-width="1920" data-height="1080"' in html
    assert 'content="width=1920, height=1080"' in html
    assert cfg_of(html)["cam"][0] == [0.0, 1.0, 0.45, 0.3]
    sub = (proj / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    assert 'data-width="1920" data-height="1080"' in sub


def test_build_916_unchanged_markers(out, theme):
    write_plan(out, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "X"}]})
    html = (B.build(out, theme=theme)["project"] / "index.html").read_text(encoding="utf-8")
    assert 'class="f916"' in html and cfg_of(html)["cam"] == [[0.0, 1.0], [2.0, 1.12]]


def test_caption_modes_switch(out169, theme):
    write_plan(out169, {"chapters": [{"at": "S1:Mówić", "title": "Intro"}, {"at": "S2:minus", "title": "Dwa"}]})
    B.build(out169, theme=theme)                                   # 16:9 default: srt
    html = (out169 / "composition" / "index.html").read_text(encoding="utf-8")
    assert cfg_of(html)["pages"] == []
    assert (out169 / "captions.srt").read_text(encoding="utf-8").startswith("1\n00:00:00,060")
    assert (out169 / "chapters.txt").read_text(encoding="utf-8") == "00:00 Intro\n00:02 Dwa\n"
    B.build(out169, theme=theme, captions={"16:9": "burn"})
    html = (out169 / "composition" / "index.html").read_text(encoding="utf-8")
    assert cfg_of(html)["pages"] and not (out169 / "captions.srt").exists()
    B.build(out169, theme=theme, captions={"16:9": "both"})
    assert cfg_of((out169 / "composition" / "index.html").read_text(encoding="utf-8"))["pages"]
    assert (out169 / "captions.srt").exists()
    write_plan(out169, {})
    B.build(out169, theme=theme, captions={"16:9": "none"})
    assert not (out169 / "captions.srt").exists() and not (out169 / "chapters.txt").exists()


def test_caption_mode_invalid(out, theme):
    from cutmate.errors import CutmateError
    write_plan(out, {})
    with pytest.raises(CutmateError, match="caption mode"):
        B.build(out, theme=theme, captions={"9:16": "subs"})


def test_chapter_plates(out169, theme):
    write_plan(out169, {"chapters": [{"at": "S1:Mówić", "title": "Intro"}, {"at": "S2:minus", "title": "Dwa"}]})
    r = B.build(out169, theme=theme)
    proj = r["project"]
    plates = sorted((proj / "compositions").glob("gx-*-chapter.html"))
    assert len(plates) == 1                               # no plate for chapter 1
    sub = plates[0].read_text(encoding="utf-8")
    assert '"label": "ROZDZIAŁ 02"' in sub and '"title": "Dwa"' in sub
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert re.search(r'id="gx-01-chapter-slot"[^>]*data-start="1.8" data-duration="1.8"', html)
    assert 2.5 in r["checkpoints"]                        # 2.1 + 0.4


def test_chapter_plate_escapes_title(out169, theme):
    write_plan(out169, {"chapters": [{"at": "S1:Mówić", "title": "A"}, {"at": "S2:minus", "title": "</script> & „x”"}]})
    sub = next((B.build(out169, theme=theme)["project"] / "compositions").glob("gx-*-chapter.html")).read_text(encoding="utf-8")
    assert "</script> &" not in sub and "<\\/script>" in sub
