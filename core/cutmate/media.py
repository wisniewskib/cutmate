"""ffmpeg / ffprobe helpers. Every call is an argument list (no shell) so any path works on every OS."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .errors import MediaError

LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


def require_ffmpeg() -> None:
    for b in ("ffmpeg", "ffprobe"):
        if shutil.which(b) is None:
            raise MediaError(f"{b} not found on PATH. Run /cutmate:setup.")


def run(cmd: list) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise MediaError(f"{cmd[0]} not found on PATH. Run /cutmate:setup.") from None


def _tail(s: str, n: int = 300) -> str:
    return s.strip()[-n:]


def duration(src: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src])
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise MediaError(f"cannot read duration of {src}: {_tail(r.stderr)}") from None


def has_audio(src: Path) -> bool:
    r = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", src])
    return bool(r.stdout.strip())


def extract_wav(src: Path, dst: Path, sr: int = 16000) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", str(sr), dst])
    if r.returncode:
        raise MediaError(f"ffmpeg could not read audio from {src}: {_tail(r.stderr)}")
    return dst


def silences(wav: Path, noise_db: float = -40, min_dur: float = 0.12) -> list[list[float]]:
    r = run(["ffmpeg", "-nostdin", "-i", wav, "-af", f"silencedetect=n={noise_db}dB:d={min_dur}", "-f", "null", "-"])
    if r.returncode:
        raise MediaError(f"cannot analyze silences in {wav}: {_tail(r.stderr)}")
    st = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    if len(st) > len(en):  # silence runs to the end of the file
        en.append(duration(wav))
    return [[round(max(a, 0.0), 3), round(b, 3)] for a, b in zip(st, en)]


def integrated_lufs(src: Path, start: float | None = None, dur: float | None = None) -> float:
    cmd = ["ffmpeg", "-nostdin"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", src, "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    r = run(cmd)
    if r.returncode:
        raise MediaError(f"cannot measure LUFS of {src}: {_tail(r.stderr)}")
    vals = re.findall(r"I:\s+(-?[0-9.]+) LUFS", r.stderr)
    v = float(vals[-1]) if vals else -70.0
    return max(v, -70.0)


def loudnorm_measure(src: Path, prefix: str = "") -> dict:
    import math
    af = (f"{prefix}," if prefix else "") + f"{LOUDNORM}:print_format=json"
    r = run(["ffmpeg", "-nostdin", "-i", src, "-vn", "-af", af, "-f", "null", "-"])
    if r.returncode:
        raise MediaError(f"loudness measurement failed for {src}: {_tail(r.stderr)}")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        raise MediaError(f"loudness measurement failed for {src}: {_tail(r.stderr)}")
    result = json.loads(m.group(0))
    input_i = result.get("input_i")
    # Check if input_i is not finite (handles "-inf", None, NaN, inf)
    try:
        if input_i is None or not math.isfinite(float(input_i)):
            raise MediaError(f"no measurable audio in {src}")
    except (ValueError, TypeError):
        raise MediaError(f"no measurable audio in {src}") from None
    return result


def loudnorm_filter(m: dict, prefix: str = "") -> str:
    return ((f"{prefix}," if prefix else "") +
            f"{LOUDNORM}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
            f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")


def read_pcm(src: Path, sr: int) -> np.ndarray:
    try:
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                           capture_output=True)
    except FileNotFoundError:
        raise MediaError("ffmpeg not found on PATH. Run /cutmate:setup.") from None
    if r.returncode:
        raise MediaError(f"cannot decode audio of {src}: {_tail(r.stderr.decode('utf-8', 'replace'))}")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def probe_video(src: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration", "-of", "json", src])
    if r.returncode:
        raise MediaError(f"cannot probe {src}: {_tail(r.stderr)}")
    p = json.loads(r.stdout)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), {})
    if not v:
        raise MediaError(f"no video stream in {src}")
    duration_val = p.get("format", {}).get("duration")
    if duration_val is None or duration_val == "N/A":
        raise MediaError(f"cannot read duration of {src}")
    try:
        duration_float = float(duration_val)
    except (ValueError, TypeError):
        raise MediaError(f"invalid duration in {src}: {duration_val}") from None
    return dict(width=v.get("width"), height=v.get("height"), fps=v.get("r_frame_rate"),
                vcodec=v.get("codec_name"), acodec=a.get("codec_name"), duration=duration_float)


def extract_frame(src: Path, t: float, dst: Path) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", dst])
    if r.returncode or not dst.exists():
        raise MediaError(f"cannot extract frame at {t:.2f}s from {src}: {_tail(r.stderr)}")
    return dst
