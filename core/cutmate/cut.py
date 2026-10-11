"""Step 4 — cut the A-roll from an EDL: per-segment encode (memory-safe for 4K), cuts snapped to the fps grid
(no A/V drift), every segment levelled to the median segment loudness (±8 dB), 15/30 ms audio fades per cut,
gentle compressor, two-pass loudnorm to -14 LUFS."""
import json
from pathlib import Path

from .errors import EDLError, MediaError
from .formats import size_of
from .media import (duration, has_audio, integrated_lufs, loudnorm_filter, loudnorm_measure, require_ffmpeg, run)

COMP = "acompressor=threshold=-26dB:ratio=3:attack=8:release=220:makeup=1"


def _tail(s: str, n: int = 400) -> str:
    return " ".join(s.split())[-n:]


def source_of(edl_path: Path, seg: dict) -> Path:
    edl_path = Path(edl_path)
    if "path" in seg:
        return (edl_path.parent / seg["path"]).resolve()
    return edl_path.parent.parent / seg["file"]


def load_edl(edl_path: Path) -> dict:
    edl_path = Path(edl_path)
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EDLError(f"EDL not found: {edl_path}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise EDLError(f"{edl_path}: not valid JSON ({' '.join(str(e).split())})") from None
    if not isinstance(edl, dict):
        raise EDLError(f"{edl_path}: EDL must be a JSON object")
    segs = edl.get("segments") or []
    if not segs:
        raise EDLError(f"{edl_path}: EDL has no segments")
    size_of(edl.get("format", "9:16"))
    for k, s in enumerate(segs):
        if not isinstance(s, dict):
            raise EDLError(f"segment #{k}: must be a JSON object")
        sid = s.get("id", f"#{k}")
        for key in ("in", "out"):
            if key not in s:
                raise EDLError(f"segment {sid}: missing \"{key}\"")
        if "file" not in s and "path" not in s:
            raise EDLError(f"segment {sid}: needs \"file\" or \"path\"")
        if isinstance(s["in"], bool) or isinstance(s["out"], bool) or not all(
                isinstance(s[key], (int, float)) for key in ("in", "out")):
            raise EDLError(f"segment {sid}: \"in\" and \"out\" must be numbers")
        src = source_of(edl_path, s)
        if not src.exists():
            raise EDLError(f"segment {sid}: source not found: {src}")
        if s["out"] <= s["in"]:
            raise EDLError(f"segment {sid}: out ({s['out']}) must be after in ({s['in']})")
        total = duration(src)
        if s["out"] > total + 0.05:
            raise EDLError(f"segment {sid}: out {s['out']} is longer than {src.name} ({total:.2f}s)")
        if not has_audio(src):
            raise EDLError(f"segment {sid}: {src.name} has no audio track")
    return edl


def _snap(t: float, fps: int) -> float:
    return round(t * fps) / fps


def cut_aroll(edl_path: Path) -> list[dict]:
    require_ffmpeg()
    edl_path = Path(edl_path).resolve()
    edl = load_edl(edl_path)
    out = edl_path.parent
    work, segdir = out / "work", out / "work" / "segs"
    segdir.mkdir(parents=True, exist_ok=True)
    fps = int(edl.get("fps", 30))
    w, h = size_of(edl.get("format", "9:16"))
    segs = edl["segments"]
    bounds = [(_snap(s["in"], fps), _snap(s["out"], fps)) for s in segs]
    levels = [integrated_lufs(source_of(edl_path, s), a, b - a) for s, (a, b) in zip(segs, bounds)]
    valid = sorted(v for v in levels if v > -60)
    target = valid[len(valid) // 2] if valid else -30.0
    scale = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1"

    parts = []
    for k, (s, (a, b), lv) in enumerate(zip(segs, bounds, levels)):
        d, pre = b - a, max(0.0, a - 2.0)  # fast seek to 2 s before, accurate trim inside the filters
        gain = 0.0 if lv < -60 else max(-8.0, min(8.0, target - lv))
        s["gain_db"] = round(gain, 1)
        part = segdir / f"{k:03d}.mov"
        r = run(["ffmpeg", "-nostdin", "-y", "-threads", "4", "-ss", f"{pre:.3f}", "-i", source_of(edl_path, s),
                 "-vf", f"trim=start={a - pre:.3f}:duration={d:.3f},setpts=PTS-STARTPTS,{scale},fps={fps},format=yuv420p",
                 "-af", f"atrim=start={a - pre:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,"
                        f"aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur={d:.4f},atrim=duration={d:.4f},"
                        f"volume={gain:.1f}dB,afade=t=in:d=0.015,afade=t=out:st={max(0.0, d - 0.03):.3f}:d=0.03",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(fps), "-pix_fmt", "yuv420p",
                 "-c:a", "pcm_s16le", part])
        if r.returncode:
            raise MediaError(f"segment {s.get('id', k)}: ffmpeg failed: {_tail(r.stderr)}")
        parts.append(part)

    # relative names: the concat demuxer resolves them next to list.txt (no quoting issues with any path)
    (segdir / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    raw = work / "aroll_raw.mov"
    r = run(["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", segdir / "list.txt", "-c", "copy", raw])
    if r.returncode:
        raise MediaError(f"joining segments failed: {_tail(r.stderr)}")
    af = loudnorm_filter(loudnorm_measure(raw, prefix=COMP), prefix=COMP)
    r = run(["ffmpeg", "-nostdin", "-y", "-i", raw, "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "256k",
             "-movflags", "+faststart", out / "aroll.mp4"])
    if r.returncode:
        raise MediaError(f"loudness normalisation failed: {_tail(r.stderr)}")

    t, timed = 0.0, []
    for s, p in zip(segs, parts):
        d = duration(p)
        timed.append(dict(s, start=round(t, 3), end=round(t + d, 3)))
        t += d
    (work / "edl_timed.json").write_text(json.dumps(timed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"aroll.mp4: {t:.2f}s, {len(segs)} segments, {integrated_lufs(out / 'aroll.mp4'):.1f} LUFS")
    for s in timed:
        print(f"  {s.get('id', ''):4} {s['start']:6.2f}–{s['end']:6.2f}  gain {s['gain_db']:+.1f} dB  {s.get('text', '')[:60]}")
    return timed
