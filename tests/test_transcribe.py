import json

import pytest

from cutmate.errors import CutmateError
from cutmate.transcribe import find_clips, run_transcribe
from cutmate.transcript import Transcript, Word
from conftest import make_clip


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def transcribe(self, wav, language, prompt=None):
        self.calls += 1
        return Transcript(language, [Word("Cześć", 0.1, 0.5, 0.95), Word("długieeee", 0.6, 1.9, 0.5)], self.name)


def test_find_clips_filters_and_sorts(tmp_path):
    for n in ("b.MOV", "a.mp4", "notes.txt", "c.wav"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in find_clips(tmp_path)] == ["a.mp4", "b.MOV"]


def test_find_clips_skips_apledouble(tmp_path):
    for n in ("._b.MOV", "a.mp4", ".hidden.mov"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in find_clips(tmp_path)] == ["a.mp4"]


def test_empty_folder_raises(tmp_path):
    with pytest.raises(CutmateError, match="no video files"):
        run_transcribe(tmp_path, FakeBackend(), "pl")


def test_writes_outputs_and_reports(tmp_path, capsys):
    rec = tmp_path / "nagranie ąę"
    make_clip(rec / "take1.mp4")
    dirs = run_transcribe(rec, FakeBackend(), "pl")
    d = rec / "out" / "work" / "take1.mp4"
    assert dirs == [d]
    t = Transcript.from_json(json.loads((d / "transcript.json").read_text(encoding="utf-8")))
    assert t.words[0].word == "Cześć"
    assert json.loads((d / "silences.json").read_text())[0][0] == pytest.approx(1.0, abs=0.06)
    out = capsys.readouterr().out
    assert "===== take1.mp4" in out and "SUSPECT" in out and "długieeee" in out


def test_resume_skips_done_clips(tmp_path, capsys):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    fb = FakeBackend()
    run_transcribe(rec, fb, "pl")
    d = rec / "out" / "work" / "take1.mp4"
    dirs = run_transcribe(rec, fb, "pl")
    assert fb.calls == 1
    assert dirs == [d]
    assert "skip take1.mp4: already transcribed" in capsys.readouterr().out
    run_transcribe(rec, fb, "pl", force=True)
    assert fb.calls == 2


def test_resume_retranscribes_incomplete(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    fb = FakeBackend()
    run_transcribe(rec, fb, "pl")
    assert fb.calls == 1
    d = rec / "out" / "work" / "take1.mp4"
    # Simulate incomplete write: only transcript.json, no silences.json
    (d / "silences.json").unlink()
    run_transcribe(rec, fb, "pl")
    assert fb.calls == 2


def test_clip_without_audio_is_skipped(tmp_path, capsys):
    rec = tmp_path / "rec"
    make_clip(rec / "broll.mp4", audio=False)
    make_clip(rec / "take1.mp4")
    dirs = run_transcribe(rec, FakeBackend(), "pl")
    assert [d.name for d in dirs] == ["take1.mp4"]
    assert "WARN broll.mp4: no audio track, skipped" in capsys.readouterr().out
