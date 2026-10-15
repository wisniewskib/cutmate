"""Caption pages (the same pages that are burned in) → SubRip (.srt) for YouTube."""


def _ts(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(pages: list[dict]) -> str:
    blocks = [f"{i}\n{_ts(p['start'])} --> {_ts(p['end'])}\n{' '.join(w[0] for w in p['words'])}\n"
              for i, p in enumerate(pages, 1)]
    return "\n".join(blocks)
