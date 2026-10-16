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


from conftest import make_clip


class FakeDetector:
    """Face drifts right over time; right hand only after 1 s."""
    def __init__(self):
        self.calls = []

    def __call__(self, rgb, t):
        self.calls.append((rgb.shape, round(t, 3)))
        return {"face": (0.4 + t * 0.1, 0.3, 0.9), "hand_left": None,
                "hand_right": (0.7, 0.6, 0.8) if t >= 1.0 else None,
                "point_right": (0.8, 0.4, 1.0) if t >= 1.0 else None}


def test_analyze_every_second_frame(tmp_path):
    from cutmate.tracks import analyze
    clip = make_clip(tmp_path / "a.mp4", dur=2.0, size="1920x1080", gaps=())
    det = FakeDetector()
    d = analyze(clip, det, every=2, width=640)
    assert (d["fps"], d["w"], d["h"]) == (15, 1920, 1080)
    assert len(det.calls) == 30 and det.calls[0][0] == (360, 640, 3)
    assert det.calls[1][1] == pytest.approx(2 / 30, abs=1e-3)
    face = d["tracks"]["face"]
    assert face[0][1] == pytest.approx(0.4, abs=0.01) and face[-1][1] == pytest.approx(0.593, abs=0.02)
    assert d["tracks"]["hand_left"] == [] and d["tracks"]["hand_right"][0][0] >= 1.0


def test_track_cache_invalidated_by_new_aroll(tmp_path):
    import os
    import time
    from cutmate.tracks import track
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=1.0, size="1920x1080", gaps=())
    det = FakeDetector()
    p = track(out, detector=det)
    n = len(det.calls)
    track(out, detector=det)                                   # cached
    assert len(det.calls) == n
    later = time.time() + 5
    os.utime(out / "aroll.mp4", (later, later))                # re-cut
    track(out, detector=det)
    assert len(det.calls) == 2 * n and p.exists()
    track(out, detector=det, force=True)
    assert len(det.calls) == 3 * n


def test_model_path_checks_sha(tmp_path, monkeypatch):
    from cutmate import tracks as T
    from cutmate.errors import CutmateError
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path))

    class R:
        status_code = 200
        content = b"not a model"
        def raise_for_status(self):
            pass
    monkeypatch.setattr(T.requests, "get", lambda url, timeout: R())
    with pytest.raises(CutmateError, match="SHA-256"):
        T.model_path()
    assert not (tmp_path / "models" / "pose_landmarker_lite.task").exists()


def test_track_cli_requires_aroll(tmp_path, capsys):
    from cutmate.cli import main
    assert main(["track", str(tmp_path / "out")]) == 2
    assert "aroll.mp4" in capsys.readouterr().err


@pytest.mark.slow
def test_pose_detector_real_footage(tmp_path):
    """Real MediaPipe on a local landscape clip (CUTMATE_TEST_HAND_CLIP); skipped when unset."""
    import shutil
    from pathlib import Path
    from cutmate.tracks import PoseDetector, analyze
    import os
    env_clip = os.environ.get("CUTMATE_TEST_HAND_CLIP")
    if not env_clip or not Path(env_clip).exists():
        pytest.skip("set CUTMATE_TEST_HAND_CLIP to a landscape clip of a pointing speaker")
    src = Path(env_clip)
    clip = tmp_path / "c.mp4"
    import subprocess
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "36", "-t", "3", "-i", str(src), "-an", str(clip)], check=True)
    d = analyze(clip, PoseDetector())
    assert len(d["tracks"]["face"]) > 30
    assert "point_left" in d["tracks"] and "point_right" in d["tracks"]
    assert all(0 < p[1] < 1 and 0 < p[2] < 0.6 for p in d["tracks"]["face"])   # face in the upper part


@pytest.mark.parametrize("data", ['[]', '{"fps": 15}', '{"tracks": []}', '{"tracks": {"face": 3}}'])
def test_load_tracks_validates_shape(tmp_path, data):
    from cutmate.errors import CutmateError
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "tracks.json").write_text(data, encoding="utf-8")
    with pytest.raises(CutmateError, match="tracks.json"):
        load_tracks(tmp_path)


def test_tracks_fresh(tmp_path):
    import os
    from cutmate.tracks import tracks_fresh
    assert not tracks_fresh(tmp_path)                                  # no tracks.json
    save_tracks(tmp_path, {"tracks": {"face": []}})
    assert tracks_fresh(tmp_path)                                      # no aroll to compare against
    (tmp_path / "aroll.mp4").write_bytes(b"x")
    t = (tmp_path / "work" / "tracks.json").stat().st_mtime
    os.utime(tmp_path / "aroll.mp4", (t - 5, t - 5))
    assert tracks_fresh(tmp_path)
    os.utime(tmp_path / "aroll.mp4", (t + 5, t + 5))                   # re-cut after tracking
    assert not tracks_fresh(tmp_path)


def test_analyze_unreadable_video_is_error(tmp_path, monkeypatch):
    from cutmate import tracks as T
    from cutmate.errors import CutmateError
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00" * 4096)
    monkeypatch.setattr(T, "probe_video", lambda p: {"width": 1920, "height": 1080})   # probe passes, decode fails
    det = FakeDetector()
    with pytest.raises(CutmateError, match="bad.mp4"):
        T.analyze(bad, det)
    assert det.calls == []


def test_pointing_target():
    from cutmate.tracks import pointing_target
    assert pointing_target((0.5, 0.5), (0.55, 0.5)) == pytest.approx((0.65, 0.5))


def test_pointing_target_clamped():
    from cutmate.tracks import pointing_target
    assert pointing_target((0.9, 0.5), (0.97, 0.5))[0] == 0.98


def test_is_extended():
    from cutmate.tracks import is_extended
    args = ((0.4, 0.3), (0.5, 0.3), (0.5, 0.7))
    assert is_extended((0.4, 0.5), *args) is False
    assert is_extended((0.1, 0.3), *args) is True


def test_gesture_at():
    from cutmate.tracks import gesture_at
    tr = {"point_right": [[1.0, 0.8, 0.4, 1.0], [1.4, 0.82, 0.42, 1.0]], "point_left": [[1.1, 0.2, 0.5, 0.0]]}
    assert gesture_at(tr, 1.2) == {"x": 0.82, "y": 0.42, "side": "right", "hand": "point_right"}
    assert gesture_at(tr, 1.1)["hand"] == "point_right"
    assert gesture_at(tr, 3.0) is None
    assert gesture_at({"face": []}, 1.0) is None          # tracks without point keys: absent, not an error


def test_analyze_keeps_point_tracks(tmp_path):
    from cutmate.tracks import analyze
    clip = make_clip(tmp_path / "a.mp4", dur=2.0, size="1920x1080", gaps=())
    d = analyze(clip, FakeDetector())
    pr = d["tracks"]["point_right"]
    assert pr and all(len(p) == 4 for p in pr) and d["tracks"]["point_left"] == []
