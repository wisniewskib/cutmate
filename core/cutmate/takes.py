"""Checks for picking takes: RMS bins show speech blobs, stumbles and smacks that transcripts smooth away."""
import math
from pathlib import Path

import numpy as np

from .media import read_pcm

SR = 16000


def rms_bins(wav: Path, start: float, end: float, bin_s: float = 0.05) -> list[tuple[float, float]]:
    x = read_pcm(wav, SR)[int(start * SR):int(end * SR)].astype(np.float64)
    n = max(1, int(round(bin_s * SR)))
    out = []
    for i in range(0, len(x) - n + 1, n):
        rms = math.sqrt(float(np.mean(x[i:i + n] ** 2)))
        out.append((round(start + i / SR, 3), round(max(-90.0, 20 * math.log10(rms + 1e-9)), 1)))
    return out


def blobs(bins: list[tuple[float, float]], threshold_db: float = -35.0, min_gap: float = 0.12) -> list[tuple[float, float]]:
    if not bins:
        return []
    step = bins[1][0] - bins[0][0] if len(bins) > 1 else 0.05
    regions, cur = [], None
    for t, db in bins:
        if db > threshold_db:
            if cur and t - cur[1] <= min_gap:
                cur[1] = t + step
            else:
                if cur:
                    regions.append(tuple(cur))
                cur = [t, t + step]
    if cur:
        regions.append(tuple(cur))
    return [(round(a, 3), round(b, 3)) for a, b in regions]
