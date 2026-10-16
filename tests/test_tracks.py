import json

import pytest

from cutmate.tracks import face_median, fill_gaps, load_tracks, pick_hand, save_tracks, smooth


def test_smooth_median_removes_spike():
    s = [[i / 15, 0.5, 0.5, 0.9] for i in range(7)]
    s[3] = [3 / 15, 0.9, 0.1, 0.9]                      # one-frame glitch
    out = smooth(s, 5)
    assert out[3][1:3] == [0.5, 0.5] and out[3][0] == pytest.approx(0.2) and len(out) == 7


def test_fill_gaps_short_only():
    s = [[0.0, 0.0, 0.0, 1.0], [0.4, 0.4, 0.8, 1.0], [2.0, 0.5, 0.5, 1.0]]
    out = fill_gaps(s, max_gap=0.5, step=0.1)
    ts = [round(p[0], 2) for p in out]
    assert ts == [0.0, 0.1, 0.2, 0.3, 0.4, 2.0]           # 0.4 → 2.0 is too long to fill
    assert out[2][1:4] == pytest.approx([0.2, 0.4, 0.0])  # interpolated, conf 0


def test_pick_hand_and_face_median():
    tr = {"hand_left": [[1.0, 0.2, 0.5, 1], [1.1, 0.2, 0.5, 1]],
          "hand_right": [[1.0, 0.8, 0.5, 1], [5.0, 0.8, 0.5, 1]],
          "face": [[0.5, 0.40, 0.30, 1], [1.0, 0.42, 0.32, 1], [1.5, 0.60, 0.20, 1]]}
    assert pick_hand(tr, 0.9, 1.2) == "hand_left"
    assert pick_hand(tr, 4.0, 6.0) == "hand_right"
    assert pick_hand({"hand_left": [], "hand_right": []}, 0, 1) == "hand_right"
    assert face_median(tr, 0.0, 1.6) == [0.42, 0.30]
    assert face_median(tr, 9.0, 10.0) is None


def test_tracks_io(tmp_path):
    out = tmp_path / "out"
    assert load_tracks(out) is None
    p = save_tracks(out, {"fps": 15, "w": 1920, "h": 1080, "tracks": {"face": [[0.0, 0.5, 0.4, 0.9]]}})
    assert p == out / "work" / "tracks.json"
    assert load_tracks(out)["tracks"]["face"] == [[0.0, 0.5, 0.4, 0.9]]
    (out / "work" / "tracks.json").write_text("{oops", encoding="utf-8")
    from cutmate.errors import CutmateError
    with pytest.raises(CutmateError, match="tracks.json"):
        load_tracks(out)
