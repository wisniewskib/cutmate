"""Step 5 — word timings: CTC forced alignment of the corrected EDL text onto aroll.mp4 (wav2vec2).
Numbers / English terms must be spelled the way they are SAID ("spoken" map in edl.json) or the aligner drifts."""
import json
import re
from pathlib import Path

from .ctc import ctc_spans
from .media import read_pcm

SR = 16000
MODELS = {"pl": "jonatasgrosman/wav2vec2-large-xlsr-53-polish",
          "en": "jonatasgrosman/wav2vec2-large-xlsr-53-english"}
SPOKEN = {"pl": {"AI": "ej aj", "GPT": "dżi pi ti", "OpenAI": "opęn ej aj", "Claude": "klod", "Google": "gugl",
                 "Gemini": "dżemini"},
          "en": {"AI": "a i", "GPT": "g p t"}}
NUMBERS = {"pl": ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć", "dziesięć"],
           "en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]}


def say(word: str, language: str, spoken: dict) -> str:
    core = re.sub(r"[^\w]", "", word)
    for k in (word, core):
        if k in spoken:
            return spoken[k]
    if core.isdigit() and int(core) <= 10:
        return NUMBERS[language][int(core)]
    return word


def to_tokens(words: list[str], vocab: dict, language: str, spoken: dict) -> tuple[list[int], list[int]]:
    toks, owner = [], []
    for wi, w in enumerate(words):
        for ch in say(w, language, spoken).lower().replace(" ", "|"):
            if ch in vocab:
                toks.append(vocab[ch])
                owner.append(wi)
        if wi < len(words) - 1 and "|" in vocab and toks and toks[-1] != vocab["|"]:
            toks.append(vocab["|"])
            owner.append(-1)
    if toks and toks[-1] == vocab.get("|"):
        toks.pop()
        owner.pop()
    return toks, owner


def spans_to_words(words: list[str], spans, seg_id: str, seg_start: float, seg_end: float, fdur: float) -> list[dict]:
    if spans is None:  # text doesn't fit the audio → spread evenly, flagged
        step = (seg_end - seg_start) / max(1, len(words))
        return [dict(seg=seg_id, word=w, start=round(seg_start + i * step, 3), end=round(seg_start + (i + 1) * step, 3),
                     estimated=True) for i, w in enumerate(words)]
    out: list[dict] = []
    for wi, w in enumerate(words):
        if wi not in spans:  # punctuation-only token → glue to the previous word
            st = out[-1]["end"] if out else seg_start
            out.append(dict(seg=seg_id, word=w, start=round(st, 3), end=round(st + 0.1, 3)))
            continue
        f0, f1 = spans[wi]
        out.append(dict(seg=seg_id, word=w, start=round(seg_start + f0 * fdur, 3), end=round(seg_start + (f1 + 1) * fdur, 3)))
    return out


def run_align(edl_path: Path, language: str) -> list[dict]:
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    edl_path = Path(edl_path).resolve()
    out = edl_path.parent
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    spoken = {**SPOKEN[language], **edl.get("spoken", {})}
    timed = json.loads((out / "work" / "edl_timed.json").read_text(encoding="utf-8"))
    proc = Wav2Vec2Processor.from_pretrained(MODELS[language])
    model = Wav2Vec2ForCTC.from_pretrained(MODELS[language]).eval()
    vocab = proc.tokenizer.get_vocab()
    blank = proc.tokenizer.pad_token_id
    audio = read_pcm(out / "aroll.mp4", SR)
    words_out: list[dict] = []
    for i, seg in enumerate(timed):
        sid = seg.get("id", f"#{i}")
        disp = (seg.get("text") or "").split()
        if not disp:
            continue
        a = audio[int(seg["start"] * SR):int(seg["end"] * SR)]
        spans, fdur = None, 0.0
        if len(a) >= SR // 10:
            with torch.no_grad():
                logits = model(proc(a, sampling_rate=SR, return_tensors="pt").input_values).logits[0]
            lp = torch.log_softmax(logits, -1).numpy()
            fdur = len(a) / SR / lp.shape[0]
            toks, owner = to_tokens(disp, vocab, language, spoken)
            spans = ctc_spans(lp, toks, owner, blank)
        if spans is None:
            print(f"WARN {sid}: audio too short for its text — word times estimated")
        words_out += spans_to_words(disp, spans, sid, seg["start"], seg["end"], fdur)
    (out / "work" / "aligned_words.json").write_text(json.dumps(words_out, ensure_ascii=False, indent=0), encoding="utf-8")
    for w in words_out:
        print(f"{w['seg']:4} {w['start']:6.2f}-{w['end']:6.2f} {w['word']}" + ("  (estimated)" if w.get("estimated") else ""))
    return words_out
