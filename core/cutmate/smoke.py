"""5 s smoke render (title + captions, optional music bed) — what the setup wizard shows at the end."""
import json
import shutil
from pathlib import Path

from . import media
from .backends import transcribe_window
from .build import build
from .config import Config
from .errors import CutmateError
from .formats import size_of
from .media import extract_frame, run
from .render import render

SMOKE_TEXT = {"pl": "To jest test cutmate. Wszystko działa.", "en": "This is a cutmate test. Everything works."}
SMOKE_TITLE = {"pl": "Działa!", "en": "It works!"}
SMOKE_DUR = 5.0


def _make_aroll(dst: Path, clip: Path | None, fmt: str, dur: float) -> None:
    w, h = size_of(fmt)
    enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "48000"]
    if clip:
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(clip), "-t", f"{dur:.3f}",
               "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1", *enc, str(dst)]
    else:
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x1e293b:size={w}x{h}:rate=30:duration={dur:.3f}",
               "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={dur:.3f}", *enc, "-shortest", str(dst)]
    r = run(cmd)
    if r.returncode or not dst.exists():
        raise CutmateError("ffmpeg failed creating the smoke A-roll: " + " ".join(r.stderr.split())[-300:])


def _synthetic_words(language: str, dur: float) -> list[dict]:
    toks = SMOKE_TEXT[language].split()
    a, b = 0.3, dur - 0.3
    step = (b - a) / len(toks)
    return [{"seg": "S1", "word": t, "start": round(a + i * step, 2), "end": round(a + (i + 1) * step - 0.05, 2)}
            for i, t in enumerate(toks)]


def smoke(workdir: Path, cfg: Config, clip: Path | None = None, fmt: str = "9:16", music_src: Path | None = None,
          backend=None) -> dict:
    rec = Path(workdir) / "rec"
    shutil.rmtree(rec, ignore_errors=True)
    out = rec / "out"
    (out / "work").mkdir(parents=True)
    dur = SMOKE_DUR
    if clip:
        have = media.duration(Path(clip))
        if have < 2.0:
            raise CutmateError(f"clip too short for the smoke test ({have:.1f} s) — pass a recording of at least 5 s")
        dur = min(SMOKE_DUR, have)
    _make_aroll(out / "aroll.mp4", Path(clip) if clip else None, fmt, dur)
    words = None
    if clip and backend:
        wav = media.extract_wav(out / "aroll.mp4", out / "work" / "smoke.wav")
        t = transcribe_window(backend, wav, 0.0, dur, cfg.language)
        words = [{"seg": "S1", "word": w.word, "start": w.start, "end": w.end} for w in t.words]
    if words is None:
        words = _synthetic_words(cfg.language, dur)
    (out / "edl.json").write_text(json.dumps({"format": fmt, "segments": []}), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(
        json.dumps([{"id": "S1", "start": 0.0, "end": dur, "text": ""}]), encoding="utf-8")
    (out / "work" / "aligned_words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    plan = {"graphics": [{"type": "title", "at": 0.4, "until": 2.4, "kicker": "cutmate",
                          "text": SMOKE_TITLE[cfg.language]}]}
    if music_src:
        plan["music"] = {"src": str(Path(music_src).resolve()), "volume": cfg.music["volume"]}
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    r = build(out, theme=cfg.theme, language=cfg.language, music=cfg.music, captions=cfg.captions)
    for w in r["warnings"]:
        print(w)
    res = render(out)
    final = out / "final.mp4"
    frame = extract_frame(final, 1.5, out / "smoke.png")
    return {"final": final, "frame": frame, "ok": bool(res["ok"]), "lufs": res["lufs"]}
