import platform
import sys
from pathlib import Path

from ..errors import BackendError
from ..transcript import Transcript, Word


def words_from_mlx(result: dict) -> list[Word]:
    return [Word(w["word"].strip(), float(w["start"]), float(w["end"]), float(w["probability"]))
            for s in result.get("segments", []) for w in s.get("words", []) if w["word"].strip()]


def words_from_faster(segments) -> list[Word]:
    return [Word(w.word.strip(), float(w.start), float(w.end), float(w.probability))
            for s in segments for w in (s.words or []) if w.word.strip()]


def pick_device() -> tuple[str, str]:
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


class LocalBackend:
    name = "local"

    def __init__(self, engine: str, model: str):
        self.engine, self.model = engine, model
        self._faster = None
        self._device = None

    @classmethod
    def auto(cls) -> "LocalBackend":
        if sys.platform == "darwin" and platform.machine() == "arm64":
            return cls("mlx", "mlx-community/whisper-large-v3-mlx")
        return cls("faster", "large-v3")

    def transcribe(self, wav: Path, language: str, prompt: str | None = None) -> Transcript:
        if self.engine == "mlx":
            try:
                import mlx_whisper
            except ImportError:
                raise BackendError("mlx-whisper is not installed. Run /cutmate:setup.") from None
            try:
                r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=self.model, word_timestamps=True, language=language,
                                           initial_prompt=prompt, condition_on_previous_text=False, temperature=0.0)
                return Transcript(language, words_from_mlx(r), self.name)
            except BackendError:
                raise
            except Exception as e:
                raise BackendError(f"local transcription failed: {e}") from None
        if self._faster is None:
            self._faster = self._load()
        try:
            return self._run_faster(wav, language, prompt)
        except Exception as e:
            if self._device != "cuda":
                raise BackendError(f"local transcription failed: {e}") from None
            # cuDNN/cuBLAS load lazily at the first transcribe, so GPU failures surface here, not at model load
            print(f"WARN local: GPU transcription failed ({type(e).__name__}), falling back to CPU")
            self._faster, self._device = self._build("cpu", "int8"), "cpu"
            try:
                return self._run_faster(wav, language, prompt)
            except Exception as e2:
                raise BackendError(f"local transcription failed: {e2}") from None

    def _build(self, device: str, compute: str):
        from faster_whisper import WhisperModel
        return WhisperModel(self.model, device=device, compute_type=compute)

    def _load(self):
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            raise BackendError("faster-whisper is not installed. Run /cutmate:setup.") from None
        device, compute = pick_device()
        try:
            model = self._build(device, compute)
        except Exception as e:
            if device != "cuda":
                raise BackendError(f"local model load failed: {e}") from None
            print(f"WARN local: GPU load failed ({type(e).__name__}), falling back to CPU")
            device = "cpu"
            try:
                model = self._build("cpu", "int8")
            except Exception as e2:
                raise BackendError(f"local model load failed: {e2}") from None
        self._device = device
        return model

    def _run_faster(self, wav: Path, language: str, prompt: str | None) -> Transcript:
        segments, _info = self._faster.transcribe(str(wav), word_timestamps=True, language=language,
                                                  initial_prompt=prompt, condition_on_previous_text=False,
                                                  temperature=0)
        return Transcript(language, words_from_faster(segments), self.name)  # consumes the lazy generator
