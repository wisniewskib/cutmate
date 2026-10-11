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
    # Positive cases from brief
    assert has_repeat(["na", "na", "githubie"])  # Rule a: adjacent identical
    assert has_repeat(["a", "każdy", "su…", "a", "każdy"])  # Rule b: ellipsis
    assert has_repeat(["podmienia", "klucze", "eee", "podmienia", "klucze"])  # Rule c: bigram repeat
    assert has_repeat(["podmienia", "klucze", "podmienia"])  # Rule d: X Y X (X=5+ chars)

    # Negative cases: ordinary sentences
    assert not has_repeat(["to", "jest", "test"])  # Original brief case
    assert not has_repeat("to jest bardzo ważne i to jest ważne".split())
    assert not has_repeat("I think that is what that means".split())
    assert not has_repeat("to jest tak jak jest".split())
    assert not has_repeat("będzie dobrze będziemy razem".split())

    # Additional positive cases
    assert has_repeat(["githu", "githubie"])  # Rule e: prefix of next word


def test_run_qa_missing_files(tmp_path):
    """Test that missing required files raise CutmateError with correct hints."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "work").mkdir()

    # Test missing final.mp4
    with pytest.raises(CutmateError, match="final.mp4.*run `cutmate finalize` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create final.mp4, test missing aroll.mp4 (produced by cut)
    (out_dir / "final.mp4").touch()
    with pytest.raises(CutmateError, match="aroll.mp4.*run `cutmate cut` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create aroll.mp4, test missing aligned_words.json
    (out_dir / "aroll.mp4").touch()
    with pytest.raises(CutmateError, match="aligned_words.json.*run `cutmate align` first"):
        run_qa(out_dir, None, "pl", asr=False)

    # Create aligned_words.json, test missing edl_timed.json (produced by cut)
    (out_dir / "work" / "aligned_words.json").write_text("[]")
    with pytest.raises(CutmateError, match="edl_timed.json.*run `cutmate cut` first"):
        run_qa(out_dir, None, "pl", asr=False)


def test_run_qa_backend_required(tmp_path):
    """Test that asr=True without backend raises CutmateError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "work").mkdir()

    # Create dummy files
    (out_dir / "final.mp4").touch()
    (out_dir / "aroll.mp4").touch()
    (out_dir / "work" / "aligned_words.json").write_text("[]")
    (out_dir / "work" / "edl_timed.json").write_text("[]")

    with pytest.raises(CutmateError, match="a transcription backend is required"):
        run_qa(out_dir, None, "pl", asr=True)


def test_run_qa_prints_lines_before_asr_failure(tmp_path, monkeypatch, capsys):
    from cutmate import qa
    from cutmate.errors import BackendError
    out = tmp_path / "out"
    (out / "work").mkdir(parents=True)
    for n in ("final.mp4", "aroll.mp4"):
        (out / n).touch()
    (out / "work" / "aligned_words.json").write_text("[]")
    (out / "work" / "edl_timed.json").write_text("[]")
    monkeypatch.setattr(qa, "read_pcm", lambda *a: tone(1.0, 0.1))
    monkeypatch.setattr(qa, "extract_wav", lambda *a: (_ for _ in ()).throw(BackendError("asr down")))

    class B:
        name = "fake"
    with pytest.raises(BackendError):
        run_qa(out, B(), "pl", asr=True)
    assert "== mix: voice median" in capsys.readouterr().out


def test_quiet_segments_use_generated_ids():
    voice = np.concatenate([tone(1.0, 0.3), tone(1.0, 0.01)])
    timed = [{"id": "S1", "start": 0.0, "end": 1.0}, {"id": "S2", "start": 1.0, "end": 2.0}]
    words = [{"seg": "S1", "start": 0.0, "end": 1.0}, {"seg": "S2", "start": 1.0, "end": 2.0}]
    assert [q[0] for q in quiet_segments(voice, words, timed, -10.0)] == ["S2"]
