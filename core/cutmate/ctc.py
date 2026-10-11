"""CTC Viterbi forced alignment (numpy). Pure function, no model."""
import numpy as np

NEG = -1e9


def ctc_spans(lp: np.ndarray, toks: list[int], owner: list[int], blank: int) -> dict[int, tuple[int, int]] | None:
    if not toks:
        return {}
    T = lp.shape[0]
    need = len(toks) + sum(1 for x, y in zip(toks, toks[1:]) if x == y)
    if T < need:
        return None
    ext = [blank if s % 2 == 0 else toks[s // 2] for s in range(2 * len(toks) + 1)]
    S = len(ext)
    ext_a = np.array(ext)
    allow = np.array([s > 1 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
    dp = np.full((T, S), NEG)
    bp = np.zeros((T, S), dtype=np.int32)
    dp[0, 0], dp[0, 1] = lp[0, blank], lp[0, ext[1]]
    for t in range(1, T):
        prev = dp[t - 1]
        step = np.concatenate([[NEG], prev[:-1]])
        skip = np.where(allow, np.concatenate([[NEG, NEG], prev[:-2]]), NEG)
        cand = np.stack([prev, step, skip])
        best = cand.argmax(0)
        dp[t] = cand.max(0) + lp[t, ext_a]
        bp[t] = np.arange(S) - best
    s = S - 1 if dp[T - 1, S - 1] > dp[T - 1, S - 2] else S - 2
    if dp[T - 1, s] <= NEG / 2:
        return None
    path = [0] * T
    for t in range(T - 1, -1, -1):
        path[t] = s
        s = bp[t, s]
    spans: dict[int, tuple[int, int]] = {}
    for t, s in enumerate(path):
        if s % 2 == 1 and owner[s // 2] >= 0:
            wi = owner[s // 2]
            spans[wi] = (spans.get(wi, (t, t))[0], t)
    return spans
