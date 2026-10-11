"""Step 1 — transcribe every clip in a recording folder with word timestamps + silence map.

Model word starts run ~0.25–0.5 s early after pauses: cut on silences.json bounds, not raw word starts.
SUSPECT words (> 1 s) usually hide a stumble + retake; probe that window (backends.transcribe_window).
"""
import json
from pathlib import Path

from .errors import CutmateError
from .media import extract_wav, has_audio, require_ffmpeg, silences
from .transcript import Transcript

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".mkv", ".webm"}


def find_clips(rec: Path) -> list[Path]:
    return sorted((p for p in Path(rec).iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS),
                  key=lambda p: p.name.lower())


def _report(name: str, t: Transcript, sil: list) -> None:
    print(f"\n===== {name}")
    print(" ".join(f"{w.word}@{w.start:.2f}-{w.end:.2f}" + (f"({w.prob:.2f})" if w.prob is not None and w.prob < 0.9 else "")
                   for w in t.words))
    print("silences:", " ".join(f"[{a}-{b}]" for a, b in sil))
    for w in t.suspects():
        print(f"SUSPECT long word '{w.word}' {w.start:.2f}-{w.end:.2f} → probe this window for a hidden retake")


def run_transcribe(rec: Path, backend, language: str, prompt: str | None = None, force: bool = False) -> list[Path]:
    require_ffmpeg()
    rec = Path(rec).resolve()
    clips = find_clips(rec)
    if not clips:
        raise CutmateError(f"no video files in {rec} (looked for {' '.join(sorted(VIDEO_EXTS))})")
    done = []
    for clip in clips:
        d = rec / "out" / "work" / clip.name
        tj = d / "transcript.json"
        if tj.exists() and not force:
            print(f"skip {clip.name}: already transcribed (use --force to redo)")
            done.append(d)
            continue
        if not has_audio(clip):
            print(f"WARN {clip.name}: no audio track, skipped")
            continue
        wav = extract_wav(clip, d / f"{clip.stem}.wav")
        t = backend.transcribe(wav, language, prompt)
        sil = silences(wav)
        tj.write_text(json.dumps(t.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "silences.json").write_text(json.dumps(sil), encoding="utf-8")
        _report(clip.name, t, sil)
        done.append(d)
    return done
