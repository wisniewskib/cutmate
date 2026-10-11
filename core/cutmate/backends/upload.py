from pathlib import Path

from ..errors import BackendError, MediaError
from ..media import run


def encode_for_upload(wav: Path, limit_bytes: int, backend: str) -> Path:
    """Mono 16 kHz 48 kbps mp3 (0.36 MB per minute, ~69 min in 25 MB) so long recordings fit API size limits."""
    dst = Path(wav).with_suffix(".upload.mp3")
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", wav, "-ac", "1", "-ar", "16000", "-b:a", "48k", dst])
    if r.returncode:
        raise MediaError(f"cannot encode {wav} for upload: {r.stderr.strip()[-300:]}")
    size = dst.stat().st_size
    if size > limit_bytes:
        raise BackendError(f"{backend}: audio is too large to upload ({size / 1e6:.1f} MB > {limit_bytes / 1e6:.0f} MB). "
                           f"Use the local backend or split the recording.")
    return dst
