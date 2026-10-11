import json
from pathlib import Path

import pytest
import responses

from cutmate.backends import get_backend, transcribe_window
from cutmate.errors import BackendError
from cutmate.transcript import Transcript, Word
from conftest import make_wav

FIX = Path(__file__).parent / "fixtures"
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"


def test_transcript_roundtrip_and_helpers():
    t = Transcript("pl", [Word("a", 0.0, 0.2), Word("długie", 0.3, 1.6, 0.4)], "groq")
    assert Transcript.from_json(t.to_json()) == t
    assert t.text() == "a długie"
    assert [w.word for w in t.suspects()] == ["długie"]
    assert t.shifted(10).words[0].start == 10.0


@responses.activate
def test_groq_word_timestamps(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    responses.post(GROQ_URL, json=json.loads((FIX / "groq_verbose.json").read_text(encoding="utf-8")))
    wav = make_wav(tmp_path / "a.wav")
    t = get_backend("groq").transcribe(wav, "pl", prompt="Claude, HyperFrames")
    assert [w.word for w in t.words] == ["Cześć,", "to", "jest", "test."]
    assert t.words[0].start == 0.12 and t.backend == "groq"
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer gsk_test"
    body = req.body
    for part in (b'name="timestamp_granularities[]"', b"verbose_json", b"whisper-large-v3", b'name="language"', b"Claude, HyperFrames"):
        assert part in body


@responses.activate
def test_openai_uses_whisper1(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    responses.post(OPENAI_URL, json=json.loads((FIX / "openai_verbose.json").read_text(encoding="utf-8")))
    t = get_backend("openai").transcribe(make_wav(tmp_path / "a.wav"), "en")
    assert [w.word for w in t.words] == ["Hello", "there."]
    assert b"whisper-1" in responses.calls[0].request.body


def test_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(BackendError, match="GROQ_API_KEY"):
        get_backend("groq").transcribe(make_wav(tmp_path / "a.wav"), "pl")


@responses.activate
def test_bad_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "wrong")
    responses.post(GROQ_URL, status=401, json={"error": {"message": "Invalid API Key"}})
    with pytest.raises(BackendError, match="rejected"):
        get_backend("groq").transcribe(make_wav(tmp_path / "a.wav"), "pl")


@responses.activate
def test_response_without_words(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    responses.post(OPENAI_URL, json={"text": "hi"})
    with pytest.raises(BackendError, match="word timestamps"):
        get_backend("openai").transcribe(make_wav(tmp_path / "a.wav"), "en")


def test_file_too_large(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    b = get_backend("groq")
    b.limit_bytes = 100
    with pytest.raises(BackendError, match="too large"):
        b.transcribe(make_wav(tmp_path / "a.wav"), "pl")


def test_unknown_backend():
    with pytest.raises(BackendError, match="unknown"):
        get_backend("whisperx")


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.durations = []

    def transcribe(self, wav, language, prompt=None):
        from cutmate.media import duration
        self.durations.append(duration(wav))
        return Transcript(language, [Word("x", 0.1, 0.3)], self.name)


def test_transcribe_window_shifts_times(tmp_path):
    fb = FakeBackend()
    t = transcribe_window(fb, make_wav(tmp_path / "a.wav", dur=3.0), 1.0, 2.2, "pl")
    assert abs(fb.durations[0] - 1.2) < 0.05
    assert t.words[0].start == pytest.approx(1.1)
