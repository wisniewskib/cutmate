import json
import math
from pathlib import Path

import pytest
import responses

from cutmate.backends import get_backend
from cutmate.errors import BackendError
from conftest import make_wav

URL = "https://api.elevenlabs.io/v1/speech-to-text"
FIX = Path(__file__).parent / "fixtures"


@responses.activate
def test_elevenlabs_words_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test")
    responses.post(URL, json=json.loads((FIX / "elevenlabs.json").read_text(encoding="utf-8")))
    t = get_backend("elevenlabs").transcribe(make_wav(tmp_path / "a.wav"), "pl")
    assert [w.word for w in t.words] == ["Cześć", "wszystkim"]
    assert t.words[1].prob == pytest.approx(math.exp(-0.7))
    req = responses.calls[0].request
    assert req.headers["xi-api-key"] == "el_test"
    for part in (b"scribe_v2", b'name="timestamps_granularity"', b'name="language_code"'):
        assert part in req.body


def test_elevenlabs_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(BackendError, match="ELEVENLABS_API_KEY"):
        get_backend("elevenlabs").transcribe(make_wav(tmp_path / "a.wav"), "pl")


@responses.activate
def test_elevenlabs_http_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test")
    responses.post(URL, status=401, json={"detail": {"status": "invalid_api_key"}})
    with pytest.raises(BackendError, match="rejected"):
        get_backend("elevenlabs").transcribe(make_wav(tmp_path / "a.wav"), "pl")


@responses.activate
def test_elevenlabs_malformed_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test")
    responses.post(URL, body="<html>oops</html>", status=200)
    with pytest.raises(BackendError, match="unexpected response format"):
        get_backend("elevenlabs").transcribe(make_wav(tmp_path / "a.wav"), "pl")


@responses.activate
def test_elevenlabs_file_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test")
    responses.post(URL, json=json.loads((FIX / "elevenlabs.json").read_text(encoding="utf-8")))
    get_backend("elevenlabs").transcribe(make_wav(tmp_path / "a.wav"), "pl")
    assert not list(tmp_path.glob("*.upload.mp3"))
