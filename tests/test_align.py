from pathlib import Path

import pytest

from cutmate.align import say, spans_to_words, to_tokens

VOCAB = {c: i + 5 for i, c in enumerate("abcdefghijklmnoprstuwyzóąćęłńśźż")}
VOCAB.update({"<pad>": 0, "|": 4})


def test_say_spoken_and_numbers():
    assert say("AI?", "pl", {"AI": "ej aj"}) == "ej aj"
    assert say("4", "pl", {}) == "cztery"
    assert say("4,", "en", {}) == "four"
    assert say("Claude", "pl", {}) == "Claude"


def test_to_tokens_owner_and_delimiters():
    toks, owner = to_tokens(["Ala", "ma"], VOCAB, "pl", {})
    assert toks == [VOCAB["a"], VOCAB["l"], VOCAB["a"], VOCAB["|"], VOCAB["m"], VOCAB["a"]]
    assert owner == [0, 0, 0, -1, 1, 1]


def test_to_tokens_drops_unknown_chars():
    toks, owner = to_tokens(["x-q!"], VOCAB, "pl", {})
    assert toks == [] and owner == []


def test_spans_to_words():
    out = spans_to_words(["raz", "dwa", "!"], {0: (0, 9), 1: (20, 29)}, "S1", 10.0, 11.0, 0.02)
    assert out[0] == {"seg": "S1", "word": "raz", "start": 10.0, "end": 10.2}
    assert out[1]["start"] == pytest.approx(10.4)
    assert out[2]["start"] == out[1]["end"]  # unaligned token glued to the previous word


def test_spans_to_words_infeasible():
    out = spans_to_words(["a", "b"], None, "S1", 0.0, 1.0, 0.02)
    assert [(w["start"], w["end"]) for w in out] == [(0.0, 0.5), (0.5, 1.0)]
    assert all(w["estimated"] for w in out)
