from pathlib import Path
from types import SimpleNamespace

import pytest

from cutmate.backends import local
from cutmate.backends.local import LocalBackend, words_from_faster, words_from_mlx

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_auto_picks_mlx_on_apple_silicon(monkeypatch):
    monkeypatch.setattr(local.sys, "platform", "darwin")
    monkeypatch.setattr(local.platform, "machine", lambda: "arm64")
    b = LocalBackend.auto()
    assert (b.engine, b.model) == ("mlx", "mlx-community/whisper-large-v3-mlx")


@pytest.mark.parametrize("plat,machine", [("linux", "x86_64"), ("win32", "AMD64"), ("darwin", "x86_64")])
def test_auto_picks_faster_elsewhere(monkeypatch, plat, machine):
    monkeypatch.setattr(local.sys, "platform", plat)
    monkeypatch.setattr(local.platform, "machine", lambda: machine)
    b = LocalBackend.auto()
    assert (b.engine, b.model) == ("faster", "large-v3")


def test_words_from_mlx():
    r = {"segments": [{"words": [{"word": " Cześć", "start": 0.1, "end": 0.4, "probability": 0.9},
                                 {"word": " ", "start": 0.4, "end": 0.4, "probability": 0.1}]},
                      {"words": [{"word": " test", "start": 0.5, "end": 0.9, "probability": 0.8}]}]}
    assert [(w.word, w.start, w.prob) for w in words_from_mlx(r)] == [("Cześć", 0.1, 0.9), ("test", 0.5, 0.8)]


def test_words_from_faster():
    W = lambda w, s, e, p: SimpleNamespace(word=w, start=s, end=e, probability=p)
    segs = iter([SimpleNamespace(words=[W(" Hello", 0.0, 0.3, 0.95)]), SimpleNamespace(words=None),
                 SimpleNamespace(words=[W(" world", 0.4, 0.8, 0.7)])])
    assert [w.word for w in words_from_faster(segs)] == ["Hello", "world"]


@pytest.mark.slow
@pytest.mark.skipif(not (SAMPLES / "pl_5s.wav").exists(), reason="samples/pl_5s.wav not recorded yet")
def test_local_real_model_pl():
    t = LocalBackend.auto().transcribe(SAMPLES / "pl_5s.wav", "pl")
    assert len(t.words) >= 5 and all(w.end >= w.start for w in t.words)
