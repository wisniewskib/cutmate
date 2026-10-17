import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_wav
from cutmate.backends import local
from cutmate.backends.local import LocalBackend, words_from_faster, words_from_mlx
from cutmate.errors import BackendError

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


def test_mlx_not_installed(monkeypatch, tmp_path):
    """mlx_whisper import fails → BackendError with setup hint."""
    monkeypatch.setitem(sys.modules, "mlx_whisper", None)
    b = LocalBackend("mlx", "mlx-community/whisper-large-v3-mlx")
    wav = tmp_path / "test.wav"
    make_wav(wav)
    with pytest.raises(BackendError, match="not installed"):
        b.transcribe(wav, "en")


def test_faster_cuda_fallback_to_cpu(monkeypatch, tmp_path, capsys):
    """WhisperModel fails on CUDA → fallback to CPU with WARN, cache on success."""
    # Create a fake WhisperModel that fails on cuda but works on cpu
    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            if device == "cuda":
                raise RuntimeError("CUDA out of memory")
            self.device = device
            self.model = model

        def transcribe(self, *args, **kwargs):
            W = lambda w, s, e, p: SimpleNamespace(word=w, start=s, end=e, probability=p)
            seg1 = SimpleNamespace(words=[W(" hello", 0.0, 0.5, 0.9)])
            return iter([seg1]), SimpleNamespace()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))

    b = LocalBackend("faster", "large-v3")
    wav = tmp_path / "test.wav"
    make_wav(wav)

    # First call should fallback and print warning
    t = b.transcribe(wav, "en")
    assert len(t.words) == 1
    assert t.words[0].word == "hello"
    captured = capsys.readouterr()
    assert "WARN local: GPU load failed" in captured.out
    assert "falling back to CPU" in captured.out

    # Verify _faster was cached (loaded on CPU)
    assert b._faster is not None
    assert b._faster.device == "cpu"
    assert b.device == "cpu"


def test_faster_transcribe_runtime_error(monkeypatch, tmp_path):
    """Transcribe raises RuntimeError → BackendError with context."""
    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            pass

        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Model corrupted")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))

    b = LocalBackend("faster", "large-v3")
    wav = tmp_path / "test.wav"
    make_wav(wav)

    with pytest.raises(BackendError, match="local transcription failed: Model corrupted"):
        b.transcribe(wav, "en")


@pytest.mark.slow
@pytest.mark.skipif(not (SAMPLES / "pl_5s.wav").exists(), reason="samples/pl_5s.wav not recorded yet")
def test_local_real_model_pl():
    t = LocalBackend.auto().transcribe(SAMPLES / "pl_5s.wav", "pl")
    assert len(t.words) >= 5 and all(w.end >= w.start for w in t.words)


def test_faster_lazy_cuda_failure_at_transcribe_falls_back_to_cpu(monkeypatch, tmp_path, capsys):
    """Model loads on cuda, but cuDNN is missing at first transcribe (generator consumed) → one WARN, CPU retry."""
    built = []

    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            self.device = device
            built.append(device)

        def transcribe(self, *args, **kwargs):
            if self.device == "cuda":
                def gen():
                    raise RuntimeError("libcudnn_ops.so.9 not found")
                    yield
                return gen(), SimpleNamespace()
            W = lambda w, s, e, p: SimpleNamespace(word=w, start=s, end=e, probability=p)
            return iter([SimpleNamespace(words=[W(" hi", 0.0, 0.5, 0.9)])]), SimpleNamespace()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    b = LocalBackend("faster", "large-v3")
    wav = tmp_path / "t.wav"
    make_wav(wav)
    assert [w.word for w in b.transcribe(wav, "en").words] == ["hi"]
    out = capsys.readouterr().out
    assert out.count("WARN local: GPU transcription failed") == 2
    assert built == ["cuda", "cuda", "cpu"]
    # cached on CPU: no further rebuilds or warnings
    b.transcribe(wav, "en")
    assert built == ["cuda", "cuda", "cpu"] and "WARN" not in capsys.readouterr().out


def test_faster_cuda_and_cpu_both_fail_raises(monkeypatch, tmp_path):
    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            pass

        def transcribe(self, *a, **k):
            raise RuntimeError("still broken")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    wav = tmp_path / "t.wav"
    make_wav(wav)
    with pytest.raises(BackendError, match="local transcription failed: still broken"):
        LocalBackend("faster", "large-v3").transcribe(wav, "en")


def test_faster_receives_decoded_audio_not_path(monkeypatch, tmp_path):
    """faster-whisper's own PyAV decoder breaks on PyAV >= 15 (metadata_errors) — we pass 16 kHz float32 audio."""
    import numpy as np
    seen = []

    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            pass

        def transcribe(self, audio, **kwargs):
            seen.append(audio)
            return iter([]), SimpleNamespace()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cpu", "int8"))
    LocalBackend("faster", "large-v3").transcribe(make_wav(tmp_path / "a.wav", dur=2.0), "pl")
    assert isinstance(seen[0], np.ndarray) and seen[0].dtype == np.float32
    assert abs(len(seen[0]) - 32000) < 400


def test_cuda_oom_float16_retries_int8_on_gpu(monkeypatch, tmp_path, capsys):
    """6 GB cards: large-v3 float16 can OOM; int8_float16 still fits on the GPU — try it before CPU."""
    built = []

    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            built.append((device, compute_type))
            if (device, compute_type) == ("cuda", "float16"):
                raise RuntimeError("CUDA failed with error out of memory")
            self.device = device

        def transcribe(self, *a, **k):
            return iter([]), SimpleNamespace()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    b = LocalBackend("faster", "large-v3")
    b.transcribe(make_wav(tmp_path / "a.wav"), "pl")
    assert built == [("cuda", "float16"), ("cuda", "int8_float16")]
    assert b.device == "cuda"
    out = capsys.readouterr().out
    assert "out of memory" in out and "int8_float16" in out


def _ladder_model(fail_on):
    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            self.key = (device, compute_type)

        def transcribe(self, *a, **k):
            if self.key in fail_on:
                raise RuntimeError("CUDA out of memory")
            W = lambda w, s, e, p: SimpleNamespace(word=w, start=s, end=e, probability=p)
            return iter([SimpleNamespace(words=[W(" hi", 0.0, 0.5, 0.9)])]), SimpleNamespace()
    return FakeWhisperModel


def test_transcribe_oom_retries_int8_float16(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "faster_whisper",
                        SimpleNamespace(WhisperModel=_ladder_model({("cuda", "float16")})))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    b = LocalBackend("faster", "large-v3")
    assert [w.word for w in b.transcribe(make_wav(tmp_path / "a.wav"), "en").words] == ["hi"]
    assert (b.device, b.compute) == ("cuda", "int8_float16")
    assert "retrying with int8_float16" in capsys.readouterr().out


def test_transcribe_gpu_failure_falls_back_to_cpu_with_hint(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(
        WhisperModel=_ladder_model({("cuda", "float16"), ("cuda", "int8_float16")})))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    b = LocalBackend("faster", "large-v3")
    b.transcribe(make_wav(tmp_path / "a.wav"), "en")
    assert (b.device, b.compute) == ("cpu", "int8")
    out = capsys.readouterr().out
    assert "transcribing on CPU" in out and "/cutmate:setup" in out


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("nvidia-smi") is None, reason="no NVIDIA GPU")
def test_gpu_transcribe_real(tmp_path):
    b = LocalBackend("faster", "tiny")
    b.transcribe(make_wav(tmp_path / "a.wav", dur=2.0), "en")
    assert b.device == "cuda"
