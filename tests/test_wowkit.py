"""The WOW test kit itself: seek_safe must catch backward-scrub and small local bugs (Review Focus 1)."""
import numpy as np
import pytest
from PIL import Image

import wowkit


def _png(path, arr):
    Image.fromarray(arr.astype("uint8")).save(path)
    return path


def test_local_measure_catches_a_small_wrong_label(tmp_path):
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 256, (1920, 1080, 3))
    label = frame.copy()
    label[1500:1560, 100:300] = 255                     # a 200x60 label in the wrong state: 0.6 % of the frame
    a, b = _png(tmp_path / "a.png", frame), _png(tmp_path / "b.png", label)
    r = wowkit.diff_report(a, b)
    assert r["mean"] < 1.0 < r["tile"]                  # the whole-frame mean misses it, the worst tile does not
    assert 0 < r["share"] < 0.01
    assert wowkit.diff_report(a, _png(tmp_path / "c.png", frame)) == {"mean": 0.0, "tile": 0.0, "share": 0.0}
    wide = wowkit.diff_report(_png(tmp_path / "w1.png", frame.transpose(1, 0, 2)),
                              _png(tmp_path / "w2.png", label.transpose(1, 0, 2)))
    assert wide["tile"] > 1.0                           # 16:9: the grid turns with the frame


def test_default_before_scrubs_back():
    assert wowkit.default_before(2.0, 6.0) == (0.3, 4.0)          # an earlier and a later time
    assert wowkit.default_before(5.0, 6.0) == (0.3, 5.95)         # clamped to the end
    assert wowkit.default_before(5.98, 6.0) == (0.3, 4.98)        # at the very end: scrub back from before it
    assert wowkit.default_before(0.2, 6.0) == (0.0, 2.2)
    for t in (0.1, 1.0, 3.0, 5.9):
        before = wowkit.default_before(t, 6.0)
        assert any(b < t for b in before) and any(b != t for b in before)
        assert all(0 <= b < 6.0 for b in before)


PROBE = """<style>
ROOT .pb { position: absolute; left: 100px; top: 1500px; width: 200px; height: 60px; background: #000;
           color: #fff; font: 700 40px/60px Inter, sans-serif; text-align: center; }
</style>
<markup><div class="pb"></div></markup>
<script>
const el = root.querySelector(".pb");
%s
</script>"""
GOOD = 'U.clock((t) => { el.textContent = t.toFixed(2); });'
STALE = 'let prev = 0;\nU.clock((t) => { el.textContent = prev.toFixed(2); prev = t; });'   # the previous frame's state
COUNT = 'let n = 0;\nU.clock(() => { el.textContent = "N" + (n++); });'                     # depends on seek history


def _probe(tmp_path, body):
    out = tmp_path / "rec" / "out" / "custom"
    out.mkdir(parents=True)
    (out / "probe.html").write_text(PROBE % body, encoding="utf-8")
    return wowkit.project(tmp_path, {"graphics": [{"type": "custom", "name": "probe", "at": 0.5, "until": 5.5}]})


@pytest.mark.hf
def test_seek_safe_passes_a_safe_probe_and_fails_broken_ones(tmp_path):
    good = wowkit.seek_report(_probe(tmp_path / "good", GOOD), 3.0)
    print("good", good)
    assert good["before"] == (0.3, 5.0) and good["tile"] <= 1.0 and good["share"] == 0.0
    for name, body in (("stale", STALE), ("count", COUNT)):
        bad = wowkit.seek_report(_probe(tmp_path / name, body), 3.0)
        print(name, bad)
        assert bad["tile"] > 1.0, (name, bad)          # caught by the worst tile …
        assert bad["mean"] < 1.0, (name, bad)          # … though the whole-frame mean alone would pass it
