"""Step 9 — QA before delivery.
1. Repeats: re-transcribe the CUT A-roll and flag repeated words / trailing „…" (missed false starts).
2. Mix: loudest-400 ms RMS of final.mp4 vs the voice every 0.1 s — LOUD = SFX/music > 3 dB over the voice;
   QUIET = a segment whose speech sits > 4 dB under the voice median."""
import json
import re
from pathlib import Path

import numpy as np

from .backends import transcribe_window
from .errors import CutmateError
from .media import duration, extract_wav, read_pcm

SR, N, HOP = 48000, 19200, 4800
FILLERS = {"pl": {"no", "eee", "yyy", "hmm"}, "en": {"um", "uh", "er", "hmm"}}
FILLER_PROMPT = {"pl": "Yyy, eee, no, hmm.", "en": "Um, uh, er, hmm."}


def window_db(x: np.ndarray) -> np.ndarray:
    c = np.cumsum(np.concatenate([[0.0], x.astype(np.float64) ** 2]))
    hi = c[N::HOP]
    e = (hi - c[:-N:HOP][:len(hi)]) / N
    return 10 * np.log10(e + 1e-12)


def mix_scan(mix: np.ndarray, voice: np.ndarray) -> tuple[float, list[tuple[float, float, float]]]:
    L = min(len(mix), len(voice))
    m, v = window_db(mix[:L]), window_db(voice[:L])
    speech = v[v > -35]
    med = float(np.median(speech)) if len(speech) else -20.0
    over = m - np.maximum(v, med - 6)
    loud = np.where((over > 3) & (m - med > 0))[0]
    runs, start = [], None
    for i, j in zip(loud, list(loud[1:]) + [None]):
        start = i if start is None else start
        if j is None or j != i + 1:
            runs.append((start * 0.1, i * 0.1 + 0.4, float(over[start:i + 1].max())))
            start = None
    return med, runs


def quiet_segments(voice: np.ndarray, words: list[dict], timed: list[dict], med: float) -> list[tuple[str, float, float]]:
    out = []
    for s in timed:
        ws = [w for w in words if w["seg"] == s["id"]]
        if not ws:
            continue
        seg = np.concatenate([voice[int(w["start"] * SR):int(w["end"] * SR)] for w in ws])
        lv = 20 * np.log10(np.sqrt(np.mean(seg.astype(np.float64) ** 2)) + 1e-9)
        if lv < med - 4:
            out.append((s["id"], s["start"], lv - med))
    return out


def has_repeat(words: list[str]) -> bool:
    """Detect false starts, repeated words, and stumbles in speech.

    Rules (any one triggers True):
    a) Two adjacent identical non-empty words
    b) "…" or "..." appears in text
    c) Bigram (w[i], w[i+1]) reappears with ≤2 words between
    d) Word of ≥5 chars reappears exactly 2 positions later (X Y X)
    e) Word of ≥3 chars is strict prefix of immediately following word (false start)
    """
    ws = [w.lower().strip(",.?!") for w in words]
    txt = " ".join(ws)

    # Rule b: Ellipsis markers
    if "…" in txt or "..." in txt:
        return True

    # Rule a: Adjacent identical non-empty words
    if any(x and x == y for x, y in zip(ws, ws[1:])):
        return True

    # Rule c: Bigram repeats with ≤2 words between
    for i in range(len(ws) - 1):
        bigram = (ws[i], ws[i + 1])
        for j in range(i + 2, min(i + 5, len(ws) - 1)):  # j from i+2 to i+4 inclusive
            if j < len(ws) - 1 and (ws[j], ws[j + 1]) == bigram:
                return True

    # Rule d: Word of ≥5 chars reappears exactly 2 positions later (X Y X)
    for i in range(len(ws) - 2):
        if len(ws[i]) >= 5 and ws[i] == ws[i + 2]:
            return True

    # Rule e: Word of ≥3 chars is strict prefix of next word (false start)
    for i in range(len(ws) - 1):
        if len(ws[i]) >= 3 and ws[i + 1].startswith(ws[i]) and ws[i] != ws[i + 1]:
            return True

    return False


def _repeats_local(backend, wav: Path, language: str) -> list[tuple[float, str]]:
    hits, end, t = [], duration(wav), 0.0
    fillers = FILLERS[language] | {""}
    while t < end - 0.3:
        ws = [w.word for w in transcribe_window(backend, wav, t, min(end, t + 1.2), language, FILLER_PROMPT[language]).words]
        if not set(w.lower().strip(",.?!") for w in ws) <= fillers and has_repeat(ws):  # skip hallucinated filler prompt
            hits.append((t, " ".join(ws)))
        t += 0.6
    return hits


def _repeats_api(backend, wav: Path, language: str) -> list[tuple[float, str]]:
    words = backend.transcribe(wav, language, FILLER_PROMPT[language]).words
    hits, last = [], -1.0
    for i in range(len(words)):
        win = words[i:i + 6]
        if has_repeat([w.word for w in win]) and win[0].start - last > 1.0:
            hits.append((win[0].start, " ".join(w.word for w in win)))
            last = win[0].start
    return hits


def run_qa(out_dir: Path, backend, language: str, asr: bool = True) -> list[str]:
    out = Path(out_dir)

    # Check for backend requirement before reading files
    if asr and backend is None:
        raise CutmateError("a transcription backend is required for the repeat check")

    # Check for required files
    required_files = [
        (out / "final.mp4", "run `cutmate finalize` first"),
        (out / "aroll.mp4", "run `cutmate cut` first"),
        (out / "work" / "aligned_words.json", "run `cutmate align` first"),
        (out / "work" / "edl_timed.json", "run `cutmate cut` first"),
    ]

    for file_path, step in required_files:
        if not file_path.exists():
            raise CutmateError(f"{file_path.name} is missing; {step}")

    lines = []

    def emit(*new: str) -> None:
        for line in new:
            print(line)
        lines.extend(new)

    mix, voice = read_pcm(out / "final.mp4", SR), read_pcm(out / "aroll.mp4", SR)
    med, runs = mix_scan(mix, voice)
    emit(f"== mix: voice median {med:.1f} dB")
    emit(*[f"  LOUD {s:5.1f}–{e:5.1f}s  SFX/music {o:+.1f} dB over the voice" for s, e, o in runs])
    words = json.loads((out / "work" / "aligned_words.json").read_text(encoding="utf-8"))
    timed = json.loads((out / "work" / "edl_timed.json").read_text(encoding="utf-8"))
    emit(*[f"  QUIET {sid} {st:.1f}s speech {d:+.1f} dB" for sid, st, d in quiet_segments(voice, words, timed, med)])
    if asr:
        wav = extract_wav(out / "aroll.mp4", out / "work" / "qa_aroll.wav")
        hits = _repeats_local(backend, wav, language) if backend.name == "local" else _repeats_api(backend, wav, language)
        emit("== repeats" + (" (1.2 s windows)" if backend.name == "local" else " (full pass)"))
        emit(*[f"  {t:5.1f}s  {txt}" for t, txt in hits])
    return lines
