import json
import re
import shutil
import subprocess
from pathlib import Path

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
<markup><div class="band"><div class="x">{{label}}</div>{{media_tag}}{{face_tag}}{{back_tag}}{{cut_tag}}</div></markup>
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
    for t in ("title", "counter", "list", "chip", "stamp", "bars", "point", "split", "chapter", "pip", "lower-third", "bg", "side"):
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


def test_music_volume_from_config(out, theme, monkeypatch):
    from conftest import make_wav
    make_wav(out.parent / "bed.wav", dur=2.0)
    write_plan(out, {"music": {"src": "bed.wav"}})
    monkeypatch.setattr(B, "carve", lambda proj: True)
    r = B.build(out, theme=theme, music={"source": "folder", "folder": None, "volume": 0.3})
    assert 'data-volume="0.3" data-audio-group="music"' in (r["project"] / "index.html").read_text(encoding="utf-8")


def test_heygen_without_src_warns(out, theme):
    write_plan(out, {})
    r = B.build(out, theme=theme, music={"source": "heygen", "folder": None, "volume": 0.45})
    assert any("music.source is heygen" in w for w in r["warnings"])
    assert 'id="music-bed"' not in (r["project"] / "index.html").read_text(encoding="utf-8")


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


def _pip_plan(o, media="broll/p.png"):
    (o.parent / "broll").mkdir(exist_ok=True)
    if media.endswith(".png"):
        from PIL import Image
        Image.new("RGB", (64, 36), "red").save(o.parent / media)
    write_plan(o, {"face": {"S2": [0.3, 0.3]},
                   "graphics": [{"type": "pip", "from": "S2:minus", "to": "S2:Claude'a", "media": media}]})


def test_pip_face_clip(out169, theme):
    from cutmate.media import probe_video
    _pip_plan(out169)
    proj = B.build(out169, theme=theme)["project"]
    faces = list((proj / "assets" / "media").glob("pipface-*.mp4"))
    assert len(faces) == 1
    info = probe_video(faces[0])
    assert (info["width"], info["height"]) == (360, 360) and info["acodec"] is None
    assert info["duration"] == pytest.approx(1.0, abs=0.1)        # 2.1 -> 3.1
    sub = (proj / "compositions" / "gx-01-pip.html").read_text(encoding="utf-8")
    assert f'src="assets/media/{faces[0].name}"' in sub and 'class="clip"' in sub and "muted" in sub


def test_pip_face_clip_regenerated_after_recut(out169, theme):
    import os
    import time
    _pip_plan(out169)
    proj = B.build(out169, theme=theme)["project"]
    face = next((proj / "assets" / "media").glob("pipface-*.mp4"))
    first = face.stat().st_mtime
    B.build(out169, theme=theme)                                 # same A-roll -> reused
    assert face.stat().st_mtime == first
    time.sleep(0.05)
    make_clip(out169 / "aroll.mp4", dur=4.0, size="1920x1080", gaps=())   # re-cut
    os.utime(out169 / "aroll.mp4", (time.time() + 5, time.time() + 5))
    B.build(out169, theme=theme)
    assert face.stat().st_mtime > first
    write_plan(out169, {})
    B.build(out169, theme=theme)
    assert not list((proj / "assets" / "media").glob("pipface-*.mp4"))   # pruned


def test_face_clip_atomic_on_failure(tmp_path, monkeypatch):
    import subprocess
    from cutmate.errors import CutmateError
    dst = tmp_path / "face.mp4"

    def fake_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    monkeypatch.setattr(B, "run", fake_run)
    with pytest.raises(CutmateError, match="pip face clip"):
        B.face_clip(tmp_path / "a.mp4", 0, 1, [0.5, 0.5], (1920, 1080), dst)
    assert list(tmp_path.iterdir()) == []


def test_missing_component_is_cutmate_error(tmp_path):
    from cutmate.errors import CutmateError
    with pytest.raises(CutmateError, match="theme has no nope.html component"):
        B._sections(tmp_path / "nope.html")


FX = """<style>ROOT .fx { width: 10px; height: 10px; }</style>
<markup><div class="fx"></div></markup>
<script>
const el = root.querySelector(".fx");
U.follow(el, P.track);
U.clock((t) => { el.style.opacity = String(Math.min(1, t)); });
</script>"""


def _fx(o, name="orb", text=FX):
    (o / "custom").mkdir(exist_ok=True)
    (o / "custom" / f"{name}.html").write_text(text, encoding="utf-8")


def _tracks169(o):
    (o / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [], "hand_left": [], "hand_right": [[2.2, 0.5, 0.5, 0.9], [2.6, 0.75, 0.5, 0.9]]}}), encoding="utf-8")


def test_custom_host_with_follow(out169, theme):
    _fx(out169)
    _tracks169(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "from": "S2:minus", "to": "S2:Claude'a",
                                      "follow": "hand", "params": {"color": "#fff"}}]})
    proj = B.build(out169, theme=theme)["project"]
    sub = (proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    P = json.loads(re.search(r"const P = (.*?);\n", sub).group(1).replace("<\\/", "</"))
    assert P["color"] == "#fff" and (P["w"], P["h"]) == (1920, 1080)
    assert P["track"] == [[0.4, 960.0, 567.0], [0.8, 1560.0, 567.0]]          # host 1.8; S2 punch-in 1.25x about (0.5, 0.4)
    assert P["follow"] == "hand"                                              # effects know they were meant to follow
    assert "CutmateFX.make" in sub and "U.follow(el, P.track)" in sub
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert '<script src="assets/effects.js"></script>' in html and (proj / "assets" / "effects.js").exists()
    assert "importmap" not in html                                            # no Three marker


def test_follow_without_samples(out169, theme):
    _fx(out169)
    (out169 / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080,
                                                             "tracks": {"face": [], "hand_left": [], "hand_right": []}}))
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus", "follow": "face"}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert '"track": []' in sub and _P(sub)["follow"] == "face"


def test_custom_three_injects_importmap_and_region(out169, theme):
    _fx(out169, "logo", FX.replace("U.clock", "U.three({}).then(() => {}); U.clock"))
    write_plan(out169, {"graphics": [{"type": "side", "from": "S2:minus", "to": "S2:</script>", "effect": "logo"}]})
    proj = B.build(out169, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert html.index("assets/effects.js") < html.index('type="importmap"')
    sub = (proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert ('<div class="cm-region" style="position:absolute;left:60px;top:60px;width:840px;height:960px;'
            'overflow:hidden">') in sub and '"w": 840' in sub
    assert "left: 60px" not in sub                                           # composition root stays full frame


def test_custom_lint_and_missing(out169, theme):
    from cutmate.errors import PlanError
    _fx(out169, "bad", FX.replace("U.clock", "Math.random(); U.clock"))
    write_plan(out169, {"graphics": [{"type": "custom", "name": "bad", "at": "S2:minus"}]})
    with pytest.raises(PlanError, match="bad.html: uses Math.random"):
        B.build(out169, theme=theme)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "nope", "at": "S2:minus"}]})
    with pytest.raises(PlanError, match="nope"):
        B.build(out169, theme=theme)


def test_bg_cutout_cached_and_atomic(out169, theme, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, env=None):
        cmd = [str(c) for c in cmd]
        calls.append((cmd, cwd))
        if "remove-background" in cmd:
            o = cmd[cmd.index("-o") + 1]
            assert "/" not in o and "\\" not in o                    # plain names, cwd-relative (Windows npx)
            (Path(cwd) / o).write_bytes(b"webm")
        elif cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(B, "run", fake_run)
    (out169.parent / "broll").mkdir()
    from PIL import Image
    Image.new("RGB", (32, 18), "blue").save(out169.parent / "broll" / "k.png")
    write_plan(out169, {"graphics": [{"type": "bg", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/k.png"}]})
    proj = B.build(out169, theme=theme)["project"]
    media = proj / "assets" / "media"
    assert sorted(p.name for p in media.iterdir()) == ["bgcut-2100-3100.webm", "m01-k.png"]
    n = sum("remove-background" in c[0] for c in calls)
    B.build(out169, theme=theme)
    assert sum("remove-background" in c[0] for c in calls) == n                  # cached
    sub = (proj / "compositions" / "gx-01-bg.html").read_text(encoding="utf-8")
    assert 'src="assets/media/bgcut-2100-3100.webm"' in sub and "muted" in sub


def test_bg_cutout_failure_leaves_nothing(out169, theme, monkeypatch, tmp_path):
    from cutmate.errors import CutmateError

    def fail_run(cmd, cwd=None, env=None):
        cmd = [str(c) for c in cmd]
        if "remove-background" in cmd:
            (Path(cwd) / cmd[cmd.index("-o") + 1]).write_bytes(b"half")
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
        Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(B, "run", fail_run)
    media = tmp_path / "m"
    media.mkdir()
    with pytest.raises(CutmateError, match="boom"):
        B.bg_cutout(out169 / "aroll.mp4", 2.1, 3.1, media)
    assert list(media.iterdir()) == []


def test_side_shifts_speaker_to_face(out169, theme):
    (out169.parent / "broll").mkdir()
    from PIL import Image
    Image.new("RGB", (32, 18), "red").save(out169.parent / "broll" / "d.png")
    write_plan(out169, {"face": {"S2": [0.4, 0.3]},
                        "graphics": [{"type": "side", "from": "S2:minus", "to": "S2:</script>", "media": "broll/d.png"}]})
    proj = B.build(out169, theme=theme)["project"]
    cfg = cfg_of((proj / "index.html").read_text(encoding="utf-8"))
    assert cfg["sides"] == [[2.1, pytest.approx(3.1), 672]]               # 1440 - 0.4*1920
    sub = (proj / "compositions" / "gx-01-side.html").read_text(encoding="utf-8")
    assert '"speaker": "right"' in sub


def test_build_ignores_stale_tracks(out169, theme):
    import os
    (out169 / "work" / "tracks.json").write_text(json.dumps({"tracks": {
        "face": [[t / 10, 0.2, 0.25, 0.9] for t in range(40)]}}), encoding="utf-8")
    write_plan(out169, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "X"}]})
    cam = cfg_of((B.build(out169, theme=theme)["project"] / "index.html").read_text(encoding="utf-8"))["cam"]
    assert cam[1][2:] == [0.2, 0.25]                                          # fresh: auto face used
    t = (out169 / "work" / "tracks.json").stat().st_mtime
    os.utime(out169 / "aroll.mp4", (t + 5, t + 5))
    cam = cfg_of((B.build(out169, theme=theme)["project"] / "index.html").read_text(encoding="utf-8"))["cam"]
    assert cam[1][2:] == [0.5, 0.4]                                           # stale: default face


def _P(sub):
    return json.loads(re.search(r"const P = (.*?);\n", sub).group(1).replace("<\\/", "</"))


def test_side_effect_region_wrapper_speaker_left(out169, theme):
    _fx(out169, "diagram")
    write_plan(out169, {"graphics": [{"type": "side", "from": "S2:minus", "to": "S2:</script>", "effect": "diagram",
                                      "speaker": "left"}]})
    proj = B.build(out169, theme=theme)["project"]
    sub = (proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert ('<div id="gx-01-custom" data-composition-id="gx-01-custom" data-width="1920" data-height="1080" '
            'data-duration="1.7"><div class="cm-region" style="position:absolute;left:1020px;top:60px;width:840px;'
            'height:960px;overflow:hidden">') in sub
    assert 'const root = document.querySelector("#gx-01-custom > .cm-region");' in sub
    assert "CutmateFX.make(tl, root, " in sub and "right: auto" not in sub
    P = _P(sub)
    assert (P["w"], P["h"]) == (840, 960)


def test_region_effect_track_is_offset(out169, theme):
    _fx(out169)
    _tracks169(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "from": "S2:minus", "to": "S2:Claude'a",
                                      "follow": "hand", "region": [1020, 60, 840, 960]}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert _P(sub)["track"] == [[0.4, -60.0, 507.0], [0.8, 540.0, 507.0]]     # on screen (960, 567) − (1020, 60)


def test_custom_params_cannot_override_timing(out169, theme):
    _fx(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "from": "S2:minus", "to": "S2:Claude'a",
                                      "params": {"at": 99, "end": 99, "w": 5, "h": 5, "dur": 99, "track": [1],
                                                 "lang": "xx", "color": "#fff"}}]})
    P = _P((B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8"))
    assert (P["at"], P["end"], P["w"], P["h"], P["dur"], P["track"], P["lang"], P["color"]) == \
        (0.3, 1.3, 1920, 1080, 1.3, [], "pl", "#fff")


def test_bg_effect_fades_and_has_no_back(out169, theme, monkeypatch):
    def fake_cut(aroll, a, b, media):
        (media / "bgcut-x.webm").write_bytes(b"w")
        return "bgcut-x.webm"
    monkeypatch.setattr(B, "bg_cutout", fake_cut)
    _fx(out169, "space")
    write_plan(out169, {"graphics": [{"type": "bg", "from": "S2:minus", "to": "S2:Claude'a", "effect": "space"}]})
    proj = B.build(out169, theme=theme)["project"]
    fx = (proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert ("tl.set(root, { autoAlpha: 0 }, 0); tl.to(root, { autoAlpha: 1, duration: 0.3 }, P.at); "
            "tl.to(root, { autoAlpha: 0, duration: 0.3, immediateRender: false }, Math.max(P.at + 0.3, P.end - 0.3));") in fx
    assert 'const root = document.getElementById("gx-01-custom");' in fx
    bg = (proj / "compositions" / "gx-02-bg.html").read_text(encoding="utf-8")
    assert 'class="img"' not in bg and "m01-" not in bg and 'src="assets/media/bgcut-x.webm"' in bg
    _fx(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus"}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert "autoAlpha" not in sub                                              # hand-placed custom: no auto fade


def test_no_effects_build_matches_2b_shape(out, theme):
    write_plan(out, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "X"}]})
    proj = B.build(out, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert ('<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>\n'
            '    <link rel="stylesheet" href="assets/tokens.css" />') in html
    assert "effects.js" not in html and "\n    \n" not in html and not (proj / "assets" / "effects.js").exists()
    sub = (proj / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    assert "CutmateFX" not in sub and "    const U = {\n" in sub and "    };\n" in sub
    assert "pointer-events: none; }\n#gx-01-chip .band" in sub                # no extra style line


def test_cam_unzoomed_while_bg_on_screen():
    cam = B.cam_from_cuts(TIMED, "16:9", {"S2": [0.3, 0.25]}, bgs=[(2.1, 3.1)])
    assert cam == [[0.0, 1.0, 0.5, 0.4], [2.0, 1.25, 0.3, 0.25], [2.1, 1.0, 0.3, 0.25], [3.1, 1.25, 0.3, 0.25]]
    cam = B.cam_from_cuts(TIMED, "16:9", {}, bgs=[(1.5, 2.5)])                  # bg spans a cut
    assert cam == [[0.0, 1.0, 0.5, 0.4], [1.5, 1.0, 0.5, 0.4], [2.0, 1.0, 0.5, 0.4], [2.5, 1.25, 0.5, 0.4]]
    assert B.cam_from_cuts(TIMED, "9:16", bgs=[(2.1, 3.1)]) == [[0.0, 1.0], [2.0, 1.12], [2.1, 1.0], [3.1, 1.12]]
    gs = [Graphic("bg", 2.1, 3.1, {}, False, None, 0), Graphic("stamp", 2.35, 3.0, {"text": "X"}, True, None, 1)]
    cam = B.cam_from_cuts(TIMED, "16:9", {}, bgs=[(2.1, 3.1)])
    assert B.hits_for(gs, cam, TIMED, 4.0) == [[2.35, 1.0, 0]]                  # shake only, no punch
    gs = [Graphic("bg", 2.8, 3.5, {}, False, None, 0), Graphic("stamp", 2.35, 2.7, {"text": "X"}, True, None, 1)]
    assert B.hits_for(gs, B.cam_from_cuts(TIMED, "16:9", {}, bgs=[(2.8, 3.5)]), TIMED, 4.0) == \
        [[2.35, 1.25, 0.31]]                                                     # punch ends before the bg starts


def test_build_cam_around_bg(out169, theme, monkeypatch):
    def fake_cut(aroll, a, b, media):
        (media / "bgcut-x.webm").write_bytes(b"w")
        return "bgcut-x.webm"
    monkeypatch.setattr(B, "bg_cutout", fake_cut)
    (out169.parent / "broll").mkdir()
    from PIL import Image
    Image.new("RGB", (32, 18), "blue").save(out169.parent / "broll" / "k.png")
    write_plan(out169, {"face": {"S2": [0.3, 0.25]}, "graphics": [
        {"type": "bg", "from": "S2:minus", "to": "S2:Claude'a", "media": "broll/k.png"},
        {"type": "stamp", "at": "S2:75%", "text": "X", "hit": True}]})
    cfg = cfg_of((B.build(out169, theme=theme)["project"] / "index.html").read_text(encoding="utf-8"))
    assert cfg["cam"][1:] == [[2.0, 1.25, 0.3, 0.25], [2.1, 1.0, 0.3, 0.25], [3.1, 1.25, 0.3, 0.25]]
    assert cfg["hits"] == [[2.35, 1.0, 0]]


def test_2b_user_theme_without_new_components_builds(tmp_path, monkeypatch, capsys):
    """A user theme copied before 2c (no bg/side components, no custom/ folder) still builds the 16:9 theme-check plan."""
    from cutmate.theme_check import _synthetic_rec
    home = tmp_path / "home"
    shutil.copytree(paths.plugin_root() / "themes" / "clean", home / "themes" / "old",
                    ignore=shutil.ignore_patterns("bg.html", "side.html", "custom"))
    monkeypatch.setenv("CUTMATE_HOME", str(home))
    monkeypatch.setattr(B, "ensure_project", lambda proj, fmt="9:16": (proj.mkdir(parents=True, exist_ok=True),
                                                                       (proj / "hyperframes.json").write_text("{}")))

    def fake_cut(aroll, a, b, media):
        (media / "bgcut-x.webm").write_bytes(b"w")
        return "bgcut-x.webm"
    monkeypatch.setattr(B, "bg_cutout", fake_cut)
    out = _synthetic_rec(tmp_path, "16:9")
    proj = B.build(out, theme="old", captions={"16:9": "both"})["project"]
    printed = capsys.readouterr().out
    assert "WARN theme old has no bg component — using clean's" in printed
    assert "WARN theme old has no side component — using clean's" in printed
    assert printed.count("has no bg component") == 1
    subs = {p.name: p.read_text(encoding="utf-8") for p in (proj / "compositions").glob("gx-*.html")}
    assert any(n.endswith("-bg.html") and "bg-wrap" in t for n, t in subs.items())
    assert any(n.endswith("-custom.html") and "fx-orb" in t for n, t in subs.items())


def test_custom_effect_assets_folder(out169, theme):
    _fx(out169)
    d = out169 / "custom" / "orb"
    (d / "tex").mkdir(parents=True)
    (d / "anim.json").write_text("{}", encoding="utf-8")
    (d / "tex" / "a.png").write_bytes(b"png")
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus"}]})
    proj = B.build(out169, theme=theme)["project"]
    fx = proj / "assets" / "fx"
    assert (fx / "orb" / "anim.json").exists() and (fx / "orb" / "tex" / "a.png").read_bytes() == b"png"
    assert _P((proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8"))["assets"] == "assets/fx/orb/"
    (d / "anim.json").unlink()
    (fx / "stale").mkdir()
    B.build(out169, theme=theme)
    assert sorted(str(p.relative_to(fx)) for p in fx.rglob("*")) == ["orb", "orb/tex", "orb/tex/a.png"]
    write_plan(out169, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "X"}]})
    B.build(out169, theme=theme)
    assert not fx.exists()


def test_custom_effect_without_folder_has_no_assets_key(out169, theme):
    _fx(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus"}]})
    proj = B.build(out169, theme=theme)["project"]
    assert "assets" not in _P((proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8"))


def test_three_effect_has_lint_visible_import(out169, theme):
    _fx(out169, "cube", FX.replace("U.clock", "const m = new THREE.Mesh(); U.clock"))
    write_plan(out169, {"graphics": [{"type": "custom", "name": "cube", "at": "S2:minus"}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert re.search(r"\b(?:import|from)\s*[^;\n]*['\"][^'\"]*three[^'\"]*['\"]", sub)   # hyperframes missing_three_script rule


def test_region_root_css(out169, theme):
    _fx(out169, "diagram", "<style>ROOT .x { color: red; }</style>\n<markup><div class=\"x\"></div></markup>\n<script>U.clock(() => {});</script>")
    write_plan(out169, {"graphics": [{"type": "side", "from": "S2:minus", "to": "S2:</script>", "effect": "diagram"}]})
    proj = B.build(out169, theme=theme)["project"]
    sub = (proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert "#gx-01-custom > .cm-region .x" in sub
    assert "#gx-01-custom .x" not in sub


def test_ensure_project_with_existing_dir(tmp_path, monkeypatch):
    from cutmate import hf as H
    proj = tmp_path / "out" / "composition"
    (proj / ".media" / "images").mkdir(parents=True)
    (proj / ".media" / "images" / "a.jpg").write_bytes(b"jpg")

    def fake_run(cmd, cwd=None, env=None, **kw):
        target = Path(cwd) / cmd[cmd.index("init") + 1]
        assert not target.exists()
        target.mkdir()
        (target / "hyperframes.json").write_text("{}")
        (target / "index.html").write_text("<html>")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(H, "run", fake_run)
    H.ensure_project(proj)
    assert (proj / "hyperframes.json").exists() and (proj / "index.html").exists()
    assert (proj / ".media" / "images" / "a.jpg").read_bytes() == b"jpg"
    assert [p.name for p in proj.parent.iterdir()] == ["composition"]


def test_custom_place_px(out169, theme):
    _fx(out169)
    _tracks169(out169)
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus"}]})
    p = out169 / "work" / "tracks.json"
    # no place -> no P.place
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert "place" not in _P(sub) and "follow" not in _P(sub)
    hand = {"fps": 15, "w": 1920, "h": 1080, "tracks": {"face": [], "point_right": [[t / 10, 0.75, 0.5, 0.9] for t in range(0, 40)]}}
    p.write_text(json.dumps(hand), encoding="utf-8")
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus", "place": "gesture"}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert _P(sub)["place"] == [1560.0, 567.0]                               # (0.75, 0.5) through the punch-in
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus", "place": "gesture",
                                      "region": [1020, 60, 840, 960]}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8")
    assert _P(sub)["place"] == [540.0, 507.0]


def test_custom_media_param_copied(out169, theme):
    _fx(out169)
    (out169.parent / "broll").mkdir()
    (out169.parent / "broll" / "a.png").write_bytes(b"png")
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus", "media": "broll/a.png"}]})
    proj = B.build(out169, theme=theme)["project"]
    P = _P((proj / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8"))
    assert P["media"].startswith("assets/media/") and (proj / P["media"]).exists()


def test_split_effect_host_and_order(out, theme):
    _fx(out, "diagram")
    write_plan(out, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:</script>", "effect": "diagram"}]})
    proj = B.build(out, theme=theme)["project"]
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert html.index("gx-01-split") < html.index("gx-02-custom")
    split = (proj / "compositions" / "gx-01-split.html").read_text(encoding="utf-8")
    assert "<video" not in split and 'class="img"' not in split and "media_tag" not in split and "band" in split
    sub = (proj / "compositions" / "gx-02-custom.html").read_text(encoding="utf-8")
    assert 'class="cm-region" style="position:absolute;left:40px;top:40px;width:1000px;height:820px' in sub
    assert (_P(sub)["w"], _P(sub)["h"]) == (1000, 820)
    # the region slides in and out with the split panel (split.html: 0.45 s in from P.at, 0.4 s out ending at P.end)
    assert ('tl.fromTo(root, { y: -900 }, { y: 0, duration: 0.45, ease: "power3.out" }, P.at); '
            'tl.to(root, { y: -900, duration: 0.4, ease: "power3.inOut", immediateRender: false }, '
            'Math.max(P.at + 0.45, P.end - 0.4));') in sub and "autoAlpha" not in sub
    assert cfg_of(html)["splits"]                                              # face still moves down for the host


def test_split_effect_missing(out, theme):
    from cutmate.errors import PlanError
    write_plan(out, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:</script>", "effect": "nope"}]})
    with pytest.raises(PlanError, match="nope"):
        B.build(out, theme=theme)
    assert not list((out / "composition" / "compositions").glob("gx-*.html"))


def test_screen_point_camera_split_side_clamp():
    cam169 = [[0.0, 1.0, 0.5, 0.4], [2.0, 1.25, 0.45, 0.4]]
    x, y = B.screen_point(0.85, 0.4, 2.5, cam169, [], [], 1920, 1080)
    assert (x, y) == (round(0.95 * 1920, 1), 432.0)                            # zoomed 16:9: about the face
    assert B.screen_point(0.85, 0.4, 1.0, cam169, [], [], 1920, 1080) == (1632.0, 432.0)   # unzoomed
    cam916 = [[0.0, 1.0], [2.0, 1.12]]
    x, y = B.screen_point(0.75, 0.25, 2.5, cam916, [], [], 1080, 1920)
    assert (x, y) == (round((0.5 + 0.25 * 1.12) * 1080, 1), round((0.46 - 0.21 * 1.12) * 1920, 1))  # #cam origin 50% 46%
    splits = [[1.0, 2.6]]                                                       # tOut = exit move start (0.4 s)
    assert B.screen_point(0.5, 0.5, 1.5, cam916[:1], splits, [], 1080, 1920) == (540.0, 1260.0)
    assert B.screen_point(0.5, 0.5, 2.95, cam916[:1], splits, [], 1080, 1920) == (540.0, 1260.0)
    assert B.screen_point(0.5, 0.5, 3.1, cam916[:1], splits, [], 1080, 1920) == (540.0, 960.0)
    sides = [[1.0, 2.6, 480]]
    assert B.screen_point(0.25, 0.4, 1.5, cam169[:1], [], sides, 1920, 1080) == (960.0, 432.0)
    assert B.screen_point(0.9, 0.4, 1.5, cam169[:1], [], sides, 1920, 1080) == (1920.0, 432.0)   # clamped
    assert B.screen_point(0.5, 0.98, 1.5, cam916[:1], splits, [], 1080, 1920) == (540.0, 1920.0)


def _point169(o, x=0.75, y=0.5):
    (o / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [], "hand_left": [], "hand_right": [], "point_left": [],
        "point_right": [[t / 10, x, y, 0.9] for t in range(0, 40)]}}), encoding="utf-8")


def test_custom_place_palm_follows_held_hand(out169, theme):
    """Open palm: P.place sits a bit above the palm and P.track follows the hand, held where it drops out."""
    _fx(out169)
    (out169 / "work" / "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [], "point_left": [], "point_right": [], "finger_left": [], "finger_right": [], "palm_left": [],
        "palm_right": [[round(2.0 + i * 0.1, 2), 0.5, 0.6, 1.0] for i in range(4)] + [[3.5, 0.6, 0.6, 1.0]]}}), encoding="utf-8")
    write_plan(out169, {"graphics": [{"type": "custom", "name": "orb", "at": "S2:minus", "until": 3.9, "place": "gesture"}]})
    P = _P((B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-custom.html").read_text(encoding="utf-8"))
    assert P["place"][1] < 0.6 * 1080 and P["track"] and P["track"][0][0] == P["at"]
    assert all(b[0] - a[0] <= 0.5 for a, b in zip(P["track"], P["track"][1:]))
    assert P["track"][0][1:] == P["place"] and "follow" not in P
    assert set(P["hands"]) == {"right"} and P["hands"]["right"][0] == P["track"][0]


def test_chip_place_gesture(out169, theme):
    _point169(out169)
    write_plan(out169, {"graphics": [{"type": "chip", "at": "S2:minus", "text": "tu", "place": "gesture"}]})
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    P = _P(sub)
    assert P["place"] == [1560.0, 567.0]                                       # through the 1.25x punch-in on S2
    assert P["safe"] == [60, 60, 1800, 800] and "place_xy" not in P
    _point169(out169)
    write_plan(out169, {"graphics": [{"type": "chip", "at": "S1:Mówić", "text": "tu", "place": "gesture"}]})
    out169.joinpath("work", "tracks.json").write_text(json.dumps({"fps": 15, "w": 1920, "h": 1080, "tracks": {
        "face": [], "point_left": [], "point_right": [[3.5, 0.75, 0.5, 0.9]]}}), encoding="utf-8")
    sub = (B.build(out169, theme=theme)["project"] / "compositions" / "gx-01-chip.html").read_text(encoding="utf-8")
    assert "place" not in _P(sub) and "safe" not in _P(sub)                    # no gesture: default band


def test_split_explainer_params_media_copied(out, theme):
    _fx(out, "stat-card")
    (out.parent / "broll").mkdir()
    (out.parent / "broll" / "shot.png").write_bytes(b"png")
    write_plan(out, {"graphics": [{"type": "split", "from": "S2:minus", "to": "S2:</script>", "effect": "stat-card",
                                   "params": {"value": 75, "media": "broll/shot.png"}}]})
    proj = B.build(out, theme=theme)["project"]
    P = _P((proj / "compositions" / "gx-02-custom.html").read_text(encoding="utf-8"))
    assert P["media"].startswith("assets/media/") and (proj / P["media"]).exists() and P["value"] == 75
