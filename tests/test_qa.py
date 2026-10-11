import json
from pathlib import Path

import numpy as np
import pytest

from cutmate.errors import CutmateError
from cutmate.qa import has_repeat, mix_scan, quiet_segments, run_qa

SR = 48000


def tone(sec, amp, sr=SR):
    t = np.arange(int(sec * sr)) / sr
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_mix_scan_finds_loud_burst():
    voice = tone(3.0, 0.1)
    mix = voice.copy()
    mix[int(1.0 * SR):int(1.3 * SR)] += tone(0.3, 0.8)
    med, runs = mix_scan(mix, voice)
    assert len(runs) == 1
    s, e, over = runs[0]
    assert 0.6 <= s <= 1.1 and e >= 1.3 and over > 3


def test_mix_scan_clean():
    voice = tone(2.0, 0.1)
    assert mix_scan(voice.copy(), voice)[1] == []


def test_quiet_segments():
    voice = np.concatenate([tone(1.0, 0.2), tone(1.0, 0.02)])
    words = [{"seg": "S1", "start": 0.1, "end": 0.9}, {"seg": "S2", "start": 1.1, "end": 1.9}]
    timed = [{"id": "S1", "start": 0.0, "end": 1.0, "text": "głośno"}, {"id": "S2", "start": 1.0, "end": 2.0, "text": "cicho"}]
    med = 20 * np.log10(0.2 / np.sqrt(2))
    assert [q[0] for q in quiet_segments(voice, words, timed, med)] == ["S2"]


def test_has_repeat():
    assert has_repeat(["na", "na", "githubie"])
    assert has_repeat(["a", "każdy", "su…", "a", "każdy"])
    assert has_repeat(["podmienia", "klucze", "eee", "podmienia", "klucze"])
    assert has_repeat(["podmienia", "klucze", "podmienia"])
    assert not has_repeat(["to", "jest", "test"])


def test_run_qa_missing_files(tmp_path):
    """Test that missing required files raise CutmateError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "work").mkdir()

    # Test missing final.mp4
    with pytest.raises(CutmateError, match="final.mp4.*run `cutmate finalize` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create final.mp4, test missing aroll.mp4
    (out_dir / "final.mp4").touch()
    with pytest.raises(CutmateError, match="aroll.mp4.*run `cutmate finalize` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create aroll.mp4, test missing aligned_words.json
    (out_dir / "aroll.mp4").touch()
    with pytest.raises(CutmateError, match="aligned_words.json.*run `cutmate align` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create aligned_words.json, test missing edl_timed.json
    (out_dir / "work" / "aligned_words.json").write_text("[]")
    with pytest.raises(CutmateError, match="edl_timed.json.*run `cutmate align` first"):
        run_qa(out_dir, None, "pl", asr=False)
