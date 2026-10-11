import tempfile
from pathlib import Path
from typing import Protocol

from ..errors import BackendError, MediaError
from ..media import run
from ..transcript import Transcript

MB = 1_000_000


class Backend(Protocol):
    name: str

    def transcribe(self, wav: Path, language: str, prompt: str | None = None) -> Transcript: ...


def get_backend(name: str) -> Backend:
    from .openai_compat import OpenAICompatBackend
    if name == "groq":
        return OpenAICompatBackend("groq", "https://api.groq.com/openai/v1/audio/transcriptions",
                                   "GROQ_API_KEY", "whisper-large-v3", 25 * MB)
    if name == "openai":
        return OpenAICompatBackend("openai", "https://api.openai.com/v1/audio/transcriptions",
                                   "OPENAI_API_KEY", "whisper-1", 25 * MB)
    if name == "elevenlabs":
        from .elevenlabs import ElevenLabsBackend
        return ElevenLabsBackend()
    if name == "local":
        from .local import LocalBackend
        return LocalBackend.auto()
    raise BackendError(f"unknown transcription backend {name!r}; use local, groq, openai or elevenlabs")


def transcribe_window(backend: Backend, wav: Path, start: float, end: float, language: str,
                      prompt: str | None = None) -> Transcript:
    """Transcribe wav[start:end]; returned word times are global (seconds in the full wav)."""
    with tempfile.TemporaryDirectory() as td:
        part = Path(td) / "window.wav"
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                 "-i", wav, "-ac", "1", "-ar", "16000", part])
        if r.returncode:
            raise MediaError(f"cannot cut window {start:.2f}-{end:.2f} from {wav}")
        return backend.transcribe(part, language, prompt).shifted(start)
