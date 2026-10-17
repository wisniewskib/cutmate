import pytest

from cutmate import cli, media, selftest as st
from cutmate.errors import BackendError, CutmateError
from cutmate.transcript import Transcript, Word
from conftest import make_clip


class ApiFake:
    name = "fake"

    def __init__(self, words=None):
        self.seen = None
        self.words = [Word("Cześć", 0.12, 0.40), Word("świecie", 0.5, 0.9)] if words is None else words

    def transcribe(self, wav, language, prompt=None):
        self.seen = media.duration(wav)
        return Transcript(language, list(self.words), self.name)


class FakeBackend(ApiFake):
    device = "cuda"
    compute = "float16"


def test_selftest_reports_device(tmp_path):
    clip = make_clip(tmp_path / "a.mp4", dur=3)
    r = st.selftest(FakeBackend(), "pl", clip)
    assert r["device"] == "cuda" and r["compute"] == "float16" and r["backend"] == "fake"
    assert len(r["words"]) == 2
    assert r["audio"] == pytest.approx(3.0, abs=0.1)


def test_selftest_limits_to_30s(tmp_path):
    clip = make_clip(tmp_path / "a.mp4", dur=35, size="320x240")
    fb = FakeBackend()
    st.selftest(fb, "pl", clip)
    assert fb.seen <= 30.1


def test_selftest_no_words(tmp_path):
    clip = make_clip(tmp_path / "a.mp4", dur=3)
    with pytest.raises(BackendError, match="no word timestamps"):
        st.selftest(FakeBackend(words=[]), "pl", clip)


def test_selftest_needs_clip(monkeypatch):
    monkeypatch.setattr(st, "find_sample", lambda lang: None)
    with pytest.raises(CutmateError, match="--clip"):
        st.selftest(FakeBackend(), "pl")


def test_selftest_api_backend_device(tmp_path):
    clip = make_clip(tmp_path / "a.mp4", dur=3)
    r = st.selftest(ApiFake(), "pl", clip)
    assert r["device"] == "api" and r["compute"] is None


def test_selftest_cli_output(tmp_path, monkeypatch, capsys):
    clip = make_clip(tmp_path / "a.mp4", dur=3)
    monkeypatch.setattr(cli, "get_backend", lambda name: FakeBackend())
    assert cli.main(["selftest", "--clip", str(clip)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert lines[0] == "backend: fake · device: cuda · compute: float16"
    assert lines[1].startswith("words: 2 in ")
    assert lines[2] == "first: Cześć@0.12-0.40 świecie@0.50-0.90"


class MlxFake(ApiFake):
    name = "local"
    engine = "mlx"
    device = None
    compute = None


def test_selftest_mlx_device(tmp_path, monkeypatch, capsys):
    clip = make_clip(tmp_path / "a.mp4", dur=3)
    assert st.selftest(MlxFake(), "pl", clip)["device"] == "mlx"
    monkeypatch.setattr(cli, "get_backend", lambda name: MlxFake())
    assert cli.main(["selftest", "--clip", str(clip)]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "backend: local · device: mlx"
