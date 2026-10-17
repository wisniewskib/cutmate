import tempfile
import time
from pathlib import Path

from . import media
from .backends import transcribe_window
from .errors import BackendError, CutmateError
from .paths import plugin_root
from .transcript import Word

SAMPLE_EXTS = ("wav", "mp3", "m4a", "mp4", "mov")


def find_sample(language: str) -> Path | None:
    for ext in SAMPLE_EXTS:
        p = plugin_root() / "samples" / f"{language}.{ext}"
        if p.exists():
            return p
    return None


def selftest(backend, language: str, clip: Path | None = None, limit: float = 30.0) -> dict:
    """Transcribe the first `limit` seconds of a clip and prove word timestamps; report the device used."""
    src = clip or find_sample(language)
    if src is None:
        raise CutmateError(f"no sample clip for {language} — pass --clip <a recording where you speak>")
    with tempfile.TemporaryDirectory() as td:
        wav = media.extract_wav(Path(src), Path(td) / "selftest.wav")
        audio = min(limit, media.duration(wav))
        t0 = time.monotonic()
        words: list[Word] = transcribe_window(backend, wav, 0.0, audio, language).words
        seconds = time.monotonic() - t0
    if not words or any(w.start >= w.end for w in words):
        raise BackendError(f"{backend.name} returned no word timestamps for {src} — is there speech in the first 30 s? "
                           "Try another clip or backend (/cutmate:setup)")
    return {"backend": backend.name, "device": getattr(backend, "device", "api"),
            "compute": getattr(backend, "compute", None), "words": words, "seconds": seconds, "audio": audio}
