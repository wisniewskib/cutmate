import numpy as np

from cutmate.ctc import ctc_spans


def lp_from_labels(labels, n=3):
    lp = np.full((len(labels), n), np.log(0.05))
    for t, l in enumerate(labels):
        lp[t, l] = np.log(0.9)
    return lp


def test_two_words():
    lp = lp_from_labels([0, 1, 1, 0, 2, 0])
    assert ctc_spans(lp, [1, 2], [0, 1], blank=0) == {0: (1, 2), 1: (4, 4)}


def test_repeated_token_needs_blank_between():
    lp = lp_from_labels([1, 0, 1])
    assert ctc_spans(lp, [1, 1], [0, 0], blank=0) == {0: (0, 2)}


def test_infeasible_returns_none():
    assert ctc_spans(lp_from_labels([1]), [1, 2], [0, 1], blank=0) is None
    assert ctc_spans(lp_from_labels([1, 1]), [1, 1], [0, 0], blank=0) is None


def test_empty_tokens():
    assert ctc_spans(lp_from_labels([0, 0]), [], [], blank=0) == {}
