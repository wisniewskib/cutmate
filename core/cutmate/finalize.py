"""Step 8 — after `hyperframes render`: bring the FULL mix to -14 LUFS (the mixer leaves ~1 dB headroom) without
re-encoding video, verify delivery specs, extract check frames for Claude to look at."""
from pathlib import Path

from .errors import MediaError
from .formats import size_of
from .media import (extract_frame, integrated_lufs, loudnorm_filter, loudnorm_measure, probe_video, require_ffmpeg, run)


def finalize(src: Path, dst: Path, fmt: str = "9:16", fps: int = 30, check=()) -> dict:
    require_ffmpeg()
    src, dst = Path(src), Path(dst)
    af = loudnorm_filter(loudnorm_measure(src))
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-c:v", "copy", "-af", af, "-c:a", "aac",
             "-b:a", "256k", "-movflags", "+faststart", dst])
    if r.returncode:
        raise MediaError(f"finalize failed: {' '.join(r.stderr.split())[-400:]}")
    info = probe_video(dst)
    w, h = size_of(fmt)
    info["lufs"] = integrated_lufs(dst)
    info["ok"] = (info["width"], info["height"], info["fps"], info["vcodec"], info["acodec"]) == (w, h, f"{fps}/1", "h264", "aac")
    info["frames"] = [extract_frame(dst, t, dst.parent / (f"check_{t:.2f}".replace(".", "_") + ".png")) for t in check]
    print(f"{dst.name}: {info['width']}x{info['height']} {info['fps']} {info['vcodec']} + {info['acodec']}, "
          f"{info['duration']:.2f}s, {info['lufs']:.1f} LUFS — {'OK' if info['ok'] else f'SPEC MISMATCH (expected {w}x{h} {fps}/1 h264 + aac)'}")
    for p in info["frames"]:
        print("frame:", p)
    return info
